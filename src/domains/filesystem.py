"""Matha 文件系统模块：路径操作、目录管理、权限、挂载。

覆盖：
  1) 路径操作（拼接、解析、规范化）
  2) 目录创建/删除/遍历
  3) 权限检查与修改
  4) 磁盘空间查询
  5) 符号链接
"""
from __future__ import annotations

import os
import shutil
import stat
from datetime import datetime


def path_join(*parts: str) -> str:
    """拼接路径。"""
    return os.path.join(*parts)


def path_basename(path: str) -> str:
    """获取路径的基名。"""
    return os.path.basename(path)


def path_dirname(path: str) -> str:
    """获取路径的目录部分。"""
    return os.path.dirname(path)


def path_ext(path: str) -> str:
    """获取文件扩展名。"""
    return os.path.splitext(path)[1]


def path_normalize(path: str) -> str:
    """规范化路径。"""
    return os.path.normpath(path)


def path_absolute(path: str) -> str:
    """获取绝对路径。"""
    return os.path.abspath(path)


def path_resolve(path: str) -> str:
    """解析符号链接获取真实路径。"""
    return os.path.realpath(path)


def path_exists(path: str) -> bool:
    """路径是否存在。"""
    return os.path.exists(path)


def path_is_file(path: str) -> bool:
    """是否为文件。"""
    return os.path.isfile(path)


def path_is_dir(path: str) -> bool:
    """是否为目录。"""
    return os.path.isdir(path)


def dir_create(path: str, recursive: bool = True) -> bool:
    """创建目录。"""
    try:
        os.makedirs(path, exist_ok=True)
        return True
    except OSError:
        return False


def dir_delete(path: str) -> bool:
    """删除空目录。"""
    try:
        os.rmdir(path)
        return True
    except OSError:
        return False


def dir_delete_all(path: str) -> bool:
    """递归删除目录。"""
    try:
        shutil.rmtree(path)
        return True
    except OSError:
        return False


def dir_list(path: str = ".") -> list[str]:
    """列出目录内容。"""
    try:
        return os.listdir(path)
    except OSError:
        return []


def dir_tree(path: str = ".", max_depth: int = 3) -> list[str]:
    """获取目录树结构。"""
    result = []
    for root, dirs, files in os.walk(path):
        depth = root.replace(path, "").count(os.sep)
        if depth >= max_depth:
            dirs[:] = []
            continue
        root.replace(path, "").lstrip(os.sep)
        indent = "  " * depth
        result.append(f"{indent}{os.path.basename(root)}/")
        for f in files:
            result.append(f"{indent}  {f}")
    return result


def disk_usage(path: str = ".") -> dict:
    """获取磁盘使用情况。"""
    usage = shutil.disk_usage(path)
    return {
        "total": usage.total,
        "used": usage.used,
        "free": usage.free,
        "total_gb": round(usage.total / (1024**3), 2),
        "used_gb": round(usage.used / (1024**3), 2),
        "free_gb": round(usage.free / (1024**3), 2),
        "usage_percent": round(usage.used / usage.total * 100, 1) if usage.total > 0 else 0,
    }


def file_permission(path: str) -> str:
    """获取文件权限（八进制字符串）。"""
    mode = os.stat(path).st_mode
    return oct(stat.S_IMODE(mode))


def file_chmod(path: str, mode: int) -> bool:
    """修改文件权限。"""
    try:
        os.chmod(path, mode)
        return True
    except OSError:
        return False


def symlink_create(target: str, link_name: str) -> bool:
    """创建符号链接。"""
    try:
        os.symlink(target, link_name)
        return True
    except OSError:
        return False


def symlink_resolve(link_name: str) -> str:
    """解析符号链接目标。"""
    try:
        return os.readlink(link_name)
    except OSError:
        return ""


def path_info(path: str) -> dict:
    """获取路径详细信息。"""
    if not os.path.exists(path):
        return {"exists": False}
    stat_info = os.stat(path)
    return {
        "path": path,
        "exists": True,
        "is_file": os.path.isfile(path),
        "is_dir": os.path.isdir(path),
        "size": stat_info.st_size,
        "created": datetime.fromtimestamp(stat_info.st_ctime).isoformat(),
        "modified": datetime.fromtimestamp(stat_info.st_mtime).isoformat(),
        "accessed": datetime.fromtimestamp(stat_info.st_atime).isoformat(),
        "permission": file_permission(path),
    }


# ============================================================
# 注册
# ============================================================

def _register_filesystem(builtins: dict) -> None:
    builtins["路径拼接"] = path_join
    builtins["路径基名"] = path_basename
    builtins["路径目录"] = path_dirname
    builtins["路径扩展名"] = path_ext
    builtins["路径规范化"] = path_normalize
    builtins["路径绝对化"] = path_absolute
    builtins["路径解析"] = path_resolve
    builtins["路径存在"] = path_exists
    builtins["路径是否为文件"] = path_is_file
    builtins["路径是否为目录"] = path_is_dir
    builtins["创建目录"] = dir_create
    builtins["删除目录"] = dir_delete
    builtins["递归删除目录"] = dir_delete_all
    builtins["目录列表"] = dir_list
    builtins["目录树"] = dir_tree
    builtins["磁盘使用"] = disk_usage
    builtins["文件权限"] = file_permission
    builtins["修改权限"] = file_chmod
    builtins["创建符号链接"] = symlink_create
    builtins["解析符号链接"] = symlink_resolve
    builtins["路径信息"] = path_info


def _filesystem_symtab_names() -> list[str]:
    return [
        "路径拼接", "路径基名", "路径目录", "路径扩展名",
        "路径规范化", "路径绝对化", "路径解析", "路径存在",
        "路径是否为文件", "路径是否为目录",
        "创建目录", "删除目录", "递归删除目录", "目录列表",
        "目录树", "磁盘使用", "文件权限", "修改权限",
        "创建符号链接", "解析符号链接", "路径信息",
    ]


__all__ = [
    "path_join", "path_basename", "path_dirname", "path_ext",
    "path_normalize", "path_absolute", "path_resolve",
    "path_exists", "dir_create", "dir_delete", "dir_list",
    "dir_tree", "disk_usage", "file_permission", "file_chmod",
    "symlink_create", "path_info",
    "_register_filesystem", "_filesystem_symtab_names",
]
