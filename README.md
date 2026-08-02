<div align="center">

<img src="app/resources/icon.png" width="120" alt="MediaForge">

# MediaForge

**全能的视频 / 音频 / 图片格式转换器 —— 支持全部可调参数**

图形界面 + 命令行 · 批量转换 · 一键打包成 Windows 安装程序

</div>

---

## 功能特性

- **视频**：MP4、MKV、WebM、MOV、AVI、FLV、WMV、TS、MPG、M4V、3GP、OGV、MXF、GIF、WebP 动图、APNG（16 种）
- **音频**：MP3、AAC、M4A、FLAC、WAV、OGG、Opus、WMA、AIFF、AC3、E-AC3、AMR、MKA、CAF、AU、MP2、Speex、TTA、WavPack（19 种）
- **图片**：JPEG、PNG、WebP、AVIF、HEIF、BMP、GIF、TIFF、TGA、ICO、JP2、DDS、EPS、PDF、PCX、PPM 等（20 种）
- **输入格式更宽**：可读取 100+ 种扩展名，包括 RMVB、M2TS、VOB、APE、DTS、PSD、SVG、HEIC 等
- **参数全开放**：编码器、码率控制（CRF/CBR/VBR/CQ/无损）、两遍编码、预设、Profile/Level、像素格式、GOP、B 帧、参考帧…… 视频侧 60+ 项参数全部可调
- **画面处理**：缩放（8 种算法）、裁剪、填充、旋转翻转、去隔行、降噪、锐化、亮度/对比度/饱和度/伽马、自定义滤镜链
- **声音处理**：响度归一化（EBU R128）、变速、变调、淡入淡出、音量、重采样、声道数
- **图片参数**：质量、无损、渐进式、色度抽样、压缩级别、位深、DPI、ICC、EXIF、旋转、滤镜等 30 项
- **硬件加速**：NVIDIA NVENC、Intel QuickSync、AMD AMF
- **批量转换**：拖放文件/文件夹、递归扫描、并发处理、命名模板、实时进度与速度
- **28 个内置预设**：从「MP4 通用高质量」到「播客响度标准化」「Windows 图标 ICO」
- **专家模式**：界面实时显示将要执行的 ffmpeg 命令，可追加任意自定义参数

## 安装

### 方式一：下载安装程序（推荐）

前往 [Releases](../../releases) 下载最新的 `MediaForge-*-Setup.exe`，双击安装即可。
安装程序已内置 FFmpeg，**无需另外安装任何依赖**。

安装选项包括：桌面快捷方式、加入系统 PATH、文件右键菜单「用 MediaForge 转换」。

> 尚未发布 Release 时，可到 [Actions](../../actions) 页面下载最新构建的
> `MediaForge-Windows-Setup-*` 产物。

### 方式二：从源码运行

```bash
git clone <本仓库地址>
cd MediaForge
pip install -r requirements.txt
python main.py            # 启动图形界面
```

音视频转换需要系统中有 FFmpeg（`ffmpeg` 在 PATH 中，或放到程序目录的 `bin/` 下）。
图片转换不依赖 FFmpeg。

## 使用

### 图形界面

```bash
python main.py
```

把文件或文件夹拖进列表 → 选择媒体类型和输出格式 → 调整参数（或直接选预设）→ 点「开始转换」。

### 命令行

```bash
# 转成 H.265 MKV，指定质量与分辨率
mediaforge convert input.mp4 -o out/ -f mkv --video-codec libx265 --crf 24 --width 1920

# 批量把整个目录的图片转成 WebP
mediaforge convert ./photos -r -f webp --quality 80 --width 1920

# 用预设提取高质量 MP3
mediaforge convert video.mkv -o out/ -p "MP3 320k 高音质"

# 只看将要执行的命令，不真正转换
mediaforge convert in.mov -f mp4 --dry-run

# 查看媒体信息 / 全部格式 / 全部预设 / 环境自检
mediaforge info movie.mp4
mediaforge list-formats
mediaforge list-presets
mediaforge doctor
```

从源码运行时把 `mediaforge` 换成 `python main.py` 即可。
`--help` 会列出全部可用参数（按编码器分组）。

常用参数速查：

| 参数 | 说明 |
|---|---|
| `-f, --format` | 输出格式扩展名 |
| `-o, --outdir` | 输出目录 |
| `-p, --preset` | 使用内置/自定义预设 |
| `-r, --recursive` | 递归处理子目录 |
| `-j, --workers` | 并发任务数 |
| `--pattern` | 命名模板，支持 `{name} {ext} {date} {time} {index} {parent}` |
| `--crf` / `--bitrate` | 恒定质量 / 目标码率 |
| `--enc-preset` | 编码速度预设（如 `slow`、`ultrafast`） |
| `--two-pass` | 两遍编码 |
| `--extra-args` | 追加任意原生 ffmpeg 参数 |

## 自行构建安装程序

### 在 Windows 上本地构建

需要 Python 3.10+ 与 [Inno Setup 6](https://jrsoftware.org/isdl.php)：

```bat
packaging\build_windows.bat
```

产物：`dist_installer\MediaForge-<version>-Setup.exe`（安装程序）与 `dist\MediaForge\`（免安装版）。
版本号默认 `0.0.0-dev`；设置环境变量 `APP_VERSION=1.2.0` 可覆盖。

### 用 GitHub Actions 构建 / 发布

**完全不懂技术？** 请看 [《如何生成安装程序》](如何生成安装程序.md)。

工作流已就绪：`.github/workflows/build-windows.yml`。

| 触发方式 | 行为 |
|---|---|
| Actions 页面点 `Run workflow` | 只构建 + 上传 Artifact（不发版） |
| `git tag v1.2.0 && git push origin v1.2.0` | 构建并自动创建 GitHub Release |

版本号**唯一来源**是 git tag（`v1.2.0` → 安装包 `MediaForge-1.2.0-Setup.exe`），
程序内版本与 PE 版本资源也会同步写入。`v1.2.0-beta.1` 这类带 `-` 的 tag 会自动标为 Pre-release。

实际构建逻辑在 `packaging/ci/build.ps1`，本地 Windows 也可直接运行它。

## 项目结构

```
app/
  core/
    formats.py        格式、编解码器与全部参数的目录定义
    ffprobe.py        ffmpeg/ffprobe 定位与媒体信息探测
    ffmpeg_builder.py 参数 → ffmpeg 命令行的翻译
    image_engine.py   基于 Pillow 的图片转换引擎
    converter.py      任务模型、进度解析、并发队列
    presets.py        内置与用户预设
    naming.py         输出命名与文件收集
  ui/
    main_window.py    主窗口
    widgets.py        参数表单控件（按目录自动生成）
  cli.py              命令行接口
packaging/            PyInstaller spec、Inno Setup 脚本、本地构建批处理
tests/                117 项测试（单元 + 真实转换端到端）
```

参数定义集中在 `app/core/formats.py`，界面与命令行都从这里读取——
新增一个参数，GUI 表单和 CLI 选项会自动出现。

## 测试

```bash
pytest tests/ -v
```

包含 79 项单元测试（命令构建、滤镜链、命名逻辑）与 38 项端到端测试
（真实调用 ffmpeg / Pillow 生成并校验文件）。没装 ffmpeg 时相关用例会自动跳过。

## 许可

GPL-3.0。本程序使用 FFmpeg 与 Pillow，版权归各自作者所有。
