# config.py
from pathlib import Path
import sys

# 如果 config.py 在 your-project 根下，这里就是 your-project 目录
ROOT = Path(__file__).resolve().parent
VINA_DIR = ROOT / "Vina"
if str(VINA_DIR) not in sys.path:
    sys.path.insert(0, str(VINA_DIR))