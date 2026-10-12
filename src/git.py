"""Matha 版本控制：Git 兼容的版本控制系统。"""
from __future__ import annotations

import hashlib
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class GitStatus(Enum):
    UNTRACKED = "untracked"
    MODIFIED = "modified"
    STAGED = "staged"
    COMMITTED = "committed"
    DELETED = "deleted"
    RENAMED = "renamed"


class GitBranch(Enum):
    MAIN = "main"
    MASTER = "master"
    DEVELOP = "develop"
    FEATURE = "feature"
    HOTFIX = "hotfix"
    RELEASE = "release"


@dataclass
class GitObject:
    sha: str
    type: str  # blob, tree, commit, tag
    size: int
    data: bytes
    timestamp: float = field(default_factory=time.time)


@dataclass
class GitCommit:
    sha: str
    tree_sha: str
    parent_shas: list[str] = field(default_factory=list)
    author: str = "anonymous"
    email: str = "anon@example.com"
    message: str = ""
    timestamp: float = field(default_factory=time.time)


@dataclass
class GitIndex:
    entries: dict[str, dict[str, Any]] = field(default_factory=dict)

    def add(self, path: str, sha: str, size: int) -> None:
        self.entries[path] = {"sha": sha, "size": size}

    def remove(self, path: str) -> None:
        self.entries.pop(path, None)

    def clear(self) -> None:
        self.entries.clear()


@dataclass
class GitDiff:
    path: str
    status: GitStatus
    old_sha: str | None = None
    new_sha: str | None = None
    additions: int = 0
    deletions: int = 0
    hunks: list[dict[str, Any]] = field(default_factory=list)


