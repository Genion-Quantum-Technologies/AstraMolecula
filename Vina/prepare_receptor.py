#%%
''' Usage note:
input.csv     header: smiles,title

 '''
import argparse
import os,sys
from pathlib import Path
import pandas as pd
import numpy as np
import json
import __main__
__main__.pymol_argv = [ 'pymol', '-qc']
import pymol
from pymol import cmd, stored
pymol.finish_launching()

pyFilePath=Path(__file__).absolute()

jupyterMode=0

def print_var(var,note=''):
    print(f"{var}:  {eval(var)}   {note}")


class argNamespace:
    ''' for test in jupyter notebook  '''
    def __init__(self):  
        self.protein = '/mnt/public-bg6/jay.zhang/Codes-public/Vina/Test/8jzx.pdb'  # 'self'引用的是类实例自身  
        self.ligand = '/mnt/public-bg6/jay.zhang/Codes-public/Vina/Test/c5.pdb' 
        self.addH = 1


def main(args):
    ''' change the work directory  '''
    proteinPath=Path(args.protein).absolute()
    ligPath=Path(args.ligand).absolute()
    os.chdir(proteinPath.parent)
    # dfInput=pd.read_csv(args.input)
    if args.addH:
        addH_CMD=f"{pyFilePath.parent}/ADFRsuite/ADFRsuite_x86_64Linux_1.0/bin/reduce {proteinPath.name} > {proteinPath.stem}H.pdb"
        os.system(addH_CMD)
        prepareCMD=f"{pyFilePath.parent}/ADFRsuite/ADFRsuite_x86_64Linux_1.0/bin/prepare_receptor -r {proteinPath.stem}H.pdb -o {proteinPath.stem}.pdbqt"
    if not args.addH:
        prepareCMD=f"{pyFilePath.parent}/ADFRsuite/ADFRsuite_x86_64Linux_1.0/bin/prepare_receptor -r {proteinPath.stem}.pdb -o receptorVina.pdbqt"
    os.system(prepareCMD)

    ''' ligand center section  '''
    
    pymol.cmd.delete('all')
    pymol.cmd.load(ligPath,'lig')
    ligCenter=pymol.cmd.centerofmass('lig',quiet=0)
    vina_box=f"center_x = {ligCenter[0]}\ncenter_y = {ligCenter[1]}\nenter_z = {ligCenter[2]}\nsize_x = 25.0\nsize_y = 25.0\nsize_z = 25.0"
    with open('vina_box.txt','w') as file:
        file.writelines(vina_box)
    # Convert and write JSON object to file
    with open("vina_box.json", "w") as outfile: 
        json.dump({'center':ligCenter}, outfile, indent = 4)

def get_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("--protein", help="the path of protein file",
                        default='protein.pdb')
    parser.add_argument("--ligand", help="the path of ligand file to get the center of pocket",
                        default='ligand.pdb')
    parser.add_argument("--addH", help="if add hydrogen to receptor, default is true",default=1,type=int)

    args = parser.parse_args()
    return args

if jupyterMode:
    args=argNamespace()
    main(args)

# %%

if __name__ == "__main__":
    args = get_parser()
    main(args)
