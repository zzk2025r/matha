# -*- coding: utf-8 -*-
"""matha app —— 应用中心 CLI（阶段 25d）。

商店服务器本体是纯 Matha 模块 应用中心（matha/store_engine.matha），
Python 侧只保留 socket 收发驱动（25 拍板设计）。命令族：

  matha app serve           监听端口，socket 收发驱动引擎（真网络面）
  matha app token           签发令牌（本地引擎或 --store 远程）
  matha app publish         发布应用（本地引擎自动签发令牌；远程须带 --token）
  matha app upgrade         升级已发布应用（存在性校验后重发布）
  matha app list            列出商店应用（本地索引或 --store 远程）
  matha app search          按词搜索（名字/说明子串）
  matha app install         安装应用到 .matha/apps/<应用>/<入口>
  matha app import-release  从 GitHub Release 附件导入应用（公开下载，零凭据）

本地命令经引擎 处理请求(原始HTTP文本) 在进程内驱动（与 socket 面同一引擎、
同一协议）；远程 --store 命令走原生 socket HTTP/1.1 客户端，响应按
Connection: close 读至 EOF（引擎响应无 Content-Length，RFC 7230 §3.3.3
规则 7）。查询参数原样发送、不做百分号解码——与应用中心登记边界一致。
"""
import json
import os
import socket
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path


class AppError(Exception):
    """用户可读的诚实失败（CLI 打印消息并返回 1）。"""


# ============================================================
# 引擎装载与本地驱动
# ============================================================

def _load_engine(root: Path):
    """在 root 下装载 应用中心 引擎；返回 调用(函数名, *参数) 助手。"""
    os.chdir(str(root))
    from src.interp import Interpreter
    ip = Interpreter()
    if ip.load_matha_module("应用中心") is not True:
        raise AppError("应用中心引擎装载失败（matha/store_engine.matha 缺失或损坏）")

    def 调用(name, *args):
        return ip._call_func_or_closure(ip.funcs[name], list(args))

    return 调用


def _local_request(调用, method: str, path: str, body_obj=None) -> tuple[int, dict]:
    """进程内驱动引擎：合成 HTTP/1.1 原始请求 → 处理请求 → (码, JSON体)。"""
    body = ""
    extra = ""
    if body_obj is not None:
        body = json.dumps(body_obj, ensure_ascii=False)
        extra = f"Content-Type: application/json\r\nContent-Length: {len(body.encode('utf-8'))}\r\n"
    raw = f"{method} {path} HTTP/1.1\r\nHost: local\r\n{extra}\r\n{body}"
    frame = 调用("处理请求", raw)
    return _parse_response(frame["响应"])


def _parse_response(raw: str) -> tuple[int, dict]:
    head, _, body = raw.partition("\r\n\r\n")
    status = head.split("\r\n", 1)[0] if "\r\n" in head else head
    parts = status.split(" ")
    code = int(parts[1]) if len(parts) >= 2 and parts[1].isdigit() else 0
    try:
        return code, json.loads(body) if body else {}
    except json.JSONDecodeError as exc:
        raise AppError(f"商店响应体不是合法 JSON（码 {code}）: {exc}") from exc


# ============================================================
# 远程 --store 客户端（原生 socket HTTP/1.1，Connection: close 读尽）
# ============================================================

def _store_addr(store: str) -> tuple[str, int]:
    parsed = urllib.parse.urlparse(store if "//" in store else "//" + store,
                                   scheme="http")
    if parsed.scheme != "http":
        raise AppError(f"商店地址须为 http://（收到 {store!r}）——"
                       "应用中心响应按 Connection: close 明文定界")
    host = parsed.hostname
    if not host:
        raise AppError(f"商店地址缺少主机名: {store!r}")
    return host, parsed.port or 80


def _remote_request(store: str, method: str, path: str, body_obj=None,
                    timeout: float = 10.0) -> tuple[int, dict]:
    host, port = _store_addr(store)
    body_bytes = b""
    headers = [f"Host: {host}", "Connection: close"]
    if body_obj is not None:
        body_bytes = json.dumps(body_obj, ensure_ascii=False).encode("utf-8")
        headers.append("Content-Type: application/json")
        headers.append(f"Content-Length: {len(body_bytes)}")
    req = (f"{method} {path} HTTP/1.1\r\n"
           + "\r\n".join(headers) + "\r\n\r\n").encode("utf-8") + body_bytes
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            sock.settimeout(timeout)
            sock.sendall(req)
            chunks = b""
            while True:
                chunk = sock.recv(65536)
                if not chunk:
                    break
                chunks += chunk
    except OSError as exc:
        raise AppError(f"无法连接商店 {store}: {exc}") from exc
    return _parse_response(chunks.decode("utf-8", errors="replace"))


