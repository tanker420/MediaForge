"""MediaForge - 一站式媒体格式转换器。"""

# 单一版本来源：所有运行时模块、CLI、GUI、构建脚本都从这里读取。
# 打包产物（Windows 文件属性、Inno Setup 版本号、spec 元数据）由
# packaging/ci/build.ps1 用 -Version 参数动态注入，保持与发布版本一致。
__version__ = "1.1.0"

__all__ = ["__version__"]