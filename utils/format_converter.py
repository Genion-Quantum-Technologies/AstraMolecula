#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
格式转换工具：用于将docking结果转换为peptide_opt可用的输入格式
"""

from pathlib import Path
from Bio.PDB import PDBParser, PDBIO, Select
from Bio.SeqUtils import seq1
from Bio.SeqUtils.ProtParam import ProteinAnalysis
import subprocess
import tempfile
import os

class DockingToPeptideConverter:
    """将Docking结果转换为peptide_opt输入格式的转换器"""
    
    def __init__(self):
        self.parser = PDBParser(QUIET=True)
        self.io = PDBIO()
    
    def pdbqt_to_pdb(self, pdbqt_file: str, output_pdb: str) -> bool:
        """
        将PDBQT文件转换为PDB文件
        
        Args:
            pdbqt_file: 输入的PDBQT文件路径
            output_pdb: 输出的PDB文件路径
            
        Returns:
            bool: 转换是否成功
        """
        try:
            with open(pdbqt_file, 'r') as f_in:
                content = f_in.read()
            
            # 去除PDBQT特有的行，保留PDB兼容的行
            pdb_lines = []
            for line in content.split('\n'):
                if line.startswith(('ATOM', 'HETATM', 'HEADER', 'TITLE', 'REMARK')):
                    # 移除PDBQT特有的电荷和原子类型信息（最后两列）
                    if line.startswith(('ATOM', 'HETATM')):
                        pdb_line = line[:66]  # 截取到occupancy列
                        if len(line) > 66:
                            # 保留温度因子列
                            pdb_line += line[60:66].ljust(6) if len(line) > 60 else '  0.00'
                        pdb_lines.append(pdb_line)
                    else:
                        pdb_lines.append(line)
                elif line.startswith('END'):
                    pdb_lines.append(line)
            
            with open(output_pdb, 'w') as f_out:
                f_out.write('\n'.join(pdb_lines))
            
            return True
            
        except Exception as e:
            print(f"转换PDBQT到PDB失败: {e}")
            return False
    
    def extract_peptide_sequence_from_pdb(self, pdb_file: str) -> str:
        """
        从PDB文件中提取肽段序列
        
        Args:
            pdb_file: PDB文件路径
            
        Returns:
            str: 肽段序列（单字母缩写）
        """
        try:
            structure = self.parser.get_structure("peptide", pdb_file)
            
            sequence = ""
            for model in structure:
                for chain in model:
                    for residue in chain:
                        if residue.get_id()[0] == ' ':  # 只处理标准氨基酸
                            res_name = residue.get_resname()
                            try:
                                # 转换为单字母缩写
                                single_letter = seq1(res_name)
                                sequence += single_letter
                            except:
                                print(f"无法识别的氨基酸: {res_name}")
                                continue
            
            return sequence
            
        except Exception as e:
            print(f"提取肽段序列失败: {e}")
            return ""
    
    def create_fasta_file(self, sequence: str, output_fasta: str, title: str = "peptide") -> bool:
        """
        创建FASTA格式文件
        
        Args:
            sequence: 肽段序列
            output_fasta: 输出的FASTA文件路径
            title: 序列标题
            
        Returns:
            bool: 创建是否成功
        """
        try:
            with open(output_fasta, 'w') as f:
                f.write(f">{title}\n")
                f.write(f"{sequence}\n")
            return True
        except Exception as e:
            print(f"创建FASTA文件失败: {e}")
            return False
    
    def convert_docking_result_to_peptide_input(self, 
                                              docked_peptide_pdbqt: str,
                                              receptor_pdbqt: str,
                                              output_dir: str) -> dict:
        """
        将docking结果转换为peptide_opt可用的输入格式
        
        Args:
            docked_peptide_pdbqt: 对接后的肽段PDBQT文件
            receptor_pdbqt: 受体PDBQT文件  
            output_dir: 输出目录
            
        Returns:
            dict: 转换结果信息
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        result = {
            "success": False,
            "files_created": [],
            "errors": []
        }
        
        try:
            # 1. 转换受体PDBQT为PDB
            receptor_pdb = output_path / "5ffg.pdb"
            if self.pdbqt_to_pdb(receptor_pdbqt, str(receptor_pdb)):
                result["files_created"].append(str(receptor_pdb))
                print(f"✅ 受体文件转换成功: {receptor_pdb}")
            else:
                result["errors"].append("受体文件转换失败")
                return result
            
            # 2. 转换肽段PDBQT为PDB
            temp_peptide_pdb = output_path / "temp_peptide.pdb"
            if self.pdbqt_to_pdb(docked_peptide_pdbqt, str(temp_peptide_pdb)):
                print(f"✅ 肽段文件转换成功: {temp_peptide_pdb}")
                
                # 3. 从肽段PDB提取序列
                peptide_sequence = self.extract_peptide_sequence_from_pdb(str(temp_peptide_pdb))
                if peptide_sequence:
                    print(f"✅ 提取肽段序列: {peptide_sequence}")
                    
                    # 4. 创建FASTA文件
                    fasta_file = output_path / "peptide.fasta"
                    if self.create_fasta_file(peptide_sequence, str(fasta_file)):
                        result["files_created"].append(str(fasta_file))
                        print(f"✅ FASTA文件创建成功: {fasta_file}")
                        
                        # 5. 清理临时文件
                        if temp_peptide_pdb.exists():
                            temp_peptide_pdb.unlink()
                        
                        result["success"] = True
                        result["peptide_sequence"] = peptide_sequence
                        print("🎉 转换完成！生成的文件可直接用于peptide_opt")
                        
                    else:
                        result["errors"].append("FASTA文件创建失败")
                else:
                    result["errors"].append("无法从肽段文件提取序列")
            else:
                result["errors"].append("肽段文件转换失败")
                
        except Exception as e:
            result["errors"].append(f"转换过程发生错误: {str(e)}")
        
        return result


def main():
    """命令行工具示例"""
    import argparse
    
    parser = argparse.ArgumentParser(description='将Docking结果转换为peptide_opt输入格式')
    parser.add_argument('--peptide_pdbqt', required=True, help='对接后的肽段PDBQT文件')
    parser.add_argument('--receptor_pdbqt', required=True, help='受体PDBQT文件')
    parser.add_argument('--output_dir', required=True, help='输出目录')
    
    args = parser.parse_args()
    
    converter = DockingToPeptideConverter()
    result = converter.convert_docking_result_to_peptide_input(
        args.peptide_pdbqt,
        args.receptor_pdbqt,
        args.output_dir
    )
    
    if result["success"]:
        print("✅ 转换成功完成！")
        print("📂 生成的文件:")
        for file_path in result["files_created"]:
            print(f"   - {file_path}")
    else:
        print("❌ 转换失败！")
        print("🔍 错误信息:")
        for error in result["errors"]:
            print(f"   - {error}")


if __name__ == "__main__":
    main()