def _store_request(调用, store, method, path, body_obj=None):
    """--store 给定走远程，否则进程内驱动本地引擎。"""
    if store:
        return _remote_request(store, method, path, body_obj)
    return _local_request(调用, method, path, body_obj)


# ============================================================
# 安装落盘
# ============================================================

def _install_record(root: Path, rec: dict, 应用: str, 来源: str) -> Path:
    入口 = str(rec.get("入口") or "main.matha")
    if "/" in 入口 or "\\" in 入口 or 入口 in (".", ".."):
        raise AppError(f"入口路径不合法: {入口!r}（须为单段文件名）")
    目录 = root / ".matha" / "apps" / 应用
    目录.mkdir(parents=True, exist_ok=True)
    (目录 / 入口).write_text(str(rec.get("内容") or ""), encoding="utf-8")
    manifest = {
        "应用": 应用,
        "版本": rec.get("版本", ""),
        "说明": rec.get("说明", ""),
        "主体": rec.get("主体", ""),
        "入口": 入口,
        "来源": 来源,
        "安装时间": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    (目录 / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return 目录 / 入口


# ============================================================
# 子命令实现
# ============================================================

def cmd_serve(args) -> int:
    """matha app serve：socket 收发驱动 应用中心 引擎（真网络面）。"""
    root = Path(args.root or ".").resolve()
    try:
        调用 = _load_engine(root)
    except AppError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        srv.bind(("", int(args.port)))
        srv.listen(16)
    except OSError as exc:
        print(f"错误: 端口 {args.port} 绑定失败: {exc}", file=sys.stderr)
        return 1
    host, port = srv.getsockname()
    print(f"应用中心服务已启动: http://{host}:{port}（根目录 {root}，Ctrl+C 停止）",
          flush=True)
    try:
        while True:
            srv.settimeout(0.5)
            try:
                conn, addr = srv.accept()
            except TimeoutError:
                continue
            except OSError as exc:
                print(f"错误: 接受连接失败: {exc}", file=sys.stderr)
                continue
            try:
                conn.settimeout(10.0)
                raw = _read_request(conn)
                if raw is not None:
                    frame = 调用("处理请求", raw)
                    conn.sendall(frame["响应"].encode("utf-8"))
            except Exception as exc:
                print(f"警告: 请求处理失败（{addr[0]}）: {exc}", file=sys.stderr)
            finally:
                conn.close()
    except KeyboardInterrupt:
        print("应用中心服务已停止", flush=True)
        return 0
    finally:
        srv.close()


def _read_request(conn) -> str | None:
    """按 HTTP/1.1 收尽一个请求：头界定 + Content-Length 补齐 / 短超时兜底。

    引擎响应无 Content-Length（Connection: close 定界），请求侧客户端
    一般带 Content-Length；不带时以 0.3s 静默判定请求收尽。"""
    buf = b""
    while b"\r\n\r\n" not in buf:
        chunk = conn.recv(65536)
        if not chunk:
            break
        buf += chunk
        if len(buf) > 1_048_576:
            raise ValueError("请求超过 1MiB 上限，拒绝")
    if b"\r\n\r\n" not in buf:
        return None if not buf else buf.decode("utf-8", errors="replace")
    head, _, rest = buf.partition(b"\r\n\r\n")
    length = 0
    for line in head.decode("latin-1").split("\r\n"):
        if line.lower().startswith("content-length:"):
            try:
                length = int(line.split(":", 1)[1].strip())
            except ValueError:
                pass
    while len(rest) < length:
        chunk = conn.recv(65536)
        if not chunk:
            break
        rest += chunk
    if length == 0:
        # 无 Content-Length：0.3s 静默判定请求收尽（同机小请求面）
        conn.settimeout(0.3)
        try:
            extra = conn.recv(65536)
            if extra:
                rest += extra
        except (TimeoutError, OSError):
            pass
    return (head + b"\r\n\r\n" + rest).decode("utf-8", errors="replace")


def cmd_token(args) -> int:
    root = Path(args.root or ".").resolve()
    调用 = _load_engine(root) if not args.store else None
    try:
        code, body = _store_request(调用, args.store, "POST", "/token",
                                    {"主体": args.subject, "过期秒": args.ttl})
    except AppError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1
    if code != 200 or "令牌" not in body:
        print(f"签发失败（码 {code}）: {body.get('错误', body)}", file=sys.stderr)
        return 1
    print(body["令牌"])
    return 0


def _publish_content(args) -> str:
    if args.file and args.content:
        raise AppError("--file 与 --content 只能二选一")
    if args.file:
        path = Path(args.file)
        if not path.is_file():
            raise AppError(f"内容文件不存在: {path}")
        return path.read_text(encoding="utf-8")
    if args.content is None:
        raise AppError("发布内容须以 --file 或 --content 提供")
    return args.content


def _do_publish(调用, args, store, content) -> tuple[int, dict]:
    if store and not args.token:
        raise AppError("远程发布须提供 --token（先 matha app token --store <地址> 签发）")
    body_obj = {"应用": args.app, "版本": args.version, "内容": content,
                "说明": args.desc or "", "入口": args.entry or "main.matha",
                "令牌": args.token}
    note = ""
    if not store:
        if not args.token:
            tcode, tbody = _local_request(调用, "POST", "/token",
                                          {"主体": args.subject or "本地", "过期秒": 3600})
            if tcode != 200 or "令牌" not in tbody:
                raise AppError(f"自动签发本地令牌失败: {tbody.get('错误', tbody)}")
            args.token = tbody["令牌"]
            note = "（已自动签发本地令牌）"
        body_obj["令牌"] = args.token
    code, body = _store_request(调用, store, "POST", "/publish", body_obj)
    if note:
        body = dict(body, 提示=note.strip("（）"))
    return code, body


def cmd_publish(args) -> int:
    return _publish_or_upgrade(args, upgrade=False)


def cmd_upgrade(args) -> int:
    return _publish_or_upgrade(args, upgrade=True)


def _publish_or_upgrade(args, upgrade: bool) -> int:
    root = Path(args.root or ".").resolve()
    store = args.store or None
    try:
        调用 = None if store else _load_engine(root)
        content = _publish_content(args)
        if upgrade:
            old_code, old_body = _store_request(
                调用, store, "GET", f"/apps/{args.app}")
            if old_code != 200:
                raise AppError(f"应用不存在（码 {old_code}）: "
                               f"{old_body.get('错误', old_body)}——升级前请先 publish")
            old_ver = old_body.get("版本", "?")
        code, body = _do_publish(调用, args, store, content)
        if code != 201 or "已发布" not in body:
            print(f"发布失败（码 {code}）: {body.get('错误', body)}", file=sys.stderr)
            return 1
        if upgrade:
            print(f"已升级 {args.app}: {old_ver} → {body.get('版本', args.version)}"
                  + (f"（{body['提示']}）" if body.get("提示") else ""))
        else:
            print(f"已发布 {args.app} 版本 {body.get('版本', args.version)}"
                  + (f"（{body['提示']}）" if body.get("提示") else ""))
        return 0
    except AppError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1


def cmd_list(args) -> int:
    try:
        调用 = None if args.store else _load_engine(Path(args.root or ".").resolve())
        code, body = _store_request(调用, args.store, "GET", "/apps")
    except AppError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1
    if code != 200:
        print(f"列举失败（码 {code}）: {body.get('错误', body)}", file=sys.stderr)
        return 1
    for name in body.get("应用", []):
        print(name)
    return 0


def cmd_search(args) -> int:
    try:
        调用 = None if args.store else _load_engine(Path(args.root or ".").resolve())
        code, body = _store_request(调用, args.store, "GET",
                                    f"/search?q={args.word}")
    except AppError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1
    if code != 200:
        print(f"搜索失败（码 {code}）: {body.get('错误', body)}", file=sys.stderr)
        return 1
    for name in body.get("命中", []):
        print(name)
    return 0


def cmd_install(args) -> int:
    root = Path(args.root or ".").resolve()
    try:
        调用 = None if args.store else _load_engine(root)
        code, body = _store_request(调用, args.store, "GET", f"/apps/{args.app}")
        if code == 404:
            raise AppError(f"应用不存在: {args.app}")
        if code != 200:
            raise AppError(f"获取应用失败（码 {code}）: {body.get('错误', body)}")
        if args.version and body.get("版本") != args.version:
            raise AppError(f"版本不符: 商店为 {body.get('版本')!r}，请求 {args.version!r}")
        入口 = str(body.get("入口") or "main.matha")
        path = _install_record(root, body, args.app,
                               args.store or "本地索引")
        print(f"已安装 {args.app} 版本 {body.get('版本', '?')} → {path}")
        print(f"运行: matha run \"{path.parent / 入口}\"")
        return 0
    except AppError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1


def cmd_import_release(args) -> int:
    root = Path(args.root or ".").resolve()
    base = (args.base_url or "https://github.com").rstrip("/")
    def _seg(s, safe=""):
        return urllib.parse.quote(str(s), safe=safe)
    url = (f"{base}/{_seg(args.repo, safe='/')}"
           f"/releases/download/{_seg(args.tag)}/{_seg(args.asset)}")
    应用 = args.app or Path(args.asset).stem
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Matha-App/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
        content = data.decode("utf-8")
    except Exception as exc:
        print(f"错误: 导入失败（{url}）: {exc}", file=sys.stderr)
        return 1
    try:
        path = _install_record(root, {"内容": content, "版本": args.tag,
                                      "入口": args.entry or "main.matha",
                                      "说明": f"来自 Release {args.tag}"},
                               应用, url)
    except AppError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1
    print(f"已导入 {应用} ← {url}")
    print(f"安装位置: {path}")
    return 0
