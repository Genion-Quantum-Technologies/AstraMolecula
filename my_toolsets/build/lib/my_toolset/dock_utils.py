try:
    from openbabel import pybel
except:
    import pybel
import pandas as pd
import argparse
from functools import partial
from multiprocessing import Pool
from tqdm.auto import tqdm
import os
from pathlib import Path
import rdkit
from rdkit import Chem
from func_timeout import func_set_timeout
# from pebble import concurrent, ProcessPool
# from concurrent.futures import TimeoutError

######## Gilde enviroment setting
schrodinger_root_path='/public/software/schrodinger/2021-2'
# schrodinger_root_path='/opt/schrodinger2021-2'
glide = f"{schrodinger_root_path}/glide"
structconvert = f"{schrodinger_root_path}/utilities/structconvert"
prepwizard = f"{schrodinger_root_path}/utilities/prepwizard"
ligprep = f"{schrodinger_root_path}/ligprep"
glide_sort = f"{schrodinger_root_path}/utilities/glide_sort"
mol2convert = f"{schrodinger_root_path}/utilities/mol2convert"

#################################

def smi_mae(id_smi, size_upper_limit=60, fast_flag=0):
    ''' The SMILES of ligand will be transformed into maestro format.
    id_smi:[name, SMILES]
    output file: {id_smi[0]}.mae
    fast_flag: only explore the best tautormers
    '''
    # chembl_id = col['ChEMBL ID']
    chembl_id = str(id_smi[0])
    smi = id_smi[1]
    # path=Path(path)
    opfile = f'{chembl_id}'
    try:
    # if 1:
        # smi = col['Smiles']
        mol = pybel.readstring("smi", smi)
        # strip salt
        mol.OBMol.StripSalts(10)
        mols = mol.OBMol.Separate()
        # print(pybel.Molecule(mols))
        mol = pybel.Molecule(mols[0])
        for imol in mols:
            imol = pybel.Molecule(imol)
            if len(imol.atoms) > len(mol.atoms):
                mol = imol
        if len(mol.atoms)>size_upper_limit:
            print(f'SMILES is larger than {size_upper_limit}')
            return 0
        # print(mol)
        mol.addh()
        mol.title = chembl_id
        # print(mol)
        mol.make3D(forcefield='mmff94', steps=100)
        mol.localopt()
        mol.write(format='mol2', filename=f'{opfile}.mol2', overwrite=True)
        os.system(f'{structconvert} -imol2 {opfile}.mol2 -omae {opfile}_raw.mae')
        if fast_flag:
            os.system(f'{ligprep} -imae {opfile}_raw.mae -omae {opfile}.mae -epik -s 1 -t 1 -WAIT  -NOJOBID')
        else:
            os.system(f'{ligprep} -imae {opfile}_raw.mae -omae {opfile}.mae -epik -WAIT  -NOJOBID')
        #  clean
        if os.path.exists(f'{opfile}.mol2'):
            os.system(f'rm {opfile}.mol2')
        return 1
    except:
        print(f"Tranformation of {smi} failed! ")
        if os.path.exists(f'{opfile}.mol2'):
            os.system(f'rm {opfile}.mol2')
        return 0

def write_dockInput(id_smi, dockInput_template):
    '''Prepare the docking control script of glide'''
    dockInput_new_file = f'{id_smi[0]}.in'
    dockInput_new_f = open(dockInput_new_file, 'w')
    with open(dockInput_template, 'r') as dockInput_template_f:
        for line in dockInput_template_f.readlines():
            line_new = line.replace('$MaeFile', f'{str(id_smi[0])}.mae')
            # line_new = line_new.replace('$n_jobs', str(n_jobs))
            dockInput_new_f.write(line_new)
    dockInput_template_f.close()
    dockInput_new_f.close()
    return dockInput_new_file

# @func_set_timeout(100)
def dock(id_smi, dockInput_template,fast_flag=0):
    #### dock a single compound
    if 'sdf' in str(dockInput_template):
        suffix='pv.sdfgz'
    if 'mae' in str(dockInput_template):
        suffix='pv.maegz'
    if Path(f"{id_smi[0]}_{suffix}").exists():
        return f"{id_smi[0]}_{suffix}"
    else:
        mae_stat=smi_mae(id_smi,fast_flag=fast_flag)
        if mae_stat:
            dockInput_new_file = write_dockInput(id_smi, dockInput_template)
            print(f'dockInput_new_f= {dockInput_new_file}')
            os.system(f'{glide} -WAIT -OVERWRITE  -NOJOBID  {dockInput_new_file}')
            # clean the output
            tempFiles = [f"{id_smi[0]}.in", f"{id_smi[0]}.mae", f"{id_smi[0]}_raw.mae"]
            for ifile in tempFiles:
                try:
                    os.system(f'rm {ifile}')
                except Exception as e:
                    print(e)
                    continue 
            return f"{id_smi[0]}_{suffix}"
        else:
            return 0

def get_docking_score(imaegz):
    try:
        isimple_name = imaegz.replace('_pv.sdfgz', '')
        isimple_name=isimple_name.replace('_pv.maegz', '')
        report_file=f'{isimple_name}.rept'
        if not Path(report_file).exists():
            os.system(
                f'{glide_sort} -r {report_file} {imaegz} -o ./{isimple_name}.mae')
        with open(report_file, 'r') as report_file_f:
            parse_mark = 0
            dockScore_list = []
            for line in report_file_f.readlines():
                line_sp = line.strip().split()
                if parse_mark > 0 and len(line_sp) == 0:
                    break
                if len(line_sp) > 0:
                    if line_sp[0] == '====':
                        parse_mark += 1
                        continue
                    if len(line_sp) == 19 and parse_mark > 0:
                        dockScore_list.append([line_sp[0], line_sp[3], line_sp[1]])
        return dockScore_list        
    except:
        return [[0.0,0.0,0.0]]

def dock_score(id_smi, dockInput_template,fast_flag=0):
    '''The Dock results will be saved locally!'''
    try:
        maegz_file=dock(id_smi, dockInput_template,fast_flag=fast_flag)
    except Exception as e:
        print(e)
        return 0.0
    if maegz_file:
        score=get_docking_score(maegz_file)
        if len(score)>0:
            return score[0][1]
        else:
            return 0
    return 0.0

### Test of code 
if __name__ == "__main__":
    os.system('mkdir test')
    os.chdir('test')
    id_smi=['test','CC(C)C1C2C(NC=1C1C=C(OC)C3=NC=NN3C=1)=CC=C(N=2)C1CCC(CC1)N1CCCC1']
    dockInput_template='../TLR7_dock.in'
    d_score = dock_score(id_smi,dockInput_template)
    print(d_score)