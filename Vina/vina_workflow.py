#%%
''' Usage note:
input.csv     header: smiles,title
'''

import argparse
import os
import sys
import uuid
import shutil
from pathlib import Path
import pandas as pd
import numpy as np
from vina import Vina
import json
from glob import glob
from rdkit import Chem
from my_toolset.my_utils import get_mol, canonic_smiles, mapper
from functools import partial
import functools
from meeko import PDBQTMolecule
from meeko import RDKitMolCreate
from rdkit.Chem import AllChem
import copy
import random
from concurrent.futures import ThreadPoolExecutor

# 脚本会在每次运行时，生成一个随机的 UUID，
# 并在 resource 文件夹下创建一个以 UUID 命名的子目录，将所有中间文件/最终结果存放在其中。
vina_root = f'/home/davis/projects/dockingVina/Vina'
HERE = Path(__file__).resolve().parent        # .../Vina
PROJECT_ROOT = HERE.parent                     # .../dockingVina
print(f"PROJECT_ROOT is {PROJECT_ROOT}")

PYTHON_BIN = Path(sys.executable)
env_root = str(PYTHON_BIN.parent)
print(f"env_root is {env_root}")

gypsumPath = f"{PROJECT_ROOT}/gypsum_dl/run_gypsum_dl.py"
print(f"gypsumPath is {gypsumPath}")


