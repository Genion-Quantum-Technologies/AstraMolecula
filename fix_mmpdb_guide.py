#!/usr/bin/env python3
"""
mmpdb版本问题解决方案
基于检查结果，这里提供多种解决方案
"""

def     print("# 检查其他服务器的版本 (用于对比)")
    print("# 在工作的服务器上运行:")
    print('python -c "import mmpdblib; print(\'mmpdb version:\', getattr(mmpdblib, \'__version__\', \'unknown\'))"')
    print('python -c "from rdkit import __version__; print(\'rdkit version:\', __version__)"')t_analysis():
    """打印问题分析"""
    print("=== 问题分析 ===")
    print("根据检查结果，问题确认为：")
    print("1. 当前使用的是 mmpdb 2.1 版本")
    print("2. rdkit 版本是 2025.03.6 (较新版本)")
    print("3. 问题SMILES在fragment_algorithm.py第122行触发AssertionError")
    print("4. 这是mmpdb 2.1版本的一个已知bug")
    print()

def print_solutions():
    """打印解决方案"""
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
    
    print("方案4: 使用替代的片段化工具")
    print("如RDKit的BRICS算法替代mmpdb")
    print("优点: 避开mmpdb的bug")
    print("缺点: 片段化结果可能不同")
    print()

def print_commands():
    """打印具体执行命令"""
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
    print("python -c \"import mmpdblib; print('mmpdb version:', getattr(mmpdblib, '__version__', 'unknown'))\""
    print("python -c \"from rdkit import __version__; print('rdkit version:', __version__)\""
    print()

def print_version_comparison():
    """打印版本对比建议"""
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

def create_temp_fix():
    """创建临时修复方案的代码"""
    print("=== 方案3: 临时代码修复 ===")
    print()
    print("如果不想改变环境，可以修改fragment_processor.py:")
    print()
    
    temp_fix_code = '''
# 在fragment_processor.py中的fragmentize_molecule函数里添加try-catch:

def fragmentize_molecule(smiles_string: str, max_ratio: float = 0.8) -> pd.DataFrame:
    input_file = "temp_input.smi"
    output_file = "temp_output.fragments"

    try:
        with open(input_file, "w") as f:
            f.write(smiles_string + "\\t" + "Molecule" + "\\n")

        ret = os.system(f"mmpdb fragment {input_file} -o {output_file}")
        if ret != 0:
            # 如果mmpdb失败，使用BRICS替代
            print(f"mmpdb failed for {smiles_string}, using BRICS fallback")
            return fallback_brics_fragment(smiles_string, max_ratio)

        # ... 原有的fragment读取代码 ...
        
    except Exception as e:
        print(f"Fragment error: {e}")
        return fallback_brics_fragment(smiles_string, max_ratio)
    finally:
        # 清理文件
        for f in [input_file, output_file]:
            if Path(f).exists():
                os.remove(f)

def fallback_brics_fragment(smiles_string: str, max_ratio: float = 0.8) -> pd.DataFrame:
    """BRICS替代方案"""
    from rdkit.Chem import BRICS
    from rdkit import Chem
    
    mol = Chem.MolFromSmiles(smiles_string)
    if mol is None:
        return pd.DataFrame()  # 返回空DataFrame
    
    fragments = BRICS.BRICSDecompose(mol)
    frag_list = []
    
    for i, frag in enumerate(fragments):
        frag_list.append({
            'variable_smiles': frag,
            'constant_smiles': smiles_string,  # 简化处理
            'record_id': f'brics_{i}',
            'normalized_smiles': smiles_string,
            'attachment_order': [0]
        })
    
    return pd.DataFrame(frag_list)
'''
    print(temp_fix_code)
    print()

if __name__ == "__main__":
    print("mmpdb版本问题解决方案")
    print("=" * 50)
    
    print_analysis()
    print_solutions()
    print_commands()
    print_version_comparison()
    create_temp_fix()
    
    print("=" * 50)
    print("建议按照方案1优先尝试，如果还有问题再尝试其他方案。")
    print("记得在另一台正常工作的服务器上检查版本进行对比！")