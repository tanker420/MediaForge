"""MediaForge 入口。

默认启动图形界面（不显示任何命令行窗口）；
传入 --cli 或设置环境变量 MEDIAFORGE_CLI=1 可切换到命令行批量模式。
"""
from __future__ import annotations

import os
import sys


def main() -> int:
    if os.environ.get("MEDIAFORGE_CLI") == "1":
        from app.cli import main as cli_main
        return cli_main()
    if "--cli" in sys.argv:
        from app.cli import main as cli_main
        # 剥离 --cli，避免传递给 argparse
        return cli_main([a for a in sys.argv[1:] if a != "--cli"])
    from app.ui.main_window import run
    return run()


if __name__ == "__main__":
    sys.exit(main())
