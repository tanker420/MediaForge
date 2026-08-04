"""命令行批量转换入口（可选）。

图形界面是默认启动方式（运行 main.py 即可）；本模块为脚本化、
批量处理、无头服务器等场景提供等价的命令行能力。

修复说明（A1）：`-f/--format` 与 `--out-format` 此前共用同一个
argparse dest，导致 --help 中互相覆盖。现改为：
  -f/--kind  媒体类别（video/audio/image）
  -F/--out-format  输出格式扩展名
互不冲突。
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import Any

from .core import formats as F
from .core import presets as P
from .core.converter import ConversionQueue, Job, Status
from .core.ffmpeg_builder import preview_command
from .core.ffprobe import ffmpeg_path, ffmpeg_version, invalidate_caches
from .core.naming import build_output_path, collect_files, dedupe

__version__ = "1.0.0"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mediaforge",
        description="MediaForge 全能媒体格式转换器（命令行模式）",
        epilog="示例：\n"
               "  mediaforge -i 视频.mp4 -F mkv -p video_codec=copy -p audio_codec=copy   # 仅换容器\n"
               "  mediaforge -i 目录 -F mp3 -p audio_bitrate=192k --workers 4             # 批量压音频\n"
               "  mediaforge -i 图片.png -F webp --preset \"WebP 有损\"                     # 图片批处理\n"
               "  mediaforge --list-formats                                              # 查看支持的格式",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"MediaForge {__version__}")

    src = parser.add_argument_group("输入与输出")
    src.add_argument("-i", "--input", nargs="+", action="append", metavar="PATH",
                     help="输入文件或目录，可多次指定；目录会递归收集支持的媒体文件")
    src.add_argument("-o", "--out-dir", metavar="DIR", help="输出目录（默认与源文件相同）")
    src.add_argument("-F", "--out-format", dest="out_format", metavar="EXT",
                     help="输出格式扩展名，如 mp4 / mp3 / png（与 --preset 二选一，通常都要给）")
    src.add_argument("-f", "--kind", dest="kind", choices=(F.VIDEO, F.AUDIO, F.IMAGE),
                     help="媒体类别过滤；不填则按第一个输入文件自动识别")

    opt = parser.add_argument_group("转换选项")
    opt.add_argument("--preset", metavar="NAME", help="应用内置/用户预设，如 “MP4 通用高质量”")
    opt.add_argument("-p", "--param", dest="params", action="append", default=[],
                     metavar="KEY=VALUE",
                     help="覆盖参数，可多次使用，如 -p crf=18 -p two_pass=1 -p width=1920")
    opt.add_argument("--vcodec", dest="video_codec", help="视频编码器（如 libx264 / h264_nvenc / copy）")
    opt.add_argument("--acodec", dest="audio_codec", help="音频编码器（如 aac / libopus / copy）")
    opt.add_argument("--pattern", default="{name}", help="输出命名模板，默认 {name}（原文件名）")
    opt.add_argument("--workers", type=int, default=2, help="并行任务数（默认 2）")
    overwrite = opt.add_mutually_exclusive_group()
    overwrite.add_argument("--overwrite", dest="overwrite", action="store_true",
                           help="覆盖已存在的同名文件（默认行为）")
    overwrite.add_argument("--no-overwrite", dest="overwrite", action="store_false",
                           help="跳过已存在的同名文件（自动追加 (1)(2)… 后缀）")

    info = parser.add_argument_group("信息与维护")
    info.add_argument("--dry-run", action="store_true",
                      help="只打印将要执行的命令，不实际转换")
    info.add_argument("--list-formats", action="store_true", help="列出支持的输出格式")
    info.add_argument("--list-presets", action="store_true", help="列出全部预设")
    info.add_argument("--list-codecs", action="store_true", help="列出当前 ffmpeg 可用的编码器")
    info.add_argument("--refresh", action="store_true",
                      help="清除 ffmpeg 探测缓存后退出（安装/更换 ffmpeg 后使用）")
    return parser


def _parse_param(text: str) -> tuple[str, str]:
    if "=" not in text:
        raise ValueError(f"参数格式应为 KEY=VALUE：{text}")
    key, _, value = text.partition("=")
    return key.strip(), value.strip()


def _collect_params(args: argparse.Namespace, kind: str,
                    ext: str, preset: P.Preset | None) -> dict[str, Any]:
    """按 默认值 → 预设 → 命令行覆盖 的顺序合并参数。"""
    params = F.default_params_for(kind)
    if preset:
        params.update(preset.params)
    for text in args.params:
        key, value = _parse_param(text)
        params[key] = value
    if args.video_codec is not None:
        params["video_codec"] = args.video_codec
    if args.audio_codec is not None:
        params["audio_codec"] = args.audio_codec
    if args.overwrite is not None:
        params["overwrite"] = args.overwrite
    if kind != F.IMAGE:
        fmt = F.find_format(ext, kind)
        if fmt:
            params.setdefault("video_codec", fmt.video_codecs[0] if fmt.video_codecs else "")
            params.setdefault("audio_codec", fmt.audio_codecs[0] if fmt.audio_codecs else "")
    return params


def _print_formats() -> None:
    print("支持的输出格式：")
    for kind, title in ((F.VIDEO, "视频"), (F.AUDIO, "音频"), (F.IMAGE, "图片")):
        print(f"\n【{title}】")
        for f in F.formats_for(kind):
            print(f"  .{f.ext:<8} {f.label}" + (f"（{f.notes}）" if f.notes else ""))


def _print_presets() -> None:
    print("可用预设：")
    for kind, title in ((F.VIDEO, "视频"), (F.AUDIO, "音频"), (F.IMAGE, "图片")):
        print(f"\n【{title}】")
        for p in P.all_presets(kind):
            mark = "内置" if p.builtin else "用户"
            print(f"  {p.name}  [{mark}]  {p.description}")


def _print_codecs() -> None:
    ff = ffmpeg_path()
    if not ff:
        print("未找到 ffmpeg，无法列出编码器。", file=sys.stderr)
        return
    from .core.ffprobe import available_encoders
    encs = sorted(available_encoders())
    print(f"当前 ffmpeg（{ff}）可用编码器 {len(encs)} 个：")
    print(" ".join(encs))


def _resolve_inputs(paths: list[str], kind: str) -> list[str]:
    # argparse `action="append" nargs="+"` 会嵌套一层（每条 -i 贡献一个子列表）
    flat = [p for chunk in paths for p in (chunk if isinstance(chunk, list) else [chunk])]
    pool = {F.VIDEO: F.INPUT_VIDEO_EXT, F.AUDIO: F.INPUT_AUDIO_EXT, F.IMAGE: F.INPUT_IMAGE_EXT}[kind]
    return collect_files(flat, recursive=True, exts=pool)


def _run(args: argparse.Namespace) -> int:
    if not args.input:
        print("错误：请用 -i/--input 指定输入文件或目录（--help 查看用法）。", file=sys.stderr)
        return 2

    preset = P.find_preset(args.preset) if args.preset else None
    if args.preset and not preset:
        print(f"错误：找不到预设 “{args.preset}”（用 --list-presets 查看）。", file=sys.stderr)
        return 2

    # 1. 确定媒体类别
    kind = args.kind or (preset.kind if preset else None)
    if not kind:
        sample = _resolve_inputs(args.input, F.VIDEO) or _resolve_inputs(args.input, F.AUDIO) \
            or _resolve_inputs(args.input, F.IMAGE)
        kind = F.detect_kind(sample[0]) if sample else F.VIDEO

    # 2. 确定输出扩展名
    ext = (args.out_format or "").lower().lstrip(".")
    if not ext and preset:
        ext = preset.ext
    if not ext:
        print("错误：请用 -F/--out-format 指定输出格式，或使用 --preset。", file=sys.stderr)
        return 2
    if not F.find_format(ext, kind):
        print(f"错误：.{ext} 不是 {kind} 类别的输出格式（--list-formats 查看）。", file=sys.stderr)
        return 2

    # 3. 收集输入文件
    files = _resolve_inputs(args.input, kind)
    if not files:
        print(f"错误：在输入中没有找到 {kind} 类别的媒体文件。", file=sys.stderr)
        return 2
    print(f"共 {len(files)} 个文件待转换（{kind} / .{ext}）")

    params = _collect_params(args, kind, ext, preset)
    queue = ConversionQueue(workers=max(1, args.workers))

    def build_jobs() -> list[Job]:
        taken: set[str] = set()
        jobs: list[Job] = []
        for i, src in enumerate(files, 1):
            out_dir = args.out_dir or os.path.dirname(src)
            dst = build_output_path(src, out_dir, ext, args.pattern,
                                    overwrite=bool(params.get("overwrite", True)), index=i)
            dst = dedupe(dst, taken)
            jobs.append(Job(src=src, dst=dst, params=dict(params), kind=kind))
        return jobs

    jobs = build_jobs()

    if args.dry_run:
        for j in jobs:
            print(f"\n{j.src}\n  -> {j.dst}")
            try:
                print("  " + preview_command(j.src, j.dst, j.params))
            except Exception as exc:  # noqa: BLE001
                print(f"  （无法生成命令：{exc}）")
        return 0

    # 4. 执行
    for j in jobs:
        queue.add(j)

    def on_progress(job: Job) -> None:
        pct = int(job.progress * 100)
        print(f"\r[{pct:3d}%] {job.name}  {job.message}  ", end="", flush=True)

    queue.on_progress = on_progress
    queue.start()
    queue.wait()

    done = [j for j in jobs if j.status is Status.DONE]
    failed = [j for j in jobs if j.status is Status.FAILED]
    skipped = [j for j in jobs if j.status is Status.SKIPPED]
    canceled = [j for j in jobs if j.status is Status.CANCELED]
    print("\n" + "=" * 48)
    print(f"完成 {len(done)} 个，失败 {len(failed)} 个，跳过 {len(skipped)} 个，取消 {len(canceled)} 个")
    for j in failed:
        print(f"  ✗ {j.name}: {j.message}")
    for j in done:
        print(f"  ✓ {j.dst}")
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.refresh:
        invalidate_caches()
        print("ffmpeg 探测缓存已清除。")
        return 0
    if args.list_formats:
        _print_formats()
        return 0
    if args.list_presets:
        _print_presets()
        return 0
    if args.list_codecs:
        _print_codecs()
        return 0

    return _run(args)


if __name__ == "__main__":
    sys.exit(main())
