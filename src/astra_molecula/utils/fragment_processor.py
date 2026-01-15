import pandas as pd
import os
import sys
import shutil
import subprocess
from pathlib import Path
from mmpdblib.fragment_io import read_fragment_records
from rdkit import Chem


def get_mmpdb_path() -> str:
    """获取 mmpdb 可执行文件的路径"""
    # 首先尝试从 PATH 中查找
    mmpdb_path = shutil.which("mmpdb")
    if mmpdb_path:
        return mmpdb_path
    
    # 如果 PATH 中没有，尝试从当前 Python 环境的 bin 目录查找
    python_bin_dir = Path(sys.executable).parent
    mmpdb_in_env = python_bin_dir / "mmpdb"
    if mmpdb_in_env.exists():
        return str(mmpdb_in_env)
    
    # 最后尝试常见的 conda 环境路径
    conda_paths = [
        "/opt/conda/envs/AstraMolecula/bin/mmpdb",
        Path.home() / "miniforge3/envs/AstraMolecula/bin/mmpdb",
        Path.home() / "miniconda3/envs/AstraMolecula/bin/mmpdb",
    ]
    for p in conda_paths:
        if Path(p).exists():
            return str(p)
    
    raise FileNotFoundError("找不到 mmpdb 可执行文件，请确保 mmpdb 已正确安装。")
class Index_Dummy:
    """对 dummy 原子进行编号：变量和常量部分分别处理"""
    def __init__(self, df):
        self.df = df

    def index_constant(self, constSmi, attachmentOrder):
        count = -1
        newConstSmi = ""
        for idx, ichar in enumerate(constSmi):
            if ichar == '*':
                count += 1
                # 注意：attachmentOrder 应为可迭代对象，这里假设传入的 attachmentOrder 为列表或可转换为列表
                ichar = f"[*:{int(attachmentOrder[count]) + 1}]"
            newConstSmi += ichar
        return newConstSmi

    def index_var(self, varSmi):
        count = 0
        newVarSmi = ""
        for idx, ichar in enumerate(varSmi):
            if ichar == '*':
                count += 1
                ichar = f"[*:{count}]"
            newVarSmi += ichar
        return newVarSmi

    def add_index(self):
        for idx, row in self.df.iterrows():
            varSmi = row['variable_smiles']
            constSmi = row['constant_smiles']
            attachmentOrder = row['attachment_order']
            self.df.loc[idx, 'variable_smiles'] = self.index_var(varSmi)
            self.df.loc[idx, 'constant_smiles'] = self.index_constant(constSmi, attachmentOrder)
        return self.df


def count_heavy_atoms(smi):
    mol = Chem.MolFromSmiles(smi)
    if not mol:
        return 0
    heavy_count = len([atom for atom in mol.GetAtoms() if atom.GetAtomicNum() > 1])
    return heavy_count


def fragmentize_molecule(smiles_string: str, max_ratio: float = 0.8) -> pd.DataFrame:
    """
    对单个分子进行 fragment 化处理：
      1. 将 SMILES 字符串写入临时文件（同时写入标题信息）
      2. 使用 mmpdb 工具 fragment 化分子
      3. 读取 fragment 文件，并依据 heavy atom 个数筛选合适的 fragment
      4. 对 fragment 中 dummy 原子添加编号
      5. 最后返回 DataFrame 格式的 fragment 数据
    """
    # 定义临时文件名（这里保证文件名唯一性可根据需要进一步改进）
    input_file = "temp_input.smi"
    output_file = "temp_output.fragments"

    try:
        # 将 SMILES 字符串写入临时输入文件（标题默认写 “Molecule”）
        with open(input_file, "w") as f:
            f.write(smiles_string + "\t" + "Molecule" + "\n")

        # 获取 mmpdb 路径并使用 subprocess 执行
        mmpdb_path = get_mmpdb_path()
        result = subprocess.run(
            [mmpdb_path, "fragment", input_file, "-o", output_file],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            raise Exception(f"mmpdb fragment 命令执行失败: {result.stderr}")

        # 读取并处理碎片
        fragment_reader = read_fragment_records(output_file)
        frag_list = []
        for record in fragment_reader:
            # 打印或记录当前处理的 record 信息，可根据需要选择注释掉
            print(f"Processing record: {record.id}, {record.normalized_smiles}")
            for frag in record.fragments:
                if count_heavy_atoms(frag.variable_smiles) < count_heavy_atoms(record.normalized_smiles) * max_ratio:
                    frag_list.append({
                        'variable_smiles': frag.variable_smiles,
                        'constant_smiles': frag.constant_smiles,
                        'record_id': record.id,
                        'normalized_smiles': record.normalized_smiles,
                        'attachment_order': frag.attachment_order
                    })

        if not frag_list:
            raise Exception("未找到满足筛选条件的碎片。")

        # 构造 DataFrame，并对 dummy 原子添加编号
        df_frag = pd.DataFrame(frag_list)
        index_dummy = Index_Dummy(df_frag)
        df_frag = index_dummy.add_index()
        return df_frag

    finally:
        # 删除临时文件，确保每次调用结束后文件被清理
        if Path(input_file).exists():
            os.remove(input_file)
        if Path(output_file).exists():
            os.remove(output_file)