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
    print("Running Gypsum-DL for molecule preparation...")
    # 使用更宽松的参数来减少conformer generation failures
    gypsum_cmd = (f"mpirun -n {num_processors} python3 -m mpi4py "
                  f"{gypsumPath} --source {inputSmi} --output_folder {dir}/gypsumFolder "
                  f"--min_ph {min_ph} --max_ph {max_ph} --pka_precision 1 "
                  f"--skip_optimize_geometry --2d_output_only --use_durrant_lab_filters "
                  f"--max_variants_per_compound 5")  # 限制变体数量
    
    result = os.system(gypsum_cmd)
    if result != 0:
        print("Warning: Gypsum-DL had issues, but continuing with available output...")
    
    print(" gypsum output folder:", f"{dir}/gypsumFolder")
    try:
        supplier = Chem.SDMolSupplier(f"{dir}/gypsumFolder/gypsum_dl_success.sdf")
    except:
        print("Error: Could not read Gypsum-DL output. Exiting.")
        sys.exit(1)
    
    molName_count = {}
    smiList = []
    processed_count = 0
    
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
            processed_count += 1
    
    print(f"Successfully processed {processed_count} molecules from Gypsum-DL")
    
    if processed_count == 0:
        print("Warning: No molecules were successfully processed by Gypsum-DL, trying direct SMILES processing...")
        # 尝试直接从原始SMILES文件处理
        try:
            original_df = pd.read_csv(inputSmi, sep='\t', header=None, names=['smiles', 'title'])
            print(f"Attempting to process {len(original_df)} original SMILES directly...")
            
            # 直接使用原始SMILES，跳过Gypsum-DL处理
            for idx, row in original_df.iterrows():
                smiles = row['smiles']
                title = row['title'] if pd.notna(row['title']) else f"mol_{idx}"
                smiList.append([smiles, title])
                processed_count += 1
            
            print(f"Successfully recovered {processed_count} molecules from original SMILES")
        except Exception as e:
            print(f"Failed to recover from original SMILES: {e}")
            raise RuntimeError("No molecules could be processed by Gypsum-DL and recovery failed")
        
    dfSmi = pd.DataFrame(smiList, columns=['smiles', 'title'])
    dfSmi.to_csv(f'{dir}/input_prepared.smi', sep='\t', index=None, header=None)
    
    # 改进的分子3D坐标生成和PDBQT转换过程
    print("Converting SMILES to 3D structures...")
    
    # 首先尝试使用Open Babel
    babel_cmd = f"{env_root}/obabel -ismi input_prepared.smi -osdf -O input_prepared.sdf --gen3d"
    result = os.system(babel_cmd)
    
    if result != 0:
        print("Warning: Open Babel 3D coordinate generation had issues, trying RDKit fallback...")
    
    # 检查是否生成了有效的SDF文件
    sdf_valid = False
    if os.path.exists(f'{dir}/input_prepared.sdf'):
        try:
            test_supplier = Chem.SDMolSupplier(f'{dir}/input_prepared.sdf')
            valid_mols = sum(1 for mol in test_supplier if mol is not None)
            if valid_mols > 0:
                sdf_valid = True
                print(f"Open Babel successfully generated {valid_mols} valid molecules")
        except:
            pass
    
    # 如果Open Babel失败，使用RDKit作为备用方法
    if not sdf_valid:
        print("Using RDKit for 3D coordinate generation...")
        try:
            df_molecules = pd.read_csv(f'{dir}/input_prepared.smi', sep='\t', header=None, names=['smiles', 'title'])
            sdf_writer = Chem.SDWriter(f'{dir}/input_prepared.sdf')
            successful_count = 0
            
            for _, row in df_molecules.iterrows():
                try:
                    mol = Chem.MolFromSmiles(row['smiles'])
                    if mol is not None:
                        # 确保添加显式氢原子
                        mol = Chem.AddHs(mol, explicitOnly=False, addCoords=False)
                        
                        # 尝试多种3D坐标生成方法
                        embed_success = False
                        
                        # 方法1: 标准ETKDG
                        try:
                            if AllChem.EmbedMolecule(mol, AllChem.ETKDG()) == 0:
                                embed_success = True
                        except:
                            pass
                        
                        # 方法2: 使用不同的随机种子
                        if not embed_success:
                            try:
                                params = AllChem.ETKDG()
                                params.randomSeed = 42
                                if AllChem.EmbedMolecule(mol, params) == 0:
                                    embed_success = True
                            except:
                                pass
                        
                        # 方法3: 使用基本距离几何
                        if not embed_success:
                            try:
                                if AllChem.EmbedMolecule(mol, randomSeed=42) == 0:
                                    embed_success = True
                            except:
                                pass
                        
                        if embed_success:
                            # 优化分子几何
                            try:
                                AllChem.OptimizeMolecule(mol, maxIters=200)
                            except:
                                pass  # 优化失败也继续
                            
                            mol.SetProp('_Name', str(row['title']))
                            sdf_writer.write(mol)
                            successful_count += 1
                        else:
                            print(f"Warning: Failed to generate 3D coordinates for {row['title']}")
                            
                except Exception as e:
                    print(f"Error processing molecule {row['title']}: {e}")
                    continue
                        
            sdf_writer.close()
            print(f"RDKit successfully generated 3D coordinates for {successful_count} molecules")
            
            if successful_count == 0:
                raise RuntimeError("No molecules could be converted to 3D structures")
                
        except Exception as e:
            print(f"RDKit fallback also failed: {e}")
            raise RuntimeError(f"All 3D coordinate generation methods failed: {e}")
    
    # 使用更详细的错误处理进行PDBQT转换
    print("Converting SDF to PDBQT format...")
    # 使用更好的参数确保正确处理显式氢原子
    prepare_cmd = f"{env_root}/mk_prepare_ligand.py -i input_prepared.sdf --multimol_outdir pdbqts --keep_nonpolar_hydrogens"
    result = os.system(prepare_cmd)
    
    if result != 0:
        print("Warning: PDBQT preparation had issues, trying without keep_nonpolar_hydrogens...")
        # 备用方法：不使用 keep_nonpolar_hydrogens 参数
        prepare_cmd_backup = f"{env_root}/mk_prepare_ligand.py -i input_prepared.sdf --multimol_outdir pdbqts"
        result_backup = os.system(prepare_cmd_backup)
        
        if result_backup != 0:
            print("Warning: Both PDBQT preparation methods failed, but continuing...")
        
    # 检查生成的PDBQT文件数量
    pdbqt_files = glob(f"{dir}/pdbqts/*.pdbqt")
    print(f"Successfully generated {len(pdbqt_files)} PDBQT files for docking")
    
    # 如果没有生成任何PDBQT文件，尝试使用更简单的方法
    if len(pdbqt_files) == 0:
        print("No PDBQT files generated, trying alternative approach...")
        try:
            # 尝试使用更基本的转换方法
            basic_cmd = f"{env_root}/mk_prepare_ligand.py -i input_prepared.sdf --multimol_outdir pdbqts --rigid_macrocycles"
            os.system(basic_cmd)
            pdbqt_files = glob(f"{dir}/pdbqts/*.pdbqt")
            print(f"Alternative method generated {len(pdbqt_files)} PDBQT files for docking")
        except Exception as e:
            print(f"Alternative PDBQT generation also failed: {e}")
    
    # 最终检查：如果仍然没有PDBQT文件，抛出错误而不是继续
    if len(pdbqt_files) == 0:
        raise RuntimeError("Failed to generate any PDBQT files for docking. This could be due to problematic input molecules or missing dependencies.")

