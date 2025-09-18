#!/usr/bin/env python3
"""
检查mmpdb和相关依赖的详细版本信息
"""
import sys
import platform
import subprocess

def run_command(cmd):
    """执行命令并返回结果"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except Exception as e:
        return "", str(e), 1

def check_python_packages():
    """检查Python包版本"""
    print("=== Python环境信息 ===")
    print(f"Python版本: {sys.version}")
    print(f"操作系统: {platform.system()} {platform.release()}")
    print(f"架构: {platform.machine()}")
    print()
    
    print("=== 关键包版本检查 ===")
    
    packages = [
        'mmpdblib',
        'rdkit',
        'pandas',
        'numpy'
    ]
    
    for package in packages:
        try:
            if package == 'mmpdblib':
                import mmpdblib
                version = getattr(mmpdblib, '__version__', 'unknown')
                print(f"{package}: {version}")
                
                # 检查mmpdblib的详细信息
                print(f"  - 安装路径: {mmpdblib.__file__}")
                
                # 检查fragment_algorithm模块
                try:
                    from mmpdblib import fragment_algorithm
                    print(f"  - fragment_algorithm可用: ✓")
                except ImportError as e:
                    print(f"  - fragment_algorithm导入失败: {e}")
                    
            elif package == 'rdkit':
                from rdkit import Chem, __version__
                print(f"{package}: {__version__}")
                print(f"  - 安装路径: {Chem.__file__}")
                
            else:
                module = __import__(package)
                version = getattr(module, '__version__', 'unknown')
                print(f"{package}: {version}")
                
        except ImportError as e:
            print(f"{package}: 未安装 ({e})")
        except Exception as e:
            print(f"{package}: 检查失败 ({e})")
    
    print()

def check_mmpdb_command():
    """检查mmpdb命令行工具"""
    print("=== mmpdb命令行工具检查 ===")
    
    stdout, stderr, returncode = run_command("mmpdb --version")
    if returncode == 0:
        print(f"mmpdb命令版本: {stdout}")
    else:
        print(f"mmpdb命令不可用: {stderr}")
    
    # 检查mmpdb help
    stdout, stderr, returncode = run_command("mmpdb --help")
    if returncode == 0:
        print("mmpdb帮助信息可用: ✓")
    else:
        print(f"mmpdb帮助信息不可用: {stderr}")
    
    print()

def test_problematic_smiles():
    """测试问题SMILES"""
    print("=== 测试问题SMILES ===")
    problematic_smiles = "CC(C)OC(=O)Nc1nc2cc(CCN3CCN(c4nncc5scc(C)c45)CC3)sc2c(C#N)c1C"
    
    try:
        from rdkit import Chem
        mol = Chem.MolFromSmiles(problematic_smiles)
        if mol:
            print(f"RDKit可以解析SMILES: ✓")
            print(f"原子数: {mol.GetNumAtoms()}")
            print(f"环数: {mol.GetRingInfo().NumRings()}")
        else:
            print("RDKit无法解析SMILES: ✗")
    except Exception as e:
        print(f"RDKit测试失败: {e}")
    
    # 测试mmpdb fragment
    print("\n测试mmpdb fragment功能:")
    
    # 创建临时文件
    temp_file = "/tmp/test_smiles.smi"
    output_file = "/tmp/test_output.fragments"
    
    try:
        with open(temp_file, 'w') as f:
            f.write(f"{problematic_smiles}\ttest_molecule\n")
        
        stdout, stderr, returncode = run_command(f"mmpdb fragment {temp_file} -o {output_file}")
        
        if returncode == 0:
            print("mmpdb fragment执行成功: ✓")
            # 检查输出文件
            try:
                with open(output_file, 'r') as f:
                    content = f.read()
                    print(f"输出文件大小: {len(content)} 字符")
            except:
                print("无法读取输出文件")
        else:
            print(f"mmpdb fragment执行失败: {stderr}")
            print(f"返回码: {returncode}")
            
    except Exception as e:
        print(f"测试过程出错: {e}")
    finally:
        # 清理临时文件
        import os
        for f in [temp_file, output_file]:
            if os.path.exists(f):
                os.remove(f)

def check_known_issues():
    """检查已知问题"""
    print("=== 已知问题检查 ===")
    
    try:
        import mmpdblib
        version = getattr(mmpdblib, '__version__', 'unknown')
        
        # mmpdb 2.1的已知问题
        if version == '2.1':
            print("⚠️  mmpdb 2.1版本存在以下已知问题:")
            print("   - 某些复杂杂环分子可能导致fragment_algorithm.py中的AssertionError")
            print("   - 建议降级到2.0版本或升级到更新版本")
        elif version.startswith('2.0'):
            print("✓ mmpdb 2.0版本相对稳定")
        else:
            print(f"ℹ️  mmpdb {version}版本，请查阅相关文档了解兼容性")
            
    except Exception as e:
        print(f"版本检查失败: {e}")

if __name__ == "__main__":
    print("开始检查mmpdb和相关依赖...")
    print("=" * 50)
    
    check_python_packages()
    check_mmpdb_command()
    test_problematic_smiles()
    check_known_issues()
    
    print("=" * 50)
    print("检查完成!")