def try_except_decorator(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            print(f"An error occurred: {e}")
    return wrapper

@try_except_decorator
def pdbqt2sdf(pdbqtFile):
    pdbqtFile_path = Path(pdbqtFile)
    pdbqt_mol = PDBQTMolecule.from_file(pdbqtFile, skip_typing=True)
    for imol in pdbqt_mol:
        rdkitmol = RDKitMolCreate.from_pdbqt_mol(copy.deepcopy(imol))
        rdkitmol0 = rdkitmol[0]
        sdfFile = f'{pdbqtFile_path.parent}/{imol.name}-p{imol.pose_id}.sdf'
        print(sdfFile)
        writer = Chem.SDWriter(sdfFile)
        rdkitmol0.SetProp("vinaScore", str(imol.score))
        ismi = Chem.MolToSmiles(Chem.RemoveHs(rdkitmol0))
        rdkitmol0.SetProp("smiles", ismi)
        writer.write(rdkitmol0)
        writer.close()

        resultDict = {
            'title': [imol.name],
            'pose': [imol.pose_id],
            'score': [imol.score],
            'smiles': [ismi],
            'file': [f"{imol.name}-p{imol.pose_id}.sdf"]
        }
        df = pd.DataFrame.from_dict(resultDict)
        df.to_csv(f'{pdbqtFile_path.parent}/{imol.name}-p{imol.pose_id}.csv', index=None)
        break  # 只输出 Top1 pose，然后跳出

def csv2gypSmi(inputCsv, dir='.'):
    dfInput = pd.read_csv(inputCsv)
    smilesHeaderList = ['SMILES', 'Smiles']
    out_path = f'{dir}/input.smi'
    if 'smiles' not in dfInput.columns:
        smilesExists = 0
        for ismiHeader in smilesHeaderList:
            if ismiHeader in dfInput.columns:
                dfInput['smiles'] = dfInput[ismiHeader]
                smilesExists = 1
        if smilesExists == 0:
            print('The input file should have smiles column!')
            sys.exit(0)
    if 'title' not in dfInput.columns:
        for idx, irow in dfInput.iterrows():
            dfInput.loc[idx, 'title'] = f"ID-{idx}"
    dfInput[['smiles', 'title']].to_csv(out_path, sep='\t', index=None)
    return out_path

def smi2pdbqt(inputSmi, min_ph=5, max_ph=9, num_processors=os.cpu_count(), dir='.'):
    gypsum_output_dir = f"{dir}/gypsumFolder"
    if not os.path.exists(gypsum_output_dir):
        os.makedirs(gypsum_output_dir)  # 先手动创建，避免 Start.py 报错
    os.system(f"mpirun -n {num_processors} python -m mpi4py "
              f"{gypsumPath} --source {inputSmi} --output_folder {dir}/gypsumFolder "
              f"--min_ph {min_ph} --max_ph {max_ph} --pka_precision 1 "
              f"--skip_optimize_geometry --2d_output_only --use_durrant_lab_filters")
    print(" gypsum output folder:", f"{dir}/gypsumFolder")
    try:
        supplier = Chem.SDMolSupplier(f"{dir}/gypsumFolder/gypsum_dl_success.sdf")
    except:
        sys.exit(1)
    molName_count = {}
    smiList = []
    for idx, mol in enumerate(supplier):
        if mol is not None:
            mol_name = mol.GetProp('_Name') if mol.HasProp('_Name') else 'NoName'
            if mol_name not in molName_count.keys():
                molName_count[mol_name] = 1
            else:
                molName_count[mol_name] += 1
            smi = mol.GetProp('SMILES') if mol.HasProp('SMILES') else ''
            if smi == '':
                continue
            print(f"Molecule Name: {mol_name} {smi}")
            smiList.append([smi, f"{mol_name}-{molName_count[mol_name]}"])
    dfSmi = pd.DataFrame(smiList, columns=['smiles', 'title'])
    dfSmi.to_csv(f'{dir}/input_prepared.smi', sep='\t', index=None, header=None)
    ''' covert smiles to 3d with babel '''
    os.system(f"{env_root}/obabel -ismi input_prepared.smi -osdf -O input_prepared.sdf --gen3d")
    os.system(f"{env_root}/mk_prepare_ligand.py -i input_prepared.sdf --multimol_outdir pdbqts")

@try_except_decorator
def vina_dock(lig, recpt='', center='', box_size=[20, 20, 20], dir='.'):
    ligPath = Path(lig)
    if os.path.exists(f'{dir}/docked/{ligPath.stem}.pdbqt'):
        print(f"Previous docking results will be used for {ligPath.stem}!")
    if not os.path.exists(f'{dir}/docked/{ligPath.stem}.pdbqt'):
        v = Vina(sf_name='vina')
        v.set_receptor(recpt)
        v.set_ligand_from_file(lig)
        v.compute_vina_maps(center=np.array(center, dtype=float), box_size=box_size)

        '''   Dock the ligand  '''
        v.dock(exhaustiveness=4, n_poses=20)
        if not os.path.exists(f'{dir}/docked'):
            os.system(f"mkdir -p {dir}/docked")
        v.write_poses(f'{dir}/docked/{ligPath.stem}.pdbqt', n_poses=5, overwrite=True)

    if not os.path.exists(f"{dir}/docked/{ligPath.stem}-p0.csv"):
        pdbqt2sdf(f"{dir}/docked/{ligPath.stem}.pdbqt")

def read_csv(file_path):
    return pd.read_csv(file_path)

def combine_csv(file_paths):
    with ThreadPoolExecutor() as executor:
        dataframes = list(executor.map(read_csv, file_paths))
    combined_df = pd.concat(dataframes, ignore_index=True)
    return combined_df

def clean_intermediate_files(work_dir):
    keep_files = {
        "70.csv",
        "dockRes.json",
        "protein_7UDP.pdbqt"
    }

    paths_to_remove = [
        f"{work_dir}/input.smi",
        f"{work_dir}/input_prepared.smi",
        f"{work_dir}/input_prepared.sdf",
        f"{work_dir}/gypsumFolder",
        f"{work_dir}/pdbqts",
        f"{work_dir}/docked",
    ]

    extra_patterns = [
        f"{work_dir}/*.sdf",
        f"{work_dir}/*.pdbqt",
        f"{work_dir}/*.csv",
    ]

    # 删除明确的文件或目录
    for path in paths_to_remove:
        if os.path.isfile(path) and os.path.basename(path) not in keep_files:
            os.remove(path)
        elif os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)

    # 使用模式匹配删除中间生成的文件
    for pattern in extra_patterns:
        for f in glob(pattern):
            if os.path.basename(f) not in keep_files:
                os.remove(f)

    print("✅ Intermediate files cleaned up.")


