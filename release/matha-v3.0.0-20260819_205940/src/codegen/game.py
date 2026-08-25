# -*- coding: utf-8 -*-
"""GameGenerator：把 Matha 规格编译为 HTML5 Canvas 游戏。

游戏与建模同属「交互式可视化」体系：
  - 建模 = 静态 3D 场景展示（Model3DGenerator）
  - 游戏 = 动态 2D 交互场景（GameGenerator，Canvas + 游戏循环）

输出文件：
  - index.html  可直接双击运行的 Canvas 游戏

游戏规格元素（通过 AppSpec.elements 传入）：
  角色（player）   ：玩家控制的角色，支持键盘移动
  敌人（enemy）    ：自动移动的障碍物/敌人
  收集（collect）  ：可拾取的物品（加分）
  墙壁（wall）     ：不可穿越的障碍
  文字（text）     ：UI 文字（标题/提示）
  脚本（脚本）     ：自定义 JS 逻辑

额外字段（meta）：
  宽度 = "800"          画布宽
  高度 = "600"          画布高
  背景 = "#000"         画布背景色
  帧率 = "60"           目标帧率
  标题 = "贪吃蛇"       页面标题

游戏机制（自动生成）：
  - requestAnimationFrame 游戏循环
  - 键盘控制（方向键/WASD）
  - AABB 碰撞检测
  - 计分系统 + 生命值
  - 胜负判定
  - 重新开始
"""

from __future__ import annotations
from src.codegen.base import Generator, CodegenResult, Element


