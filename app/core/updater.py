"""通过 GitHub Releases 检查新版本并下载安装包。

设计原则：
- 检查与下载失败必须降级（不要 raise），UI 拿到 None 就当「无更新/网络问题」；
- 不阻塞 GUI；调用方应放到 QThreadPool 里跑；
- 版本比较是简单的三元组 (major, minor, patch) 对比；
- 不写死 repo：检查路径从常量读，将来迁移仓库只改一处。
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable

# 单一事实来源：仓库地址。GitHub 上传地址。
GITHUB_REPO = "tanker420/MediaForge"
GITHUB_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

# GitHub API 在国内偶发超时/限流，给个稍宽容的默认超时
DEFAULT_TIMEOUT = 10.0

# Inno Setup 安装包文件名匹配规则（CI 打包产物的命名）
_INSTALLER_RE = re.compile(r"MediaForge-.*-Setup\.exe$", re.IGNORECASE)


@dataclass(frozen=True)
class UpdateInfo:
    """一条可用的新版本信息。"""

    version: str                # 形如 "1.2.3"（不含 v 前缀）
    name: str                   # GitHub Release 标题
    body: str                   # 更新说明（Markdown，纯文本已去除标签）
    asset_url: str              # 安装包 .exe 直链
    asset_size: int             # 安装包字节数
    asset_name: str             # 安装包文件名
    html_url: str               # GitHub Release 页面地址
    published_at: str           # 发布时间（ISO8601）

    def summary(self, max_chars: int = 600) -> str:
        """去掉 Markdown 标记的前若干字符，供对话框显示。"""
        text = _strip_markdown(self.body or "")
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) > max_chars:
            text = text[: max_chars - 1] + "…"
        return text


def parse_version(tag: str) -> tuple[int, ...]:
    """把 'v1.2.3' / '1.2.3-rc1' 解析成 (1, 2, 3) 用于比较。

    解析失败返回 (-1,) 让任意新版本都显得「不比当前旧」。
    """
    s = (tag or "").strip().lstrip("v").split("-", 1)[0]
    parts = s.split(".")
    try:
        return tuple(int(p) for p in parts)
    except ValueError:
        return (-1,)


def _strip_markdown(md: str) -> str:
    """极简 Markdown → 纯文本：去除常见标记，保留链接文本与列表项。"""
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", md)              # 图片
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)        # 链接
    text = re.sub(r"`([^`]*)`", r"\1", text)                    # 行内代码
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)  # 标题
    text = re.sub(r"^\s*[-*+]\s+", "• ", text, flags=re.MULTILINE)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)              # 加粗
    text = re.sub(r"\*([^*]+)\*", r"\1", text)                  # 斜体
    text = re.sub(r"~~([^~]+)~~", r"\1", text)                  # 删除线
    return text


def _http_get(url: str, timeout: float = DEFAULT_TIMEOUT) -> bytes:
    """带 User-Agent 的 GET；网络错误抛出 urllib.error.URLError。"""
    req = urllib.request.Request(url, headers={
        "User-Agent": "MediaForge-Updater/1.0 (+https://github.com/tanker420/MediaForge)",
        "Accept": "application/vnd.github+json",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def check_for_update(current: str, *,
                     repo: str = GITHUB_REPO,
                     prerelease: bool = False,
                     timeout: float = DEFAULT_TIMEOUT) -> UpdateInfo | None:
    """联网检查 GitHub Releases，发现新版本则返回 UpdateInfo。

    返回 None 表示「已是最新 / 网络失败 / 无匹配资产」，调用方无需区分原因。
    """
    try:
        api_url = (f"https://api.github.com/repos/{repo}/releases/latest"
                   if not prerelease else
                   f"https://api.github.com/repos/{repo}/releases")
        data = json.loads(_http_get(api_url, timeout=timeout).decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None

    candidates = data if isinstance(data, list) else [data]
    if prerelease:
        candidates = [r for r in candidates if not r.get("draft")]
    else:
        # 只取首个稳定版；prerelease 自动跳过
        candidates = [r for r in candidates if not r.get("prerelease")][:1]

    if not candidates:
        return None
    rel = candidates[0]

    tag = rel.get("tag_name") or ""
    new_v = parse_version(tag)
    cur_v = parse_version(current)
    if new_v <= cur_v or (-1,) in (new_v, cur_v):
        return None

    # 在 assets 里找安装包（按命名规则匹配）
    asset = next((a for a in rel.get("assets", [])
                  if _INSTALLER_RE.search(a.get("name", ""))), None)
    if not asset:
        return None

    return UpdateInfo(
        version=".".join(str(x) for x in new_v),
        name=rel.get("name") or tag,
        body=rel.get("body") or "",
        asset_url=asset.get("browser_download_url", ""),
        asset_size=int(asset.get("size") or 0),
        asset_name=asset.get("name", ""),
        html_url=rel.get("html_url", ""),
        published_at=rel.get("published_at", ""),
    )


# --------------------------------------------------------------------------
# 下载 / 安装
# --------------------------------------------------------------------------
ProgressCB = Callable[[int, int], None]    # (bytes_done, bytes_total)
CancelCheck = Callable[[], bool]           # 返回 True 表示取消


def download(url: str, dest: str, *,
             timeout: float = 30.0,
             on_progress: ProgressCB | None = None,
             cancel: CancelCheck | None = None,
             chunk: int = 64 * 1024) -> str:
    """流式下载 url 到 dest（带进度回调，可取消）。返回 dest 路径。

    失败抛 urllib.error.URLError / OSError，由调用方处理。
    """
    req = urllib.request.Request(url, headers={
        "User-Agent": "MediaForge-Updater/1.0",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        # 原子写入：先下载到同目录的 .part，再 rename
        tmp = dest + ".part"
        with open(tmp, "wb") as f:
            while True:
                if cancel and cancel():
                    raise _Canceled("用户取消下载")
                block = resp.read(chunk)
                if not block:
                    break
                f.write(block)
                done += len(block)
                if on_progress:
                    on_progress(done, total)
    os.replace(tmp, dest)
    return dest


class _Canceled(Exception):
    pass


def download_update(info: UpdateInfo, *,
                    on_progress: ProgressCB | None = None,
                    cancel: CancelCheck | None = None) -> str:
    """把 UpdateInfo 指向的安装包下载到系统临时目录，返回本地路径。"""
    suffix = "_" + re.sub(r"[^\w.-]", "_", info.asset_name or "installer.exe")
    dest = os.path.join(tempfile.gettempdir(), f"MediaForgeUpdate{suffix}")
    return download(info.asset_url, dest,
                    on_progress=on_progress, cancel=cancel)


def launch_installer_and_exit(installer_path: str) -> None:
    """启动安装包并退出当前进程。

    Inno Setup 静默参数：
      /SP-    跳过「即将安装」欢迎页
      /VERYSILENT  完全静默（无进度窗口）
      /SUPPRESSMSGBOXES  不弹完成对话框
      /CLOSEAPPLICATIONS  关闭正在运行的应用（依赖 [Setup] AppMutex）
      /NORESTART  安装完不重启

    AppMutex 由 packaging/installer.iss 定义，确保安装程序能可靠关闭 MediaForge。
    """
    flags = ["/SP-", "/VERYSILENT", "/SUPPRESSMSGBOXES",
             "/CLOSEAPPLICATIONS", "/NORESTART"]
    # detached 启动，不等待；非 Windows 平台仅作占位
    creationflags = 0
    if os.name == "nt":
        creationflags = 0x08000000  # CREATE_NO_WINDOW
    try:
        subprocess.Popen([installer_path] + flags,
                         creationflags=creationflags,
                         close_fds=True)
    except OSError:
        # 启动失败也照常退出——用户可手动重试
        pass
    # 给安装器一点时间识别 mutex，再退出
    time.sleep(0.5)
    sys.exit(0)


__all__ = [
    "GITHUB_REPO",
    "UpdateInfo",
    "parse_version",
    "check_for_update",
    "download",
    "download_update",
    "launch_installer_and_exit",
]