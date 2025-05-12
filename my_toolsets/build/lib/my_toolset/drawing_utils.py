import pandas as pd
import numpy as np
from rdkit.Chem import AllChem,Draw,rdFMCS
from rdkit import Chem, DataStructs
from rdkit.Chem.Draw import rdDepictor
from svglib.svglib import svg2rlg
from reportlab.graphics import renderPDF, renderPM
import matplotlib.pyplot as plt
import seaborn as sns
from .my_utils import get_mol
import warnings
warnings.filterwarnings('ignore')

def view_difference(mol1, mol2,legends):
    mol1=get_mol(mol1)
    mol2=get_mol(mol2)
    mcs = rdFMCS.FindMCS([mol1,mol2])
    mcs_mol = Chem.MolFromSmarts(mcs.smartsString)
    match1 = mol1.GetSubstructMatch(mcs_mol)
    target_atm1 = []
    for atom in mol1.GetAtoms():
        if atom.GetIdx() not in match1:
            target_atm1.append(atom.GetIdx())
    match2 = mol2.GetSubstructMatch(mcs_mol)
    target_atm2 = []
    for atom in mol2.GetAtoms():
        if atom.GetIdx() not in match2:
            target_atm2.append(atom.GetIdx())
    
    png=Draw.MolsToGridImage([mol1, mol2],subImgSize=(300,300),useSVG=False,highlightAtomLists=[target_atm1, target_atm2],legends=legends)
    # svg=Draw.MolsToGridImage([mol1, mol2],subImgSize=(300,300), useSVG=True,highlightAtomLists=[target_atm1, target_atm2],legends=legends)
    svg=''
    return (png,svg)

def save_svg(png_svg, svg_file, ipython=False):
    '''Save the png and svg to file
    - png_svg  [png,svg]
    - svg_file  file_name.svg
    - ipython In ipython something interesting is heppening!
    '''
    if ipython:
        png=png_svg[0].data
        svg=png_svg[1].data
    else:
        png=png_svg[0]#.data
        svg=png_svg[1]#.data
    with open(svg_file, 'w') as f:
        f.write(svg)
    # drawing = svg2rlg(svg_file)
    # renderPDF.drawToFile(drawing, f"{svg_file.replace('.svg')}+'.pdf'")
    # renderPM.drawToFile(drawing, svg_file.replace('.svg','')+'.png', fmt="PNG")
    # plot=plt.imshow(png.data)
    if ipython:
        with open(svg_file.replace('.svg','')+'.png', 'wb+') as f:
            f.write(png)
    else:
        png.save(svg_file.replace('.svg','')+'.png')

def show_mols(smiles_mols,legends=[],subImgSize=(800,600)):
    '''Display multiple mols with legends'''
    mols=[get_mol(ismiles_mol) for ismiles_mol in smiles_mols]
    mol_cls,legends_cls=[],[]
    for i in range(len(mols)):
        if mols[i]==None:
            continue
        mol_cls.append(mols[i])
        if len(legends)>i:
            legends_cls.append(legends[i])
        else:
            legends_cls.append('')
    svg=Draw.MolsToGridImage(mol_cls,subImgSize=subImgSize, molsPerRow=3,useSVG=True,legends=legends_cls)
    png=Draw.MolsToGridImage(mol_cls,subImgSize=subImgSize,useSVG=False,molsPerRow=3,legends=legends_cls)
    return png,svg

def plot_xy(x,y,x_label='',y_label='',save_file=''):
    '''Plot x-y graph'''
    plt.figure(figsize=(7, 4.5), dpi=500)
    plt.rc('font', family='Times New Roman', size=12, weight='bold')
    plt.plot(x,y)
    plt.xlabel(x_label)
    plt.ylabel(y_label)
    if save_file!='':
        plt.savefig(save_file, dpi=500)
    plt.show()
      
def scatter_xy(x,y,x_label='',y_label='',save_file='', xlims=None, ylims=None):
    '''Plot x-y graph'''
    plt.figure(figsize=(7, 4.5), dpi=500)
    plt.rc('font', family='Times New Roman', size=12, weight='bold')
    plt.scatter(x,y)
    plt.xlabel(x_label)
    plt.ylabel(y_label)
    if xlims != None:
        plt.xlim(xlims[0],xlims[1])
    if ylims != None:
        plt.ylim(ylims[0],ylims[1])
    if save_file!='':
        plt.savefig(save_file, dpi=500)
    plt.show()

def plot_density(x,x_label='',y_label='Density (%)',save_file=''):
    '''Plot x-y graph'''
    plt.figure(figsize=(7, 4.5), dpi=500)
    plt.rc('font', family='Times New Roman', size=12, weight='bold')
    sns.displot(x, stat="density")
    plt.xlabel(x_label)
    plt.ylabel(y_label)
    if save_file!='':
        plt.savefig(save_file, dpi=500)
    plt.show()