class GameGenerator(Generator):
    """游戏生成器：AppSpec → HTML5 Canvas 游戏。"""

    def generate(self) -> CodegenResult:
        try:
            html = self._build_html()
            path = self._write("index.html", html)
        except Exception as e:
            return CodegenResult(成功=False, 类型="游戏", 名称=self.app.name,
                                 错误=str(e))
        return CodegenResult(
            成功=True, 类型="游戏", 名称=self.app.name,
            文件=[path], 入口=path,
        )

    def _build_html(self) -> str:
        """构建完整 HTML 游戏页面。"""
        title = self.app.title or self.app.name
        width = self.app.meta.get("宽度", "800")
        height = self.app.meta.get("高度", "600")
        bg = self.app.meta.get("背景", "#1a1a2e")
        fps = self.app.meta.get("帧率", "60")

        # 分类元素
        players = []
        enemies = []
        collects = []
        walls = []
        texts = []
        scripts = []
        for el in self.app.elements:
            tag = el.tag.lower()
            if tag in ("player", "玩家", "角色"):
                players.append(el)
            elif tag in ("enemy", "敌人", "障碍"):
                enemies.append(el)
            elif tag in ("collect", "收集", "物品", "食物"):
                collects.append(el)
            elif tag in ("wall", "墙", "墙壁", "障碍墙"):
                walls.append(el)
            elif tag in ("h1", "h2", "h3", "p", "label", "text", "文字"):
                texts.append(el)
            elif tag == "脚本":
                scripts.append(el.text)

        # 生成 JS 游戏逻辑
        js = self._build_js(players, enemies, collects, walls, width, height)

        # 自定义脚本
        custom_js = "\n".join(scripts)

        # UI 文字
        text_html = ""
        for t in texts:
            tag = t.tag.lower()
            if tag in ("h1", "h2", "h3"):
                text_html += f'<{tag}>{self._escape_html(t.text)}</{tag}>\n'
            else:
                text_html += f'<p>{self._escape_html(t.text)}</p>\n'

        return (
            f"<!DOCTYPE html>\n"
            f'<html lang="zh-CN">\n'
            f"<head>\n"
            f'  <meta charset="UTF-8">\n'
            f"  <title>{self._escape_html(title)}</title>\n"
            f"  <style>\n"
            f"    * {{ margin: 0; padding: 0; box-sizing: border-box; }}\n"
            f"    body {{\n"
            f'      background: #0f0f1a; color: #eee;\n'
            f'      font-family: "Microsoft YaHei", sans-serif;\n'
            f"      display: flex; flex-direction: column;\n"
            f"      align-items: center; min-height: 100vh; padding: 20px;\n"
            f"    }}\n"
            f"    h1 {{ margin-bottom: 10px; color: #e94560; }}\n"
            f"    #hud {{\n"
            f"      display: flex; gap: 30px; margin-bottom: 10px;\n"
            f"      font-size: 18px; font-weight: bold;\n"
            f"    }}\n"
            f"    #hud span {{ color: #0f3460; background: #e94560; }}\n"
            f"    #hud b {{ color: #e94560; }}\n"
            f"    canvas {{\n"
            f"      border: 3px solid #e94560; border-radius: 8px;\n"
            f"      box-shadow: 0 0 30px rgba(233,69,96,0.3);\n"
            f"    }}\n"
            f"    #msg {{\n"
            f"      position: absolute; top: 50%; left: 50%;\n"
            f"      transform: translate(-50%,-50%);\n"
            f"      font-size: 32px; color: #e94560; font-weight: bold;\n"
            f"      display: none; text-align: center;\n"
            f"    }}\n"
            f"    #msg button {{\n"
            f"      margin-top: 15px; padding: 8px 24px; font-size: 18px;\n"
            f"      background: #e94560; color: #fff; border: none;\n"
            f"      border-radius: 5px; cursor: pointer;\n"
            f"    }}\n"
            f"    p {{ color: #aaa; margin-top: 10px; }}\n"
            f"  </style>\n"
            f"</head>\n"
            f"<body>\n"
            f"  {text_html}"
            f'  <div id="hud">\n'
            f'    <span>分数: <b id="score">0</b></span>\n'
            f'    <span>生命: <b id="lives">3</b></span>\n'
            f"  </div>\n"
            f'  <canvas id="game" width="{width}" height="{height}" '
            f'style="background:{bg}"></canvas>\n'
            f'  <div id="msg"></div>\n'
            f"  <script>\n"
            f"{js}\n"
            f"{custom_js}\n"
            f"  </script>\n"
            f"</body>\n"
            f"</html>\n"
        )

    def _build_js(self, players, enemies, collects, walls,
                  cw: str, ch: str) -> str:
        """生成游戏 JS 逻辑。"""
        # 玩家初始参数
        px, py, pr = "400", "300", "15"
        pspeed = "5"
        pcolor = "#e94560"
        if players:
            a = self._attrs_dict(players[0])
            px = a.get("x", px)
            py = a.get("y", py)
            pr = a.get("r", a.get("半径", pr))
            pspeed = a.get("speed", a.get("速度", pspeed))
            pcolor = a.get("color", a.get("颜色", pcolor))

        # 敌人列表
        enemy_defs = []
        for e in enemies:
            a = self._attrs_dict(e)
            enemy_defs.append({
                "x": a.get("x", "100"),
                "y": a.get("y", "100"),
                "r": a.get("r", a.get("半径", "12")),
                "speed": a.get("speed", a.get("速度", "2")),
                "color": a.get("color", a.get("颜色", "#0f3460")),
                "dx": a.get("dx", "1"),
                "dy": a.get("dy", "1"),
            })

        # 收集品列表
        collect_defs = []
        for c in collects:
            a = self._attrs_dict(c)
            collect_defs.append({
                "x": a.get("x", "200"),
                "y": a.get("y", "200"),
                "r": a.get("r", a.get("半径", "8")),
                "color": a.get("color", a.get("颜色", "#16c79a")),
                "score": a.get("score", a.get("分数", "10")),
            })

        # 墙壁列表
        wall_defs = []
        for w in walls:
            a = self._attrs_dict(w)
            wall_defs.append({
                "x": a.get("x", "0"),
                "y": a.get("y", "0"),
                "w": a.get("w", a.get("宽", "50")),
                "h": a.get("h", a.get("高", "50")),
                "color": a.get("color", a.get("颜色", "#555")),
            })

        # 构建 JS 数组字面量
        enemy_js = ", ".join(
            f'{{x:{e["x"]},y:{e["y"]},r:{e["r"]},s:{e["speed"]},'
            f'c:"{e["color"]}",dx:{e["dx"]},dy:{e["dy"]}}}'
            for e in enemy_defs
        ) or "{x:100,y:100,r:12,s:2,c:'#0f3460',dx:1,dy:1}"

        collect_js = ", ".join(
            f'{{x:{c["x"]},y:{c["y"]},r:{c["r"]},'
            f'c:"{c["color"]}",sc:{c["score"]}}}'
            for c in collect_defs
        ) or "{x:200,y:200,r:8,c:'#16c79a',sc:10}"

        wall_js = ", ".join(
            f'{{x:{w["x"]},y:{w["y"]},w:{w["w"]},h:{w["h"]},c:"{w["color"]}"}}'
            for w in wall_defs
        )

        return (
            f"// ===== Matha 生成的游戏引擎 =====\n"
            f"const canvas = document.getElementById('game');\n"
            f"const ctx = canvas.getContext('2d');\n"
            f"const W = canvas.width, H = canvas.height;\n"
            f"let score = 0, lives = 3, gameOver = false, won = false;\n"
            f"const keys = {{}};\n\n"
            f"// 玩家\n"
            f"const player = {{x:{px}, y:{py}, r:{pr}, s:{pspeed}, c:'{pcolor}'}};\n\n"
            f"// 敌人\n"
            f"const enemies = [{enemy_js}];\n\n"
            f"// 收集品\n"
            f"const items = [{collect_js}];\n"
            f"let totalItems = items.length;\n\n"
            f"// 墙壁\n"
            f"const walls = [{wall_js}];\n\n"
            f"// 键盘输入\n"
            f"document.addEventListener('keydown', e => keys[e.key] = true);\n"
            f"document.addEventListener('keyup', e => keys[e.key] = false);\n\n"
            f"// AABB 碰撞\n"
            f"function hit(a, b) {{\n"
            f"  let dx = a.x - b.x, dy = a.y - b.y;\n"
            f"  let d = Math.sqrt(dx*dx + dy*dy);\n"
            f"  return d <= (a.r || 10) + (b.r || 10);\n"
            f"}}\n"
            f"function hitWall(p, w) {{\n"
            f"  return p.x + p.r >= w.x && p.x - p.r <= w.x + w.w &&\n"
            f"         p.y + p.r >= w.y && p.y - p.r <= w.y + w.h;\n"
            f"}}\n\n"
            f"// 更新逻辑\n"
            f"function update() {{\n"
            f"  if (gameOver) return;\n"
            f"  // 玩家移动\n"
            f"  if (keys['ArrowLeft']||keys['a']||keys['A']) player.x -= player.s;\n"
            f"  if (keys['ArrowRight']||keys['d']||keys['D']) player.x += player.s;\n"
            f"  if (keys['ArrowUp']||keys['w']||keys['W']) player.y -= player.s;\n"
            f"  if (keys['ArrowDown']||keys['s']||keys['S']) player.y += player.s;\n"
            f"  // 边界\n"
            f"  player.x = Math.max(player.r, Math.min(W-player.r, player.x));\n"
            f"  player.y = Math.max(player.r, Math.min(H-player.r, player.y));\n"
            f"  // 墙壁碰撞\n"
            f"  for (let w of walls) {{ if (hitWall(player, w)) {{\n"
            f"    player.x = Math.max(player.r, Math.min(W-player.r, player.x));\n"
            f"    player.y = Math.max(player.r, Math.min(H-player.r, player.y));\n"
            f"  }} }}\n"
            f"  // 敌人移动\n"
            f"  for (let e of enemies) {{\n"
            f"    e.x += e.dx * e.s; e.y += e.dy * e.s;\n"
            f"    if (e.x < e.r || e.x > W-e.r) e.dx *= -1;\n"
            f"    if (e.y < e.r || e.y > H-e.r) e.dy *= -1;\n"
            f"    if (hit(player, e)) {{\n"
            f"      lives--; document.getElementById('lives').textContent = lives;\n"
            f"      player.x = {px}; player.y = {py};\n"
            f"      if (lives <= 0) endGame(false);\n"
            f"    }}\n"
            f"  }}\n"
            f"  // 收集品\n"
            f"  for (let i = items.length-1; i >= 0; i--) {{\n"
            f"    if (hit(player, items[i])) {{\n"
            f"      score += items[i].sc;\n"
            f"      document.getElementById('score').textContent = score;\n"
            f"      items.splice(i, 1);\n"
            f"      if (items.length === 0) endGame(true);\n"
            f"    }}\n"
            f"  }}\n"
            f"}}\n\n"
            f"// 绘制\n"
            f"function draw() {{\n"
            f"  ctx.clearRect(0, 0, W, H);\n"
            f"  // 墙壁\n"
            f"  for (let w of walls) {{\n"
            f"    ctx.fillStyle = w.c;\n"
            f"    ctx.fillRect(w.x, w.y, w.w, w.h);\n"
            f"  }}\n"
            f"  // 收集品\n"
            f"  for (let it of items) {{\n"
            f"    ctx.fillStyle = it.c;\n"
            f"    ctx.beginPath(); ctx.arc(it.x, it.y, it.r, 0, Math.PI*2); ctx.fill();\n"
            f"  }}\n"
            f"  // 敌人\n"
            f"  for (let e of enemies) {{\n"
            f"    ctx.fillStyle = e.c;\n"
            f"    ctx.beginPath(); ctx.arc(e.x, e.y, e.r, 0, Math.PI*2); ctx.fill();\n"
            f"  }}\n"
            f"  // 玩家\n"
            f"  ctx.fillStyle = player.c;\n"
            f"  ctx.beginPath(); ctx.arc(player.x, player.y, player.r, 0, Math.PI*2); ctx.fill();\n"
            f"}}\n\n"
            f"// 游戏结束\n"
            f"function endGame(victory) {{\n"
            f"  gameOver = true; won = victory;\n"
            f"  let msg = document.getElementById('msg');\n"
            f"  msg.style.display = 'block';\n"
            f"  msg.innerHTML = (victory ? '胜利！' : '游戏结束') +\n"
            f"    '<br>分数: ' + score +\n"
            f"    '<br><button onclick=\"location.reload()\">重新开始</button>';\n"
            f"}}\n\n"
            f"// 游戏循环\n"
            f"function loop() {{\n"
            f"  update();\n"
            f"  draw();\n"
            f"  if (!gameOver) requestAnimationFrame(loop);\n"
            f"}}\n"
            f"loop();\n"
        )

    def _attrs_dict(self, el: Element) -> dict[str, str]:
        return {k: v for k, v in el.attrs}

    @staticmethod
    def _escape_html(text: str) -> str:
        return (text.replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;"))
