"""输出文件名生成与工具函数。"""
from __future__ import annotations

import os
import re
from datetime import datetime


def human_size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.2f} {unit}"
        n /= 1024
    return f"{n:.2f} TB"


def human_time(secs: float) -> str:
    if secs <= 0:
        return "--:--"
    secs = int(secs)
    h, rem = divmod(secs, 3600)
    m, s = divmod(rem, 60)
    return f"{h:d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


_ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitize(name: str) -> str:
    cleaned = _ILLEGAL.sub("_", name).strip(" .")
    return cleaned or "output"


def build_output_path(src: str, out_dir: str, ext: str,
                      pattern: str = "{name}", overwrite: bool = True,
                      index: int = 1) -> str:
    """按命名模板生成输出路径。

    模板变量：{name} 原文件名、{ext} 原扩展名、{date}、{time}、{index}、{parent}
    """
    src_dir, base = os.path.split(os.path.abspath(src))
    stem, src_ext = os.path.splitext(base)
    now = datetime.now()
    fields = {
        "name": stem,
        "ext": src_ext.lstrip("."),
        "date": now.strftime("%Y%m%d"),
        "time": now.strftime("%H%M%S"),
        "index": f"{index:03d}",
        "parent": os.path.basename(src_dir),
    }
    try:
        stem_out = pattern.format(**fields)
    except (KeyError, IndexError, ValueError):
        stem_out = stem
    stem_out = sanitize(stem_out)

    target_dir = os.path.abspath(out_dir) if out_dir else src_dir
    path = os.path.join(target_dir, f"{stem_out}.{ext.lstrip('.')}")

    if os.path.abspath(path) == os.path.abspath(src):
        path = os.path.join(target_dir, f"{stem_out}_converted.{ext.lstrip('.')}")

    if not overwrite:
        path = unique_path(path)
    return path


def unique_path(path: str) -> str:
    """若文件已存在，追加 (1)(2)… 直到不冲突。"""
    if not os.path.exists(path):
        return path
    root, ext = os.path.splitext(path)
    i = 1
    while os.path.exists(f"{root} ({i}){ext}"):
        i += 1
    return f"{root} ({i}){ext}"


def dedupe(path: str, taken: set[str]) -> str:
    """在一批任务内避免输出路径互相冲突；会把结果登记进 taken。"""
    candidate = path
    if candidate in taken:
        root, ext = os.path.splitext(path)
        i = 1
        while f"{root} ({i}){ext}" in taken:
            i += 1
        candidate = f"{root} ({i}){ext}"
    taken.add(candidate)
    return candidate


def collect_files(paths: list[str], recursive: bool = True,
                  exts: tuple[str, ...] | None = None) -> list[str]:
    """展开目录，收集所有匹配的文件。"""
    out: list[str] = []
    for p in paths:
        if os.path.isfile(p):
            out.append(os.path.abspath(p))
        elif os.path.isdir(p):
            walker = os.walk(p) if recursive else [(p, [], os.listdir(p))]
            for root, _dirs, files in walker:
                for f in sorted(files):
                    full = os.path.join(root, f)
                    if not os.path.isfile(full):
                        continue
                    if exts:
                        e = f.rsplit(".", 1)[-1].lower() if "." in f else ""
                        if e not in exts:
                            continue
                    out.append(os.path.abspath(full))
    seen, uniq = set(), []
    for f in out:
        if f not in seen:
            seen.add(f)
            uniq.append(f)
    return uniq