def vina_dock(lig, recpt='', center='', box_size=[20, 20, 20], dir='.'):
    """
    执行分子对接
    """
    ligPath = Path(lig)
    
    # 检查是否已有对接结果
    if os.path.exists(f'{dir}/docked/{ligPath.stem}.pdbqt'):
        print(f"Previous docking results will be used for {ligPath.stem}!")
        # 如果结果文件存在但CSV不存在，尝试生成CSV
        if not os.path.exists(f"{dir}/docked/{ligPath.stem}-p0.csv"):
            try:
                pdbqt2sdf(f"{dir}/docked/{ligPath.stem}.pdbqt")
            except Exception as e:
                print(f"Error generating CSV for existing result {ligPath.stem}: {e}")
        return
    
    try:
        # 验证受体文件存在
        if not os.path.exists(recpt):
            raise FileNotFoundError(f"Receptor file not found: {recpt}")
        
        # 验证配体文件存在且不为空
        if not os.path.exists(lig):
            raise FileNotFoundError(f"Ligand file not found: {lig}")
        
        # 检查配体文件内容是否有效
        with open(lig, 'r') as f:
            ligand_content = f.read().strip()
            if not ligand_content or len(ligand_content) < 10:
                raise ValueError(f"Ligand file appears to be empty or invalid: {lig}")
        
        print(f"Starting docking for ligand: {lig}")
        print(f"Using receptor: {recpt}")
        print(f"Center: {center}")
        print(f"Box size: {box_size}")
        
        # 创建Vina对象
        v = Vina(sf_name='vina')
        
        # 设置受体 - 使用不同的调用方式
        try:
            # 方法1: 直接传递文件路径字符串
            v.set_receptor(str(recpt))
            print("Receptor set successfully using string path")
        except Exception as e1:
            try:
                # 方法2: 使用rigid参数（如果是较新版本的vina）
                v.set_receptor(rigid_pdbqt_filename=str(recpt))
                print("Receptor set successfully using rigid_pdbqt_filename")
            except Exception as e2:
                try:
                    # 方法3: 读取文件内容后设置
                    with open(recpt, 'r') as f:
                        receptor_content = f.read()
                    v.set_receptor(receptor_content)
                    print("Receptor set successfully using file content")
                except Exception as e3:
                    print(f"All receptor setting methods failed:")
                    print(f"Method 1 error: {e1}")
                    print(f"Method 2 error: {e2}")
                    print(f"Method 3 error: {e3}")
                    raise RuntimeError(f"Failed to set receptor: {recpt}")
        
        # 设置配体
        print(f"Setting ligand: {lig}")
        try:
            v.set_ligand_from_file(str(lig))
            print("Ligand set successfully")
        except Exception as e:
            print(f"Error setting ligand {lig}: {e}")
            # 尝试先验证PDBQT文件格式
            print("Attempting to validate and fix ligand file...")
            raise RuntimeError(f"Failed to set ligand: {lig}")
        
        # 计算Vina maps
        print(f"Computing vina maps...")
        try:
            v.compute_vina_maps(center=np.array(center, dtype=float), box_size=np.array(box_size, dtype=float))
            print("Vina maps computed successfully")
        except Exception as e:
            print(f"Error computing vina maps for {lig}: {e}")
            raise RuntimeError(f"Failed to compute vina maps for ligand: {lig}")

        # 执行对接 - 添加更多错误处理
        print("Starting docking...")
        try:
            # 使用较低的exhaustiveness来避免一些数值问题
            v.dock(exhaustiveness=2, n_poses=10)
            print("Docking completed successfully")
        except Exception as e:
            print(f"Docking failed for {lig}: {e}")
            # 如果assertion error，跳过这个分子但不终止整个流程
            if "Assertion failed" in str(e) or "nrm >= epsilon_fl" in str(e):
                print(f"Skipping problematic ligand {ligPath.stem} due to coordinate/structure issues")
                # 创建一个错误记录文件
                error_dir = f'{dir}/errors'
                if not os.path.exists(error_dir):
                    os.makedirs(error_dir, exist_ok=True)
                with open(f'{error_dir}/{ligPath.stem}_error.txt', 'w') as f:
                    f.write(f"Docking failed for {lig}: {e}\n")
                    f.write("Likely cause: problematic ligand coordinates or structure\n")
                return  # 跳过这个分子，继续下一个
            else:
                raise  # 其他类型的错误继续抛出
        
        # 创建输出目录
        docked_dir = f'{dir}/docked'
        if not os.path.exists(docked_dir):
            os.makedirs(docked_dir, exist_ok=True)
        
        # 写入对接结果
        output_file = f'{docked_dir}/{ligPath.stem}.pdbqt'
        v.write_poses(output_file, n_poses=5, overwrite=True)
        print(f"Poses written to {output_file}")
        
        # 生成CSV结果
        if not os.path.exists(f"{docked_dir}/{ligPath.stem}-p0.csv"):
            try:
                pdbqt2sdf(output_file)
                print(f"CSV generated for {ligPath.stem}")
            except Exception as e:
                print(f"Error generating CSV for {ligPath.stem}: {e}")
                # 不抛出异常，因为主要的对接已经完成
    
    except Exception as e:
        print(f"An error occurred in vina_dock for {lig}: {e}")
        import traceback
        traceback.print_exc()
        
        # 对于assertion错误，不重新抛出异常，而是记录并跳过
        if "Assertion failed" in str(e) or "nrm >= epsilon_fl" in str(e):
            print(f"Skipping problematic ligand {ligPath.stem} and continuing with next ligand")
            error_dir = f'{dir}/errors'
            if not os.path.exists(error_dir):
                os.makedirs(error_dir, exist_ok=True)
            with open(f'{error_dir}/{ligPath.stem}_error.txt', 'w') as f:
                f.write(f"Docking failed for {lig}: {e}\n")
                f.write("Likely cause: problematic ligand coordinates or structure\n")
                f.write(traceback.format_exc())
            return
        else:
            # 其他错误重新抛出
            raise

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
                           n_jobs: int = 8) -> str:
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
    
    print(f"Found {len(pdbqtList)} PDBQT files for docking")
    random.shuffle(pdbqtList)

    vina_dock_p = partial(vina_dock,
                          recpt=receptPath.as_posix(),
                          center=centerDict['center'],
                          dir=parent_path)
    mapper(n_jobs)(vina_dock_p, pdbqtList)

    # Step 6: 合并所有单个 ligand 的 CSV，生成 dockRes.csv
    csv_paths = glob(f"{parent_path}/docked/*.csv")
    if len(csv_paths) == 0:
        # 检查是否有错误文件生成
        error_files = glob(f"{parent_path}/errors/*.txt")
        if len(error_files) > 0:
            print(f"Warning: {len(error_files)} ligands failed docking but no successful results found")
            print(f"Creating empty result set...")
            # 创建空的结果数据框
            dfRes = pd.DataFrame(columns=['title', 'pose', 'score', 'smiles', 'file', 'protein_path'])
        else:
            raise RuntimeError("未发现任何 docked/*.csv，说明 docking 或 pdbqt2sdf 步骤出错。")
    else:
        dfRes = combine_csv(csv_paths)
        dfRes = dfRes.sort_values(by='score', ascending=True)
    
    # 为每个结果添加protein路径信息
    dfRes['protein_path'] = str(receptPath)
    
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
    print("This module is designed to be imported and used via vina_docking_from_list() function")
    print("Command line interface not available in this version")
