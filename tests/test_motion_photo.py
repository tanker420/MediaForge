"""Motion Photo（Live Photo）与动图互转相关回归测试（纯字符串，无需 ffmpeg）。"""
from __future__ import annotations

from app.core import formats as F
from app.core import motion_photo as MP
from app.core import presets as P


# ---------------- 格式识别 ----------------
def test_is_motion_photo():
    assert F.is_motion_photo("IMG_0001.MP.jpg")
    assert F.is_motion_photo("a.mp.jpeg")
    assert F.is_motion_photo("b.mpjpeg")
    assert not F.is_motion_photo("c.jpg")
    assert not F.is_motion_photo("d.mp4")


def test_input_ext_motion_photo():
    assert F.input_ext("a.MP.jpg") == "mp.jpg"
    assert F.input_ext("b.png") == "png"
    assert F.input_ext("c.mp4") == "mp4"


def test_detect_kind_motion_photo_is_video():
    assert F.detect_kind("IMG_0001.MP.jpg") == F.VIDEO


def test_motion_photo_format_registered():
    fmt = F.find_format("mp.jpg", F.VIDEO)
    assert fmt is not None
    assert fmt.kind == F.VIDEO
    assert "libx264" in fmt.video_codecs
    assert "mp.jpg" in F.INPUT_VIDEO_EXT


def test_animated_interchange_formats_present():
    # GIF / WebP / APNG / Live Photo 均作为视频输出格式存在，支持互转
    for ext in ("gif", "webp", "apng", "mp.jpg"):
        assert F.find_format(ext, F.VIDEO).ext == ext


# ---------------- 预设 ----------------
def test_motion_photo_and_animated_presets():
    names = {p.name for p in P.all_presets(F.VIDEO)}
    assert "Live Photo 动态照片" in names
    assert "WebP 动图" in names
    assert "APNG 动图" in names
    assert "GIF 动图" in names


# ---------------- XMP 构建 ----------------
def test_build_xmp_contains_required_tags():
    xmp = MP.build_xmp(12345, 1000000)
    assert 'Camera:MotionPhoto="1"' in xmp
    assert 'Camera:MotionPhotoVersion="1"' in xmp
    assert 'Camera:MotionPhotoPresentationTimestampUs="1000000"' in xmp
    assert 'Item:Mime="video/mp4"' in xmp
    assert 'Item:Semantic="MotionPhoto"' in xmp
    assert 'Item:Length="12345"' in xmp
    assert 'Item:Mime="image/jpeg"' in xmp


def test_make_xmp_segment_and_inject():
    seg = MP.make_xmp_segment(MP.build_xmp(100, 0))
    assert seg[:2] == b"\xff\xe1"
    # APP1 段长度字段 = 标识符 + XMP 字节 + 2
    ident = b"http://ns.adobe.com/xap/1.0/\x00"
    import struct
    length = struct.unpack(">H", seg[2:4])[0]
    assert length == len(ident) + len(seg) - 4 - len(ident) + 2

    jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01" + b"\xff\xd9"
    out = MP.inject_xmp(jpeg, seg)
    assert out[:2] == b"\xff\xd8"
    assert out[2:4] == b"\xff\xe1"          # XMP 紧跟 SOI
    assert ident in out
    assert out.endswith(b"\xff\xd9")        # JPEG 仍完整
