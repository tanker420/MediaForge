"""MediaForge 启动入口。

不带参数 → 打开图形界面；带参数 → 走命令行。
"""
from __future__ import annotations

import multiprocessing
import sys


def main() -> int:
    multiprocessing.freeze_support()   # PyInstaller 冻结后必需
    if len(sys.argv) > 1:
        from app.cli import main as cli_main
        return cli_main()
    from app.ui.main_window import run
    return run()


if __name__ == "__main__":
    sys.exit(main())
