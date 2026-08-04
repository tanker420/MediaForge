# MediaForge 全能媒体格式转换器

> 一个免费开源的「一站式」媒体格式转换工具：视频 / 音频 / 图片，共 **55 种输出格式**。
> 现代化图形界面，拖拽即转，无需任何命令行操作。

[![License: GPL-3.0](https://img.shields.io/badge/License-GPL--3.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)]()

---

## ✨ 功能特性

- **三合一转换**：视频、音频、图片三类媒体，一个窗口搞定
- **55 种输出格式**：MP4/MKV/WebM/AV1、MP3/FLAC/AAC/Opus、PNG/WebP/AVIF/ICO…
- **智能类别识别**：把文件拖进窗口，自动切换到对应的转换模式
- **一键预设**：内置 28 个常用预设（B 站上传、手机 720p、无损归档、播客响度标准化…）
- **批量处理**：多文件并行转换，实时进度，完成后一键打开输出文件夹
- **硬核参数齐全**：分辨率、帧率、码率、CRF 质量、裁剪、旋转、降噪、音量、淡入淡出、响度归一化、变速变调… 全部图形化调节
- **硬件加速**：支持 NVIDIA NVENC / Intel QSV / AMD AMF 显卡编码
- **图片无损/有损**：质量、压缩级别、位深、ICC 色彩、EXIF 摆正、多尺寸 ICO、动图转 GIF/WebP
- **无命令行**：纯 GUI 操作，转换过程不弹出任何黑窗口

## 📦 安装

### 方式一：Windows 安装包（推荐）

从 [Releases](https://github.com/tanker420/MediaForge/releases) 下载 `MediaForge-x.x.x-Setup.exe`，一路「下一步」即可。
安装程序为中文界面，可选的右键菜单「用 MediaForge 转换」让操作更顺手。

### 方式二：源码运行

需要 Python 3.10+，并安装 [FFmpeg](https://ffmpeg.org/download.html)（加入 PATH 即可，视频/音频转换必需；纯图片转换无需）。

```bash
git clone https://github.com/tanker420/MediaForge.git
cd MediaForge
pip install -r requirements.txt
python main.py          # 启动图形界面
```

## 🎮 使用说明

1. 点击「＋ 添加文件」或直接把文件/文件夹拖进窗口
2. 选择输出格式（可先套用一个预设）
3. 按需微调右侧参数，设置输出目录与命名规则
4. 点击「开始转换」，完成后点击「打开输出文件夹」

> 提示：顶部右上角显示 FFmpeg 状态。安装或更换 FFmpeg 后点击它即可重新检测，无需重启程序。

## 🖥 命令行模式（可选）

日常使用无需命令行；为脚本化/批量处理场景保留了 CLI 入口：

```bash
python main.py --cli -i 视频.mp4 -F mkv -p video_codec=copy -p audio_codec=copy
python main.py --cli -i ./素材目录 -F mp3 -p audio_bitrate=192k --workers 4
python main.py --cli --list-formats
```

## 🔧 自行打包 Windows 安装包

见 [如何生成安装程序.md](如何生成安装程序.md)。支持两种方式：

- **本地一键打包**：安装 Python 与 Inno Setup 后运行 `packaging\build_windows.bat`
- **GitHub Actions**：推送 `v*` 标签自动构建并发布 Release

## 🏗 技术架构

```
main.py                入口（默认 GUI，--cli 切换命令行）
└── app/
    ├── cli.py         命令行模式（与 GUI 共用参数目录）
    ├── core/
    │   ├── formats.py          ★ 单一事实来源：55 种格式 + 编码器 + 参数目录
    │   ├── presets.py          内置/用户预设
    │   ├── naming.py           输出路径与命名规则
    │   ├── ffprobe.py          ffmpeg 定位 / 媒体信息探测 / 编码器查询
    │   ├── ffmpeg_builder.py   参数 → ffmpeg 命令行翻译
    │   ├── image_engine.py     图片转换引擎（Pillow，支持取消）
    │   └── converter.py        任务模型 + 并发队列 + 进度回调
    └── ui/
        ├── theme.py            现代化浅色主题（QSS）
        ├── widgets.py          分段选择器 / 自动参数表单 / 文件表格
        └── main_window.py      主窗口
```

**设计要点**：UI 与 CLI 共用 `formats.py` 参数目录——新增格式或参数时，界面控件自动生成，两端永不脱节。

## 📄 许可证

[GPL-3.0](LICENSE) © MediaForge
