"""MediaForge 命令行接口。

示例：
    mediaforge convert in.mkv -o out/ -f mp4 --video-codec libx265 --crf 24
    mediaforge convert ./photos -f webp --quality 80 --width 1920 -r
    mediaforge preset "MP3 320k 高音质" song.flac -o out/
    mediaforge info movie.mp4
    mediaforge list-formats
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading

from .core import formats as F
from .core import naming, presets
from .core.converter import ConversionQueue, Job, Status
from .core.ffprobe import available_encoders, ffmpeg_version, probe
from .core.naming import human_size, human_time

APP_NAME = "MediaForge"
VERSION = "1.0.0"


# --------------------------------------------------------------------------
def _add_param_args(parser: argparse.ArgumentParser) -> None:
    """把所有已知参数注册成 --xxx 命令行选项。"""
    # 与 convert 子命令自身选项冲突的键，改用带前缀的长选项
    reserved = {"preset": "--enc-preset", "format": "--out-format",
                "quiet": "--be-quiet", "pattern": "--name-pattern"}
    # 这些键在不同编码器下取值集合不同，放开为自由文本，避免误拒合法值
    free_text = {"preset", "profile", "level", "tune", "pix_fmt", "sample_fmt"}
    seen: set[str] = set()
    groups = (
        ("通用", F.GENERAL_PARAMS),
        ("视频处理", F.VIDEO_FILTER_PARAMS),
        ("音频处理", F.AUDIO_FILTER_PARAMS),
        ("图片", F.IMAGE_PARAMS),
    )
    codec_params: list[F.Param] = []
    for c in list(F.VIDEO_CODECS.values()) + list(F.AUDIO_CODECS.values()):
        codec_params.extend(c.params)

    for title, pool in groups + (("编码器", tuple(codec_params)),):
        g = parser.add_argument_group(f"{title}参数")
        for p in pool:
            if p.key in seen or p.key.startswith("_"):
                continue
            seen.add(p.key)
            flag = reserved.get(p.key) or ("--" + p.key.replace("_", "-"))
            help_text = p.help or p.label
            if p.type == "bool":
                g.add_argument(flag, dest=p.key, action="store_true", default=None,
                               help=f"{p.label}。{help_text}")
                g.add_argument("--no-" + p.key.replace("_", "-"), dest=p.key,
                               action="store_false", default=None,
                               help=argparse.SUPPRESS)
            elif p.type == "int":
                g.add_argument(flag, dest=p.key, type=int, default=None, help=help_text)
            elif p.type == "float":
                g.add_argument(flag, dest=p.key, type=float, default=None, help=help_text)
            elif p.type == "choice" and p.choices and p.key not in free_text:
                g.add_argument(flag, dest=p.key, choices=[c for c in p.choices if c],
                               default=None, help=help_text)
            else:
                g.add_argument(flag, dest=p.key, default=None, help=help_text)


def _collect_params(args: argparse.Namespace) -> dict:
    skip = {"command", "inputs", "outdir", "format", "recursive", "pattern",
            "workers", "dry_run", "use_preset", "json", "yes", "quiet",
            "func"}
    return {k: v for k, v in vars(args).items() if k not in skip and v is not None}


# --------------------------------------------------------------------------
def cmd_convert(args: argparse.Namespace) -> int:
    exts = None
    ext_out = (args.format or "").lower().lstrip(".")
    files = naming.collect_files(args.inputs, args.recursive, exts)
    if not files:
        print("未找到任何输入文件", file=sys.stderr)
        return 2

    params = _collect_params(args)
    if args.use_preset:
        p = presets.find_preset(args.use_preset)
        if not p:
            print(f"未知预设：{args.use_preset}", file=sys.stderr)
            return 2
        merged = dict(p.params)
        merged.update(params)
        params = merged
        ext_out = ext_out or p.ext

    if not ext_out:
        print("必须用 -f/--format 指定输出格式（或使用 --preset）", file=sys.stderr)
        return 2

    fmt = F.find_format(ext_out)
    if not fmt:
        print(f"不支持的输出格式：{ext_out}（用 list-formats 查看全部）", file=sys.stderr)
        return 2

    q = ConversionQueue(workers=args.workers)
    taken: set[str] = set()
    for i, src in enumerate(files, 1):
        dst = naming.build_output_path(src, args.outdir, ext_out, args.pattern,
                                       params.get("overwrite", True), i)
        dst = naming.dedupe(dst, taken)
        job = Job(src=src, dst=dst, params=dict(params), kind=fmt.kind)
        q.add(job)

    if args.dry_run:
        from .core.ffmpeg_builder import preview_command
        for job in q.jobs:
            print(f"\n# {job.src}\n#   -> {job.dst}")
            if job.kind != F.IMAGE:
                print(preview_command(job.src, job.dst, job.params))
            else:
                print(f"[Pillow] 图片转换，参数：{json.dumps(job.params, ensure_ascii=False)}")
        return 0

    total = len(q.jobs)
    lock = threading.Lock()
    state = {"done": 0}

    def on_done(job: Job) -> None:
        with lock:
            state["done"] += 1
            idx = state["done"]
        if args.quiet:
            return
        mark = {Status.DONE: "✔", Status.FAILED: "✘",
                Status.CANCELED: "－", Status.SKIPPED: "»"}.get(job.status, "?")
        extra = ""
        if job.status is Status.DONE:
            extra = f"  {human_size(job.out_size)}  用时 {human_time(job.elapsed)}"
        elif job.status is Status.FAILED:
            extra = f"  {job.message.splitlines()[0] if job.message else ''}"
        print(f"[{idx}/{total}] {mark} {os.path.basename(job.dst)}{extra}", flush=True)

    def on_progress(job: Job) -> None:
        if args.quiet or not sys.stdout.isatty():
            return
        bar = int(job.progress * 24)
        sys.stdout.write(
            f"\r  {job.name[:28]:<28} [{'█' * bar}{'·' * (24 - bar)}] "
            f"{job.progress * 100:5.1f}% {job.speed:>6}  ")
        sys.stdout.flush()

    q.on_job_done = on_done
    q.on_progress = on_progress
    q.start()
    for t in q._threads:  # noqa: SLF001
        t.join()
    if not args.quiet and sys.stdout.isatty():
        sys.stdout.write("\r" + " " * 78 + "\r")

    ok = sum(1 for j in q.jobs if j.status is Status.DONE)
    failed = [j for j in q.jobs if j.status is Status.FAILED]
    if not args.quiet:
        print(f"\n完成 {ok}/{total}，失败 {len(failed)}")
    for j in failed:
        print(f"  ✘ {j.name}: {j.message}", file=sys.stderr)
    return 1 if failed else 0


def cmd_info(args: argparse.Namespace) -> int:
    for path in args.inputs:
        info = probe(path)
        if args.json:
            print(json.dumps({
                "path": info.path, "duration": info.duration, "size": info.size,
                "bit_rate": info.bit_rate, "format": info.format_name,
                "streams": [vars(s) for s in info.streams],
            }, ensure_ascii=False, indent=2))
            continue
        print(f"\n文件：{info.path}")
        print(f"  容器：{info.format_name or '未知'}   大小：{human_size(info.size)}"
              f"   时长：{human_time(info.duration)}")
        if info.bit_rate:
            print(f"  总码率：{info.bit_rate // 1000} kbps")
        for s in info.streams:
            if s.codec_type == "video":
                print(f"  [视频 #{s.index}] {s.codec_name} {s.width}x{s.height} "
                      f"{s.fps:.3f}fps {s.pix_fmt}")
            elif s.codec_type == "audio":
                print(f"  [音频 #{s.index}] {s.codec_name} {s.sample_rate}Hz "
                      f"{s.channels}ch {s.bit_rate // 1000 if s.bit_rate else '?'}kbps "
                      f"{s.language}")
            else:
                print(f"  [{s.codec_type} #{s.index}] {s.codec_name} {s.language}")
    return 0


def cmd_list_formats(args: argparse.Namespace) -> int:
    for title, pool in (("视频", F.VIDEO_FORMATS), ("音频", F.AUDIO_FORMATS),
                        ("图片", F.IMAGE_FORMATS)):
        print(f"\n== {title}输出格式 ==")
        for f in pool:
            codecs = ""
            if f.video_codecs:
                codecs = "  视频编码: " + ", ".join(f.video_codecs[:5])
            if f.audio_codecs:
                codecs += "  音频编码: " + ", ".join(f.audio_codecs[:5])
            print(f"  .{f.ext:<6} {f.label}{codecs}")
    return 0


def cmd_list_presets(args: argparse.Namespace) -> int:
    for p in presets.all_presets(args.kind):
        tag = "内置" if p.builtin else "自定义"
        print(f"[{tag}][{p.kind}] {p.name}  -> .{p.ext}\n      {p.description}")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    print(f"{APP_NAME} {VERSION}")
    print(f"Python: {sys.version.split()[0]}")
    print(f"FFmpeg: {ffmpeg_version()}")
    encs = available_encoders()
    print(f"可用编码器数量: {len(encs)}")
    for group, pool in (("视频", F.VIDEO_CODECS), ("音频", F.AUDIO_CODECS)):
        avail = [e for e in pool if e in encs or e == "copy"]
        missing = [e for e in pool if e not in encs and e != "copy"]
        print(f"  {group}: 可用 {len(avail)} 个" +
              (f"，缺失 {', '.join(missing[:8])}{'…' if len(missing) > 8 else ''}"
               if missing else ""))
    try:
        from PIL import Image, features
        print(f"Pillow: {Image.__version__}  WebP:{features.check('webp')} "
              f"JPEG2000:{features.check('jpg_2000')}")
    except ImportError:
        print("Pillow: 未安装（图片功能不可用）")
    from .core.image_engine import HEIF_OK
    print(f"HEIF/AVIF 支持: {'是' if HEIF_OK else '否'}")
    return 0


# --------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="mediaforge",
        description=f"{APP_NAME} {VERSION} — 视频/音频/图片全格式转换工具",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("-V", "--version", action="version", version=f"{APP_NAME} {VERSION}")
    sub = p.add_subparsers(dest="command", required=True)

    c = sub.add_parser("convert", help="转换文件或目录",
                       formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    c.add_argument("inputs", nargs="+", help="输入文件或目录")
    c.add_argument("-o", "--outdir", default="", help="输出目录，默认与源文件同目录")
    c.add_argument("-f", "--format", default="", help="输出格式扩展名，如 mp4/mp3/webp")
    c.add_argument("-p", "--preset", dest="use_preset", default="", help="使用预设名称")
    c.add_argument("-r", "--recursive", action="store_true", help="递归处理子目录")
    c.add_argument("--pattern", default="{name}",
                   help="输出文件名模板，可用 {name}{ext}{date}{time}{index}{parent}")
    c.add_argument("-j", "--workers", type=int, default=2, help="并发任务数")
    c.add_argument("--dry-run", action="store_true", help="只打印命令不执行")
    c.add_argument("-q", "--quiet", action="store_true", help="安静模式")
    c.add_argument("--video-codec", dest="video_codec", default=None,
                   choices=sorted(F.VIDEO_CODECS), help="视频编码器")
    c.add_argument("--audio-codec", dest="audio_codec", default=None,
                   choices=sorted(F.AUDIO_CODECS) + ["none"], help="音频编码器")
    _add_param_args(c)
    c.set_defaults(func=cmd_convert)

    i = sub.add_parser("info", help="显示媒体信息")
    i.add_argument("inputs", nargs="+")
    i.add_argument("--json", action="store_true")
    i.set_defaults(func=cmd_info)

    lf = sub.add_parser("list-formats", help="列出所有支持的输出格式")
    lf.set_defaults(func=cmd_list_formats)

    lp = sub.add_parser("list-presets", help="列出所有预设")
    lp.add_argument("--kind", choices=[F.VIDEO, F.AUDIO, F.IMAGE])
    lp.set_defaults(func=cmd_list_presets)

    d = sub.add_parser("doctor", help="检查运行环境与依赖")
    d.set_defaults(func=cmd_doctor)

    g = sub.add_parser("gui", help="启动图形界面")
    g.set_defaults(func=lambda a: _launch_gui())
    return p


def _launch_gui() -> int:
    from .ui.main_window import run
    return run()


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args) or 0)
    except KeyboardInterrupt:
        print("\n已中断", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
