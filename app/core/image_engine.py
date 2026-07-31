"""基于 Pillow 的图片转换引擎。"""
from __future__ import annotations

import os
from typing import Any

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

try:  # 可选：AVIF / HEIF 支持
    import pillow_heif  # type: ignore

    pillow_heif.register_heif_opener()
    try:
        pillow_heif.register_avif_opener()
    except AttributeError:
        pass
    HEIF_OK = True
except ImportError:  # pragma: no cover
    HEIF_OK = False

Image.MAX_IMAGE_PIXELS = None

RESAMPLE = {
    "nearest": Image.Resampling.NEAREST,
    "box": Image.Resampling.BOX,
    "bilinear": Image.Resampling.BILINEAR,
    "hamming": Image.Resampling.HAMMING,
    "bicubic": Image.Resampling.BICUBIC,
    "lanczos": Image.Resampling.LANCZOS,
}

# 扩展名 -> Pillow 保存格式
SAVE_FORMAT = {
    "jpg": "JPEG", "jpeg": "JPEG", "jfif": "JPEG",
    "png": "PNG", "webp": "WEBP", "gif": "GIF", "bmp": "BMP",
    "tiff": "TIFF", "tif": "TIFF", "tga": "TGA", "ico": "ICO",
    "ppm": "PPM", "pgm": "PPM", "pbm": "PPM", "pcx": "PCX",
    "jp2": "JPEG2000", "j2k": "JPEG2000", "dds": "DDS", "eps": "EPS",
    "pdf": "PDF", "im": "IM", "sgi": "SGI", "msp": "MSP", "xbm": "XBM",
    "avif": "AVIF", "heif": "HEIF", "heic": "HEIF", "qoi": "QOI",
}

NO_ALPHA = {"JPEG", "PDF", "EPS", "PPM", "PCX", "DDS", "SGI", "MSP", "XBM", "JPEG2000"}


def _i(p: dict[str, Any], k: str, d: int = 0) -> int:
    try:
        return int(float(p.get(k, d)))
    except (TypeError, ValueError):
        return d


def _f(p: dict[str, Any], k: str, d: float = 0.0) -> float:
    try:
        return float(p.get(k, d))
    except (TypeError, ValueError):
        return d


def _b(p: dict[str, Any], k: str, d: bool = False) -> bool:
    v = p.get(k, d)
    if isinstance(v, str):
        return v.lower() in ("1", "true", "yes", "on")
    return bool(v)


def _s(p: dict[str, Any], k: str, d: str = "") -> str:
    v = p.get(k, d)
    return "" if v is None else str(v).strip()


def _flatten(img: Image.Image, background: str) -> Image.Image:
    """把透明通道合成到背景色上。"""
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        try:
            bg = Image.new("RGBA", img.size, background or "#FFFFFF")
        except ValueError:
            bg = Image.new("RGBA", img.size, "#FFFFFF")
        img = Image.alpha_composite(bg, img)
    return img.convert("RGB")


def _apply_geometry(img: Image.Image, p: dict[str, Any]) -> Image.Image:
    if _b(p, "auto_orient", True):
        try:
            img = ImageOps.exif_transpose(img)
        except Exception:  # noqa: BLE001
            pass

    w, h = _i(p, "width"), _i(p, "height")
    if w or h:
        resample = RESAMPLE.get(_s(p, "resample", "lanczos"), Image.Resampling.LANCZOS)
        ow, oh = img.size
        if _b(p, "keep_aspect", True):
            if w and h:
                img = ImageOps.contain(img, (w, h), resample)
            elif w:
                img = img.resize((w, max(1, round(oh * w / ow))), resample)
            else:
                img = img.resize((max(1, round(ow * h / oh)), h), resample)
        else:
            img = img.resize((w or ow, h or oh), resample)

    rot = _s(p, "rotate", "0")
    if rot in ("90", "180", "270"):
        img = img.rotate(-int(rot), expand=True)
    if _b(p, "hflip"):
        img = ImageOps.mirror(img)
    if _b(p, "vflip"):
        img = ImageOps.flip(img)
    return img


def _apply_adjustments(img: Image.Image, p: dict[str, Any]) -> Image.Image:
    if _b(p, "grayscale"):
        img = ImageOps.grayscale(img).convert("RGB") if img.mode != "L" else img

    for key, cls in (("brightness", ImageEnhance.Brightness),
                     ("contrast", ImageEnhance.Contrast),
                     ("saturation", ImageEnhance.Color),
                     ("sharpness", ImageEnhance.Sharpness)):
        val = _f(p, key, 1.0)
        if abs(val - 1.0) > 1e-6:
            try:
                img = cls(img).enhance(val)
            except ValueError:
                pass

    blur = _f(p, "blur", 0)
    if blur > 0:
        img = img.filter(ImageFilter.GaussianBlur(blur))
    return img


