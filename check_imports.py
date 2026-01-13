#!/usr/bin/env python3
"""
检查项目中的导入问题
"""
import sys
import os

# 添加 src 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

print("开始检查导入...")
errors = []

# 测试各个模块的导入
test_imports = [
    "astra_molecula",
    "astra_molecula.utils",
    "astra_molecula.utils.log",
    "astra_molecula.ml.models",
    "astra_molecula.ml.preprocess",
    "astra_molecula.db.services",
    "astra_molecula.db.repositories",
    "astra_molecula.schemas",
]

for module in test_imports:
    try:
        __import__(module)
        print(f"✓ {module}")
    except Exception as e:
        error_msg = f"✗ {module}: {type(e).__name__}: {str(e)}"
        print(error_msg)
        errors.append(error_msg)

if errors:
    print(f"\n发现 {len(errors)} 个导入错误:")
    for err in errors:
        print(f"  {err}")
    sys.exit(1)
else:
    print("\n所有导入检查通过!")
    sys.exit(0)
