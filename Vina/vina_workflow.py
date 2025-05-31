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
# 该脚本在每次运行时，会生成一个随机的 UUID，
# 并在 resource 文件夹下创建一个以 UUID 命名的子目录，将所有中间文件/最终结果存放在其中。
vina_root = f'/home/davis/projects/dockingVina/Vina'
# 当前文件 /home/davis/projects/dockingVina/Vina/vina_workflow.py
HERE = Path(__file__).resolve().parent        # .../Vina
PROJECT_ROOT = HERE.parent                     # .../dockingVina
print(f"PROJECT_ROOT is {PROJECT_ROOT}")

PYTHON_BIN = Path(sys.executable)
env_root = str(PYTHON_BIN.parent)
print(f"env_root is {env_root}")

gypsumPath = f"{PROJECT_ROOT}/gypsum_dl/run_gypsum_dl.py"
print(f"gypsumPath is {gypsumPath}")

def print_var(var, note=''):
    print(f"{var}:  {eval(var)}   {note}")

def try_except_decorator(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            print(f"An error occurred: {e}")
            # 你可以选择在这里返回某个默认值，或者重新抛出异常
            # return None  # 或者 raise
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
        "dockRes.csv",
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

def main(args):
    ''' 
    改动：
    1. 先根据输入 CSV 所在目录（resource），生成一个随机 UUID 子文件夹 run_dir；
    2. 把原始的 CSV 文件复制到 run_dir 下，后续所有中间结果都存放到 run_dir；
    '''
    inputPath = Path(args.input).absolute()    # e.g. /home/davis/projects/dockingVina/resource/70.csv
    receptPath = Path(args.receptor).absolute() # e.g. /home/davis/projects/dockingVina/resource/protein_7UDP.pdbqt

    orig_parent = inputPath.parent            # /home/davis/projects/dockingVina/resource
    # 生成随机 UUID，创建子目录
    run_id = uuid.uuid4().hex
    run_dir = orig_parent / run_id
    os.makedirs(run_dir, exist_ok=True)

    # 复制原始的 CSV 到 run_dir 下
    input_csv_name = inputPath.name          # "70.csv"
    new_input = run_dir / input_csv_name
    shutil.copy(inputPath, new_input)

    # 切换工作目录到 run_dir
    os.chdir(run_dir)

    # 后续都将使用 new_input 作为输入路径
    inputPath = new_input
    parent_path = str(run_dir)

    # 读取自带的 CSV，检查 columns
    dfInput = pd.read_csv(inputPath)
    if 'smiles' not in dfInput.columns:
        print('The input file should have smiles column!')
        sys.exit(0)
    if 'title' not in dfInput.columns:
        print('title will be added automatically!')
        for idx, irow in dfInput.iterrows():
            dfInput.loc[idx, 'title'] = f'ID_{idx}'

    ''' 1. prepare ligand with chiral, tautomer and pH '''
    smi_path = csv2gypSmi(inputPath, dir=parent_path)
    smi2pdbqt(smi_path, min_ph=args.min_ph, max_ph=args.max_ph,
              num_processors=args.n_jobs, dir=parent_path)

    ''' 2. 读取 receptor 同级目录下的 vina_box.json'''
    with open(f"{receptPath.parent}/vina_box.json", "r") as infile:
        centerDict = json.load(infile)

    ''' 3. 把所有 .pdbqt 列表读出来，然后并行做 docking '''
    pdbqtList = glob(f"{parent_path}/pdbqts/*.pdbqt")
    random.shuffle(pdbqtList)
    vina_dock_p = partial(vina_dock,
                          recpt=receptPath.as_posix(),
                          center=centerDict['center'],
                          dir=parent_path)
    mapper(args.n_jobs)(vina_dock_p, pdbqtList)

    ''' 4. 合并所有单个 ligand 的 CSV，生成 dockRes.csv '''
    csv_paths = glob(f"{parent_path}/docked/*.csv")
    print(f'len(csv_paths): {len(csv_paths)}')
    dfRes = combine_csv(csv_paths)
    dfRes = dfRes.sort_values(by='score', ascending=True)
    dfRes.to_csv(f"{parent_path}/dockRes.csv", index=None)

    ''' 5. 清理中间文件（只保留 keep_files） '''
    # clean_intermediate_files(parent_path)

    print(f"✅ 本次运行的 UUID: {run_id}")
    print(f"📂 结果目录: {run_dir}")
    print(f"📄 最终结果: {run_dir}/dockRes.csv")

def get_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", help="the path of ligand csv file with columns: ['smiles','title']",
                        default='')
    parser.add_argument("--receptor", help="the path of protein receptor file with center json",
                        default='')
    parser.add_argument("--min_ph", help="the minimum ph for protonization", type=float,
                        default=6)
    parser.add_argument("--max_ph", help="the maximum ph for protonization", type=float,
                        default=8)
    parser.add_argument("--n_jobs", help="the number of jobs running in parallel", type=int,
                        default=10)
    args = parser.parse_args()
    return args

if __name__ == "__main__":
    args = get_parser()
    main(args)
