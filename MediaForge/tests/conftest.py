"""pytest 公共配置：保证 `import app` 可用。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
