#!/usr/bin/env python
"""
AstraMolecula 启动脚本
兼容旧的 main.py 入口
"""

import sys
from pathlib import Path

# 添加 src 目录到 Python 路径
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

# 导入并运行应用
from astra_molecula.app import app, main

if __name__ == "__main__":
    main()
