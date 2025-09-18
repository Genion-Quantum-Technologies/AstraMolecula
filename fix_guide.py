#!/usr/bin/env python3
"""
mmpdb版本问题解决方案
"""

print("=== 问题分析 ===")
print("根据检查结果，问题确认为：")
print("1. 当前使用的是 mmpdb 2.1 版本")
print("2. rdkit 版本是 2025.03.6 (较新版本)")
print("3. 问题SMILES在fragment_algorithm.py第122行触发AssertionError")
print("4. 这是mmpdb 2.1版本的一个已知bug")
print()

print("=== 解决方案 ===")
print()

print("方案1: 降级mmpdb到2.0版本 (推荐)")
print("命令:")
print("  micromamba activate AstraMolecula")
print("  pip uninstall mmpdb")
print("  pip install mmpdb==2.0")
print("优点: 2.0版本相对稳定，bug较少")
print("缺点: 可能缺少2.1版本的新功能")
print()

print("方案2: 升级到最新版本")
print("命令:")
print("  micromamba activate AstraMolecula")
print("  pip install --upgrade mmpdb")
print("优点: 获得最新功能和bug修复")
print("缺点: 可能引入新的不兼容问题")
print()

print("方案3: 修改代码添加错误处理 (临时方案)")
print("在fragment_processor.py中添加try-catch处理")
print("优点: 不改变环境，快速修复")
print("缺点: 治标不治本，某些分子仍无法处理")
print()

print("=== 立即执行的修复命令 ===")
print()

print("# 方案1: 降级到mmpdb 2.0 (建议先尝试)")
print("micromamba activate AstraMolecula")
print("pip uninstall mmpdb -y")
print("pip install mmpdb==2.0")
print("python check_versions.py  # 重新检查")
print()

print("# 如果方案1不行，尝试方案2: 升级到最新版")
print("micromamba activate AstraMolecula")
print("pip install --upgrade mmpdb")
print("python check_versions.py  # 重新检查")
print()

print("# 检查其他服务器的版本 (用于对比)")
print("# 在工作的服务器上运行:")
print('python -c "import mmpdblib; print(mmpdblib.__version__)"')
print('python -c "from rdkit import __version__; print(__version__)"')
print()

print("=== 版本对比建议 ===")
print()
print("如果你有另一台正常工作的服务器，建议:")
print("1. 在那台服务器上运行check_versions.py")
print("2. 对比两台服务器的版本差异")
print("3. 将问题服务器的版本调整为与工作服务器一致")
print()
print("常见的工作组合:")
print("- mmpdb 2.0 + rdkit 2023.x")
print("- mmpdb 2.1 + rdkit 2023.x (某些分子有问题)")
print("- mmpdb 3.x + rdkit 2024.x+ (如果有更新版本)")
print()

print("=" * 50)
print("建议按照方案1优先尝试，如果还有问题再尝试其他方案。")
print("记得在另一台正常工作的服务器上检查版本进行对比！")