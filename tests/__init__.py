"""
Tests package
"""
import sys
from pathlib import Path

# 确保 src 目录在 Python 路径中
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))
