''' Common import and functions  '''
import pandas as pd
import numpy as np
import seaborn as sns
from matplotlib import pyplot as plt
import os,sys
import re
import sqlite3
from glob import glob
from pathlib import Path
import rdkit
from rdkit import Chem, DataStructs
from rdkit.Chem import Descriptors, rdMolDescriptors, AllChem, QED
from rdkit.Chem import ChemicalFeatures
from my_toolset.my_utils import get_mol,canonic_smiles
from rdkit import RDConfig
from functools import partial
import numpy as np
import re
import argparse
import copy

def get_dummy_negb(atom):
    ''' Get the neighbor index of the dummy atom '''
    negb=atom.GetNeighbors()[0]
    return int(negb.GetIdx())

def bondLabel(smi):
    pattern = r"\*:\d"
    matches = re.findall(pattern, smi)
    for imatch in set(matches):
        imatch_sp=imatch.split(':')
        newLabel=f"{imatch_sp[1]}*"
        smi=smi.replace(imatch,newLabel)
    return smi

def connect_constVar(constSmi, varSmi, return_type='smiles'):
    ''' Connect single R group to the core
    '''
    comboSmi=constSmi+'.'+varSmi
    comboSmi=bondLabel(comboSmi)
    # print(comboSmi)
    combo_mol=get_mol(comboSmi)
    # var_mol=Chem.MolFromSmiles(varSmi)  # the isotope of dummy atom is zero
    # combo = Chem.CombineMols(const_mol, var_mol)
    match = combo_mol.GetSubstructMatches(Chem.MolFromSmarts('[#0]')) ## detect the dummy atoms
    # print(match)
    combo_atoms=combo_mol.GetAtoms()
    
    dummy_info=[[] for i in range(5)] # store the idx of connect dummy atoms
    for imatch in match: # look through all the dummy atoms
        atm_idx=imatch[0]
        isotope=combo_atoms[atm_idx].GetIsotope()
        dummy_negb=get_dummy_negb(combo_atoms[atm_idx])
        dummy_info[isotope].append([atm_idx,isotope,dummy_negb])
    #     if isotope in [0, Rsite]:
    #         dummy_pair.append(atm_idx)
    #         dummy_negb.append(get_dummy_negb(combo_atoms[atm_idx]))
    # print(dummy_info)
            
    edcombo = Chem.EditableMol(combo_mol)
    dummyAtoms=[]
    for idummyPair in dummy_info:
        if len(idummyPair)==2:
            edcombo.AddBond(idummyPair[0][2],idummyPair[1][2],order=Chem.rdchem.BondType.SINGLE) 
            dummyAtoms.append(idummyPair[0][0]) 
            dummyAtoms.append(idummyPair[1][0])  
    dummyAtoms.sort(reverse=True) 
    for idummy in dummyAtoms:
        edcombo.RemoveAtom(idummy)
    combo = edcombo.GetMol()
    ''' Replace dummy atom with hydrogen '''
    products = Chem.ReplaceSubstructs(combo,Chem.MolFromSmarts('[#0]'),Chem.MolFromSmarts('[#1]'),replaceAll=True)
    combo=products[0]
    combo_smi=Chem.MolToSmiles(combo)  ## To remove the hydrogen
    combo=Chem.MolFromSmiles(combo_smi) 
    combo=Chem.RemoveHs(combo)
    if return_type=='mol':
        return combo
    if return_type=='smiles':
        combo_smi=Chem.MolToSmiles(combo)
        # print(combo_smi)
        return combo_smi

def connect_constVar_try(constSmi, varSmi, return_type='smiles'):
    try:
        fullSmi=connect_constVar(constSmi, varSmi, return_type='smiles')
        return fullSmi
    except:
        return ''
    

def get_completeMol(rootFolder, overwrite=False, unique=False):
    if not overwrite and Path(f"{rootFolder}/generated_molecules_complete.csv").exists():
        print('COMBINE MOL EXIST, SKIP COMBINATION!')
        return
    dfGen=pd.read_csv(f"{rootFolder}/generated_molecules.csv")  ## load generated compounds
    for igen in range(1,10000):
        if f"Predicted_smi_{igen}" not in dfGen.columns:
            continue
        # ires=[]
        dfGen[f"Predicted_smi_{igen}"]=dfGen.apply(lambda x:connect_constVar_try(x['constantSMILES'],x[f"Predicted_smi_{igen}"]),axis=1)
    dfGen["Source_Mol"]=dfGen.apply(lambda x:connect_constVar_try(x['constantSMILES'],x['fromVarSMILES']),axis=1)
    dfGen["Target_Mol"]=dfGen.apply(lambda x:connect_constVar_try(x['constantSMILES'],x['toVarSMILES']),axis=1)
    dfGen.to_csv(f"{rootFolder}/generated_molecules_complete.csv", index=None)

    gen_list=[]
    for idx,irow in dfGen.iterrows():
        srcCPD=canonic_smiles(irow["Source_Mol"])
        Delta_pki=re.findall(r'(\d+(?:\.\d+)?)', irow["Delta_Value"])
        Delta_pki=[float(i) for i in Delta_pki]
        Delta_pki=np.array(Delta_pki).mean()
        for igen in range(1,10000):
            if f"Predicted_smi_{igen}" not in dfGen.columns:
                continue
            # ires=[]
            smi=irow[f"Predicted_smi_{igen}"]
            # sourceSmi=canonic_smiles(irow['Source_Mol'])
            if not pd.isna(smi):
                smi=canonic_smiles(smi)
                ires=[srcCPD,smi,Delta_pki]
                gen_list.append(ires)   
    dfRes=pd.DataFrame(gen_list, columns=["Source_Mol","Gen_Mol",'Delta_pki'])
    dfRes.sort_values(by="Delta_pki", ascending=False, inplace=True)
    dfRes=dfRes.reindex()
    if unique:
        dfRes.drop_duplicates(subset=['Gen_Mol'],inplace=True)
        print('removing dulplicated........')
    print(f"Total {len(dfRes)} molecules have been generated.")
    dfRes.sort_values(by="Delta_pki", ascending=False, inplace=True)
    dfRes.to_csv(f"{rootFolder}/generated_collection.csv", index=None)
    


def get_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rootFolder", help="the root folder to save the generated SMILES", required=True, default='')
    parser.add_argument('--overwrite',type=bool, default=False,help='whether overwrite exist file')
    parser.add_argument('--unique',type=bool, default=False,help='whether overwrite exist file')
    args = parser.parse_args()
    return args

if __name__ == '__main__':
    args = get_parser()

    get_completeMol(args.rootFolder, args.overwrite, args.unique)