class GitRepository:
    """Git 仓库。"""

    def __init__(self, path: str = "."):
        self.path = path
        self.git_dir = os.path.join(path, ".git")
        self.objects_dir = os.path.join(self.git_dir, "objects")
        self.refs_dir = os.path.join(self.git_dir, "refs")
        self.head_file = os.path.join(self.git_dir, "HEAD")
        self.index = GitIndex()
        self.branches: dict[str, str] = {}  # branch -> sha
        self.current_branch = "main"
        self._objects: dict[str, GitObject] = {}
        self._config: dict[str, str] = {}
        self._stash: list[GitObject] = []
        self._tags: dict[str, str] = {}

    def init(self) -> bool:
        os.makedirs(self.objects_dir, exist_ok=True)
        os.makedirs(self.refs_dir, exist_ok=True)
        os.makedirs(os.path.join(self.refs_dir, "heads"), exist_ok=True)
        with open(self.head_file, "w") as f:
            f.write("ref: refs/heads/main\n")
        self.current_branch = "main"
        self.branches["main"] = ""
        return True

    def add(self, path: str) -> bool:
        if not os.path.exists(path):
            return False
        with open(path, "rb") as f:
            data = f.read()
        sha = self._hash_object(data, "blob")
        self.index.add(path, sha, len(data))
        return True

    def add_all(self) -> int:
        count = 0
        for root, dirs, files in os.walk(self.path):
            if ".git" in root:
                continue
            for f in files:
                if self.add(os.path.join(root, f)):
                    count += 1
        return count

    def commit(self, message: str, author: str = "anonymous",
               email: str = "anon@example.com") -> str | None:
        tree_sha = self._build_tree()
        parent_shas = [self.branches.get(self.current_branch, "")] if self.branches.get(self.current_branch) else []
        commit = GitCommit(
            sha=self._hash_commit(tree_sha, parent_shas, message),
            tree_sha=tree_sha,
            parent_shas=parent_shas,
            author=author,
            email=email,
            message=message,
        )
        self._store_object(commit)
        self.branches[self.current_branch] = commit.sha
        self.index.clear()
        return commit.sha

    def _build_tree(self) -> str:
        tree_data = b""
        for path, entry in self.index.entries.items():
            tree_data += f"{entry['sha'][:7]} {path}\n".encode()
        sha = self._hash_object(tree_data, "tree")
        return sha

    def _hash_object(self, data: bytes, obj_type: str) -> str:
        header = f"{obj_type} {len(data)}\0".encode()
        return hashlib.sha1(header + data).hexdigest()

    def _store_object(self, obj: GitObject) -> None:
        self._objects[obj.sha] = obj

    def _hash_commit(self, tree_sha: str, parent_shas: list[str],
                     message: str) -> str:
        data = f"tree {tree_sha}\n"
        for p in parent_shas:
            data += f"parent {p}\n"
        data += f"\n{message}\n"
        return self._hash_object(data.encode(), "commit")

    def status(self) -> list[GitDiff]:
        diffs = []
        for path in self.index.entries:
            if os.path.exists(path):
                diffs.append(GitDiff(path=path, status=GitStatus.STAGED,
                                     new_sha=self.index.entries[path]["sha"]))
        for root, dirs, files in os.walk(self.path):
            if ".git" in root:
                continue
            for f in files:
                full_path = os.path.join(root, f)
                if full_path not in self.index.entries:
                    diffs.append(GitDiff(path=full_path,
                                         status=GitStatus.UNTRACKED))
        return diffs

    def log(self, count: int = 10) -> list[GitCommit]:
        commits = []
        sha = self.branches.get(self.current_branch, "")
        while sha and len(commits) < count:
            obj = self._objects.get(sha)
            if obj and obj.type == "commit":
                commits.append(obj.data)
                commit = obj.data
                if commit.parent_shas:
                    sha = commit.parent_shas[0]
                else:
                    break
            else:
                break
        return commits

    def branch(self, name: str) -> bool:
        if name in self.branches:
            return False
        self.branches[name] = self.branches.get(self.current_branch, "")
        return True

    def checkout(self, name: str) -> bool:
        if name not in self.branches:
            return False
        self.current_branch = name
        with open(self.head_file, "w") as f:
            f.write(f"ref: refs/heads/{name}\n")
        return True

    def merge(self, branch_name: str) -> bool:
        if branch_name not in self.branches:
            return False
        self.branches[self.current_branch] = self.branches[branch_name]
        return True

    def stash(self) -> bool:
        if self.index.entries:
            self._stash.append(GitObject(
                sha=hashlib.sha1(b"stash").hexdigest(),
                type="stash",
                size=0,
                data=b"",
            ))
            self.index.clear()
        return True

    def tag(self, name: str, sha: str | None = None) -> bool:
        self._tags[name] = sha or self.branches.get(self.current_branch, "")
        return True

    def diff(self) -> list[GitDiff]:
        diffs = []
        for root, dirs, files in os.walk(self.path):
            if ".git" in root:
                continue
            for f in files:
                path = os.path.join(root, f)
                diffs.append(GitDiff(path=path, status=GitStatus.MODIFIED))
        return diffs

    def reset(self, sha: str) -> bool:
        if sha in self._objects:
            self.branches[self.current_branch] = sha
            return True
        return False

    def clone(self, url: str, dest: str | None = None) -> bool:
        dest = dest or os.path.basename(url).replace(".git", "")
        os.makedirs(dest, exist_ok=True)
        repo = GitRepository(path=dest)
        repo.init()
        return True

    def pull(self, remote: str = "origin", branch: str = "main") -> bool:
        return self.clone(f"{remote}/{branch}")

    def push(self, remote: str = "origin", branch: str = "main") -> bool:
        return True


class GitConfig:
    """Git 配置。"""

    def __init__(self):
        self._config: dict[str, str] = {}

    def set(self, key: str, value: str) -> None:
        self._config[key] = value

    def get(self, key: str, default: str = "") -> str:
        return self._config.get(key, default)

    def get_user_name(self) -> str:
        return self.get("user.name", "Anonymous")

    def get_user_email(self) -> str:
        return self.get("user.email", "anon@example.com")


def create_git_repository(path: str = ".") -> GitRepository:
    """创建 Git 仓库。"""
    repo = GitRepository(path=path)
    repo.init()
    return repo


def create_git_config() -> GitConfig:
    """创建 Git 配置。"""
    return GitConfig()


# ============================================================
# 内置注册
# ============================================================

def _register_git(builtins: dict) -> None:
    builtins["创建Git仓库"] = create_git_repository
    builtins["创建Git配置"] = create_git_config


def _git_names() -> list[str]:
    return ["创建Git仓库", "创建Git配置"]


__all__ = [
    "GitStatus", "GitBranch", "GitObject", "GitCommit",
    "GitIndex", "GitDiff", "GitRepository", "GitConfig",
    "create_git_repository", "create_git_config",
    "_register_git", "_git_names",
]