def vina_docking_from_list(ligands: list,
                           receptor_pdbqt: str,
                           min_ph: float = 6.0,
                           max_ph: float = 8.0,
                           n_jobs: int = 10) -> str:
    """
    新增接口：直接传递 ligands 列表（如：[{"smiles":"C=CCNC…","title":"ID1"}, {...}, …]），
    而不需要用户预先写 CSV。
    内部会自动生成一次 CSV 放到 run_dir 下
    返回 run_dir（字符串）。
    """
    orig_cwd = os.getcwd()
    # 1. 使用 ligands 列表和 receptor_pdbqt 构建 run_dir
    # receptor_pdbqt 是一个文件路径字符串，必须存在
    inputPath_dummy = None  # 这里只用来占位，不做文件读取
    receptPath = Path(receptor_pdbqt).absolute()
    if not receptPath.exists():
        raise FileNotFoundError(f"受体 PDBQT 文件不存在: {receptPath}")

    # ligands 必须是 list of dict，且每个 dict 至少含 'smiles' 和 'title'
    if not isinstance(ligands, list) or any(('smiles' not in mol or 'title' not in mol) for mol in ligands):
        raise ValueError("ligands 参数必须是 list，且每个元素含 'smiles' 和 'title'。")

    # 找到 ligands 所属“资源目录”，我们约定它是 receptor_pdbqt 所在目录的同级 resources
    # 也可以直接用 receptor_pdbqt.parent 作为资源根
    orig_parent = receptPath.parent   # e.g. /home/davis/projects/dockingVina/resource

    # 2. 生成随机 UUID，并创建 run_dir
    run_id = uuid.uuid4().hex
    run_dir = orig_parent / run_id
    os.makedirs(run_dir, exist_ok=True)

    # 3. 在 run_dir 下写一次 CSV：文件名可以固定为 "input.csv"
    csv_path = run_dir / "input.csv"
    df_lig = pd.DataFrame(ligands)  # 直接把 list of dict 转成 DataFrame
    # DataFrame 会自动按 {'smiles','title'} 两列写文件
    df_lig.to_csv(csv_path, index=False)

    # 4. 把当前 cwd 切换到 run_dir
    os.chdir(run_dir)

    # 已有： inputPath = csv_path
    inputPath = csv_path
    parent_path = str(run_dir)

    # Step 2: 检查 CSV 中是否含有 smiles/title 列
    dfInput = pd.read_csv(inputPath)
    if 'smiles' not in dfInput.columns:
        raise ValueError("输入的 CSV 必须包含 'smiles' 列。")
    if 'title' not in dfInput.columns:
        for idx, irow in dfInput.iterrows():
            dfInput.loc[idx, 'title'] = f'ID_{idx}'

    # Step 3: 组装 ligand（CSV → input.smi → input_prepared.sdf → .pdbqt）
    smi_path = csv2gypSmi(inputPath, dir=parent_path)
    smi2pdbqt(smi_path,
              min_ph=min_ph,
              max_ph=max_ph,
              num_processors=n_jobs,
              dir=parent_path)

    # Step 4: 读取 receptor 同级目录下的 vina_box.json
    DEFAULT_ROOT = Path(__file__).resolve().parent.parent  # Vina/ 下往上两级到项目根
    box_json = DEFAULT_ROOT / "resource" / "vina_box.json"
    if not box_json.exists():
        raise FileNotFoundError(f"未找到 {box_json}，请确认在受体文件同级目录下有 vina_box.json。")
    with open(box_json, "r") as infile:
        centerDict = json.load(infile)

    # Step 5: 并行调用 Vina 对所有 .pdbqt 做 docking
    pdbqtList = glob(f"{parent_path}/pdbqts/*.pdbqt")
    if len(pdbqtList) == 0:
        raise RuntimeError(f"在 {parent_path}/pdbqts 下未发现任何 .pdbqt 文件，可能生成步骤失败。")
    random.shuffle(pdbqtList)

    vina_dock_p = partial(vina_dock,
                          recpt=receptPath.as_posix(),
                          center=centerDict['center'],
                          dir=parent_path)
    mapper(n_jobs)(vina_dock_p, pdbqtList)

    # Step 6: 合并所有单个 ligand 的 CSV，生成 dockRes.csv
    csv_paths = glob(f"{parent_path}/docked/*.csv")
    if len(csv_paths) == 0:
        raise RuntimeError("未发现任何 docked/*.csv，说明 docking 或 pdbqt2sdf 步骤出错。")
    dfRes = combine_csv(csv_paths)
    dfRes = dfRes.sort_values(by='score', ascending=True)
    dfRes.to_json(f"{parent_path}/dockRes.json", orient="records", force_ascii=False, indent=2)

    # Step 7: 清理中间文件（只保留 keep_files）
    clean_intermediate_files(parent_path)

    # 返回本次运行的 run_dir
    os.chdir(orig_cwd)
    return str(run_dir)
# ============================================================
# 保持原有的命令行入口：如果直接脚本调用，则走 argparse → main
# ============================================================
if __name__ == "__main__":
    args = get_parser()
    main(args)
