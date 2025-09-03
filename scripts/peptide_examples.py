#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单的Peptide任务提交示例
演示如何使用peptide_api_client.py提交任务
"""

import sys
import os
from pathlib import Path

# 添加scripts目录到Python路径
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))

from peptide_api_client import PeptideAPIClient

def example_basic_peptide_task():
    """基础肽段优化任务示例"""
    print("🧬 基础肽段优化任务示例")
    print("=" * 50)
    
    # 创建API客户端
    client = PeptideAPIClient(
        base_url="http://127.0.0.1:8000",
        username="admin", 
        password="Admin#2024"
    )
    
    # 示例参数
    peptide_sequence = "MKFLVNVAL"  # 简短的测试序列
    receptor_file = "../test/5ffg.pdb"  # 使用test目录中的文件
    
    # 检查受体文件是否存在
    receptor_path = Path(receptor_file)
    if not receptor_path.exists():
        print(f"❌ 受体文件不存在: {receptor_file}")
        print("💡 请确保文件路径正确，或使用绝对路径")
        return False
    
    # 运行完整工作流程
    success = client.run_complete_workflow(
        peptide_sequence=peptide_sequence,
        receptor_pdb_file=str(receptor_path.absolute()),
        cores=4,
        cleanup=False,  # 保留中间文件以便检查
        step=None,  # 运行完整流程
        proteinmpnn_enabled=False,  # 暂时禁用以加快测试
        n_poses=5,  # 较少的构象数以加快测试
        max_wait_minutes=30
    )
    
    return success

def example_step_by_step():
    """分步骤执行示例"""
    print("🧬 分步骤执行示例")
    print("=" * 50)
    
    # 创建API客户端
    client = PeptideAPIClient()
    
    # 1. 登录
    if not client.login():
        return False
    
    # 2. 查看已上传的文件
    uploaded_files = client.list_uploaded_files()
    
    # 3. 上传新文件（如果需要）
    receptor_file = "../test/5ffg.pdb"
    receptor_path = Path(receptor_file)
    
    if receptor_path.exists():
        client.upload_pdb_file(str(receptor_path.absolute()))
    
    # 4. 创建任务
    task_id = client.create_peptide_task(
        peptide_sequence="ANAERIVRT",  # 从user3.pdbqt提取的序列开头
        receptor_pdb_filename="5ffg.pdb",
        cores=2,
        cleanup=False,
        step=3,  # 只运行对接步骤
        proteinmpnn_enabled=False,
        n_poses=3
    )
    
    if task_id:
        print(f"✅ 任务创建成功: {task_id}")
        
        # 5. 监控任务状态
        success = client.monitor_task_progress(task_id, max_wait_minutes=15)
        
        # 6. 获取结果
        client.get_task_results(task_id)
        
        return success
    
    return False

def example_from_docking_result():
    """从docking结果创建peptide任务的示例"""
    print("🧬 从Docking结果创建Peptide任务示例")
    print("=" * 50)
    
    # 使用我们之前转换的结果
    converted_input_dir = "../test/converted_peptide_input"
    fasta_file = Path(converted_input_dir) / "peptide.fasta"
    pdb_file = Path(converted_input_dir) / "5ffg.pdb"
    
    if not fasta_file.exists() or not pdb_file.exists():
        print("❌ 转换后的文件不存在，请先运行格式转换")
        print("💡 运行: python ../utils/format_converter.py --help")
        return False
    
    # 读取肽段序列
    with open(fasta_file, 'r') as f:
        lines = f.readlines()
        if len(lines) >= 2:
            sequence = lines[1].strip()
            # 使用较短的序列片段进行测试
            test_sequence = sequence[:20]  # 取前20个氨基酸
        else:
            print("❌ FASTA文件格式错误")
            return False
    
    print(f"🧬 使用序列: {test_sequence}")
    
    # 创建API客户端
    client = PeptideAPIClient()
    
    # 运行完整工作流程
    success = client.run_complete_workflow(
        peptide_sequence=test_sequence,
        receptor_pdb_file=str(pdb_file.absolute()),
        cores=4,
        cleanup=False,
        step=None,
        proteinmpnn_enabled=True,  # 启用完整优化
        n_poses=5,
        max_wait_minutes=45
    )
    
    return success

def main():
    """主函数"""
    print("🧬 Peptide API客户端使用示例")
    print("=" * 60)
    
    # 检查当前目录
    current_dir = Path.cwd()
    print(f"📂 当前目录: {current_dir}")
    
    # 提供多个示例选项
    examples = {
        "1": ("基础肽段优化任务", example_basic_peptide_task),
        "2": ("分步骤执行示例", example_step_by_step),
        "3": ("从Docking结果创建任务", example_from_docking_result)
    }
    
    print("\n📋 可用示例:")
    for key, (desc, _) in examples.items():
        print(f"  {key}. {desc}")
    
    # 如果提供了命令行参数，直接运行对应示例
    if len(sys.argv) > 1:
        choice = sys.argv[1]
    else:
        choice = input("\n请选择示例 (1-3, 默认1): ").strip() or "1"
    
    if choice in examples:
        desc, func = examples[choice]
        print(f"\n🚀 运行示例: {desc}")
        print("-" * 40)
        
        try:
            success = func()
            if success:
                print("\n🎉 示例执行成功！")
            else:
                print("\n⚠️  示例执行未完全成功")
        except KeyboardInterrupt:
            print("\n👤 用户中断执行")
        except Exception as e:
            print(f"\n❌ 示例执行失败: {e}")
            import traceback
            traceback.print_exc()
    else:
        print(f"❌ 无效选择: {choice}")
        sys.exit(1)

if __name__ == "__main__":
    main()