def _save_options(fmt: str, p: dict[str, Any], img: Image.Image) -> dict[str, Any]:
    opts: dict[str, Any] = {}
    quality = _i(p, "quality", 90)
    lossless = _b(p, "lossless")

    if fmt == "JPEG":
        opts.update(quality=quality, optimize=_b(p, "optimize", True),
                    progressive=_b(p, "progressive"))
        sub = _s(p, "subsampling", "auto")
        if sub != "auto":
            opts["subsampling"] = {"4:4:4": 0, "4:2:2": 1, "4:2:0": 2}.get(sub, 0)
    elif fmt == "PNG":
        opts.update(optimize=_b(p, "optimize", True),
                    compress_level=_i(p, "png_compress_level", 6))
    elif fmt == "WEBP":
        opts.update(quality=quality, method=_i(p, "webp_method", 4), lossless=lossless)
    elif fmt == "AVIF":
        opts.update(quality=quality, speed=_i(p, "avif_speed", 6))
        if lossless:
            opts["quality"] = 100
    elif fmt == "HEIF":
        opts.update(quality=100 if lossless else quality)
    elif fmt == "TIFF":
        comp = _s(p, "tiff_compression", "tiff_deflate")
        opts["compression"] = None if comp == "none" else comp
        if comp == "jpeg":
            opts["quality"] = quality
    elif fmt == "JPEG2000":
        opts["quality_mode"] = "rates"
        opts["irreversible"] = not lossless
    elif fmt == "GIF":
        opts["optimize"] = _b(p, "optimize", True)
    elif fmt == "ICO":
        sizes = []
        for chunk in _s(p, "ico_sizes", "16,32,48,64,128,256").split(","):
            chunk = chunk.strip()
            if chunk.isdigit():
                n = int(chunk)
                if n <= max(img.size):
                    sizes.append((n, n))
        opts["sizes"] = sizes or [(256, 256)]

    dpi = _i(p, "dpi", 0)
    if dpi > 0 and fmt in ("JPEG", "PNG", "TIFF", "PDF"):
        opts["dpi"] = (dpi, dpi)

    if not _b(p, "strip_metadata") and _b(p, "keep_icc", True):
        icc = img.info.get("icc_profile")
        if icc and fmt in ("JPEG", "PNG", "WEBP", "TIFF", "AVIF"):
            opts["icc_profile"] = icc
    if not _b(p, "strip_metadata") and fmt == "JPEG":
        exif = img.info.get("exif")
        if exif:
            opts["exif"] = exif
    return opts


def convert_image(src: str, dst: str, params: dict[str, Any]) -> str:
    """执行一次图片转换，返回输出路径。"""
    if not _b(params, "overwrite", True) and os.path.exists(dst):
        raise FileExistsError(f"目标文件已存在：{dst}")

    ext = dst.rsplit(".", 1)[-1].lower()
    fmt = SAVE_FORMAT.get(ext)
    if not fmt:
        raise ValueError(f"不支持的图片输出格式：.{ext}")
    if fmt in ("AVIF", "HEIF") and not HEIF_OK and fmt == "HEIF":
        raise RuntimeError("当前环境缺少 HEIF 支持（pillow-heif 未安装）")

    with Image.open(src) as im:
        n_frames = getattr(im, "n_frames", 1)
        animated = n_frames > 1 and fmt in ("GIF", "WEBP", "PNG", "TIFF")

        if animated:
            return _convert_animated(im, dst, fmt, params, n_frames)

        img = im.convert(im.mode) if im.mode == "P" and fmt == "GIF" else im.copy()
        img.info = dict(im.info)

    img = _apply_geometry(img, params)
    img = _apply_adjustments(img, params)

    mode = _s(params, "color_mode")
    if mode:
        img = img.convert(mode)
    elif fmt in NO_ALPHA:
        img = _flatten(img, _s(params, "background", "#FFFFFF"))
    elif fmt == "GIF" and img.mode not in ("P", "L"):
        img = img.convert("P", palette=Image.Palette.ADAPTIVE)

    depth = _s(params, "bit_depth")
    if depth and img.mode != "P":
        img = img.convert("P", palette=Image.Palette.ADAPTIVE, colors=2 ** int(depth))

    if fmt == "ICO" and img.mode != "RGBA":
        img = img.convert("RGBA")

    os.makedirs(os.path.dirname(os.path.abspath(dst)) or ".", exist_ok=True)
    img.save(dst, fmt, **_save_options(fmt, params, img))
    return dst


def _convert_animated(im: Image.Image, dst: str, fmt: str,
                      params: dict[str, Any], n_frames: int) -> str:
    """处理 GIF / 动态 WebP / APNG 多帧图。"""
    from PIL import ImageSequence

    frames: list[Image.Image] = []
    durations: list[int] = []
    for frame in ImageSequence.Iterator(im):
        f = frame.convert("RGBA")
        f = _apply_geometry(f, params)
        f = _apply_adjustments(f, params)
        if fmt in NO_ALPHA:
            f = _flatten(f, _s(params, "background", "#FFFFFF"))
        frames.append(f)
        durations.append(frame.info.get("duration", 100))

    first, rest = frames[0], frames[1:]
    if fmt == "GIF":
        first = first.convert("P", palette=Image.Palette.ADAPTIVE)
        rest = [f.convert("P", palette=Image.Palette.ADAPTIVE) for f in rest]

    os.makedirs(os.path.dirname(os.path.abspath(dst)) or ".", exist_ok=True)
    opts = _save_options(fmt, params, first)
    opts.pop("exif", None)
    first.save(dst, fmt, save_all=True, append_images=rest,
               duration=durations, loop=_i(params, "gif_loop", 0), **opts)
    return dst


def read_size(src: str) -> tuple[int, int]:
    try:
        with Image.open(src) as im:
            return im.size
    except Exception:  # noqa: BLE001
        return (0, 0)
