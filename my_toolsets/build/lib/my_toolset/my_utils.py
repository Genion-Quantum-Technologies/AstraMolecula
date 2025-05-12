from __future__ import print_function

import math
import os.path as op
import pickle
from collections import Counter,UserList, defaultdict
from functools import partial
from tkinter import N
import numpy as np
import pandas as pd
import scipy.sparse
from rdkit import Chem, DataStructs
from rdkit.Chem import AllChem
from rdkit.Chem import rdMolDescriptors
#from rdkit.six import iteritems
from rdkit.Chem.QED import qed
from rdkit.Chem.Scaffolds import MurckoScaffold
from rdkit.Chem import Descriptors
from rdkit.Chem import MACCSkeys
from rdkit.Chem import Draw
from rdkit.Chem.AllChem import GetMorganFingerprintAsBitVect as Morgan
from multiprocessing import Pool
from rdkit.Chem.Pharm2D import Generate
from .pharmacophore import factory
from rdkit.Chem import GetDistanceMatrix
from rdkit.Chem.Descriptors import MolWt
from rdkit.Chem.Lipinski import NumHAcceptors, NumHDonors, NumRotatableBonds
from rdkit.Chem.MolSurf import TPSA
from rdkit.Chem.rdMolDescriptors import CalcNumRings, CalcNumAtomStereoCenters, CalcNumAromaticRings, \
    CalcNumAliphaticRings
from rdkit.Chem.Crippen import MolLogP
from tqdm.auto import tqdm
from rdkit.ML.Cluster import Butina

_fscores = None
##### Calculate systhesize score
def strip_pose(idx, keep_num=2):
    idx_nopose = ''
    idx_sp = idx.split("_")
    for itm in range(keep_num):
        if idx_nopose == '':
            idx_nopose = idx_sp[itm]
        else:
            idx_nopose += f'_{idx_sp[itm]}'
    return idx_nopose

def readFragmentScores(name='fpscores'):
    import gzip
    global _fscores
    # generate the full path filename:
    if name == "fpscores":
        name = op.join(op.dirname(__file__), name)
    _fscores = pickle.load(gzip.open('%s.pkl.gz' % name))
    outDict = {}
    for i in _fscores:
        for j in range(1, len(i)):
            outDict[i[j]] = float(i[0])
    _fscores = outDict

def numBridgeheadsAndSpiro(mol, ri=None):
    nSpiro = rdMolDescriptors.CalcNumSpiroAtoms(mol)
    nBridgehead = rdMolDescriptors.CalcNumBridgeheadAtoms(mol)
    return nBridgehead, nSpiro

def calculateScore(m):
    if _fscores is None:
        readFragmentScores()

    # fragment score
    fp = rdMolDescriptors.GetMorganFingerprint(
        m, 2  # <- 2 is the *radius* of the circular fingerprint
    )
    fps = fp.GetNonzeroElements()
    score1 = 0.
    nf = 0
    for bitId, v in iteritems(fps):
        nf += v
        sfp = bitId
        score1 += _fscores.get(sfp, -4) * v
    score1 /= nf

    # features score
    nAtoms = m.GetNumAtoms()
    nChiralCenters = len(Chem.FindMolChiralCenters(m, includeUnassigned=True))
    ri = m.GetRingInfo()
    nBridgeheads, nSpiro = numBridgeheadsAndSpiro(m, ri)
    nMacrocycles = 0
    for x in ri.AtomRings():
        if len(x) > 8:
            nMacrocycles += 1

    sizePenalty = nAtoms ** 1.005 - nAtoms
    stereoPenalty = math.log10(nChiralCenters + 1)
    spiroPenalty = math.log10(nSpiro + 1)
    bridgePenalty = math.log10(nBridgeheads + 1)
    macrocyclePenalty = 0.
    # ---------------------------------------
    # This differs from the paper, which defines:
    #  macrocyclePenalty = math.log10(nMacrocycles+1)
    # This form generates better results when 2 or more macrocycles are present
    if nMacrocycles > 0:
        macrocyclePenalty = math.log10(2)

    score2 = (0. - sizePenalty - stereoPenalty -
              spiroPenalty - bridgePenalty - macrocyclePenalty)

    # correction for the fingerprint density
    # not in the original publication, added in version 1.1
    # to make highly symmetrical molecules easier to synthetise
    score3 = 0.
    if nAtoms > len(fps):
        score3 = math.log(float(nAtoms) / len(fps)) * .5

    sascore = score1 + score2 + score3

    # need to transform "raw" value into scale between 1 and 10
    min = -4.0
    max = 2.5
    sascore = 11. - (sascore - min + 1) / (max - min) * 9.
    # smooth the 10-end
    if sascore > 8.:
        sascore = 8. + math.log(sascore + 1. - 9.)
    if sascore > 10.:
        sascore = 10.0
    elif sascore < 1.:
        sascore = 1.0

    return sascore

def get_mol(smiles_or_mol):
    '''
    Loads SMILES/molecule into RDKit's object
    '''
    if isinstance(smiles_or_mol, str):
        if len(smiles_or_mol) == 0:
            return None
        mol = Chem.MolFromSmiles(smiles_or_mol)
        if mol is None:
            return None
        try:
            Chem.SanitizeMol(mol)
        except ValueError:
            return None
        return mol
    return smiles_or_mol

def canonic_smiles(smiles_or_mol):
    try:
        mol = get_mol(smiles_or_mol)    
        if mol is None:
            return None
        return Chem.MolToSmiles(mol,isomericSmiles=False)
    except Exception as e:
        print(e)
        return None

def SA(smiles_or_mol):
    """
    Computes RDKit's Synthetic Accessibility score
    """
    mol = get_mol(smiles_or_mol)
    if mol is None:
        return None
    return calculateScore(mol)

def QED(smiles_or_mol):
    """
    Computes RDKit's QED score
    """
    mol = get_mol(smiles_or_mol)
    if mol is None:
        return None
    return qed(mol)


def weight(smiles_or_mol):
    """
    Computes molecular weight for given molecule.
    Returns float,
    """
    mol = get_mol(smiles_or_mol)
    if mol==None:
        return 0
    return Descriptors.MolWt(mol)

def slog_p(smiles_or_mol) -> float:
        mol = get_mol(smiles_or_mol)
        if mol==None:
            return 0
        return MolLogP(mol)

def get_n_rings(mol):
    """
    Computes the number of rings in a molecule
    """
    return mol.GetRingInfo().NumRings()


def fragmenter(mol):
    """
    fragment mol using BRICS and return smiles list
    """
    fgs = AllChem.FragmentOnBRICSBonds(get_mol(mol))
    fgs_smi = Chem.MolToSmiles(fgs).split(".")
    return fgs_smi


def compute_fragments(mol_list, n_jobs=1):
    """
    fragment list of mols using BRICS and return smiles list
    """
    fragments = Counter()
    for mol_frag in mapper(n_jobs)(fragmenter, mol_list):
        fragments.update(mol_frag)
    return fragments


def compute_scaffolds(mol_list, n_jobs=1, min_rings=2):
    """
    Extracts a scafold from a molecule in a form of a canonic SMILES
    """
    # scaffolds = Counter()
    map_ = mapper(n_jobs)
    scaffolds =  map_(partial(compute_scaffold, min_rings=min_rings), mol_list)
    # if None in scaffolds:
    #     scaffolds.pop(None)
    return scaffolds

def counter_to_df(counter):
    scalf_list=[]
    for key in counter.keys():
        scalf_list.append([key, counter[key]])
    df=pd.DataFrame(scalf_list, columns=['SMILES','Count'])
    return df

def df_valid(df, row_smi='SMILES'):
    valid_idx=[idx for idx, row in df.iterrows() if canonic_smiles(row[row_smi])!=None]
    df_valid=df.loc[valid_idx]
    return df_valid

def ClusterFps(fps,cutoff=0.2):
    # first generate the distance matrix:
    dists = []
    nfps = len(fps)
    for i in range(1,nfps):
        sims = DataStructs.BulkTanimotoSimilarity(fps[i],fps[:i])
        dists.extend([1-x for x in sims])
    # now cluster the data:
    cs = Butina.ClusterData(dists,nfps,cutoff,isDistData=True)
    return cs

def save_svg(png_svg, svg_file):
    png=png_svg[0]
    svg=png_svg[1]
    with open(svg_file, 'w') as f:
        f.write(svg)
    # renderPDF.drawToFile(drawing, f"{svg_file.replace('.svg')}+'.pdf'")
    # renderPM.drawToFile(drawing, svg_file.replace('.svg','')+'.png', fmt="PNG")
    # plot=plt.imshow(png.data)
    # with open(svg_file.replace('.svg','')+'.png', 'wb+') as f:
    #     f.write(png)
    png.save(svg_file.replace('.svg','')+'.png')

def draw_smis(smis, svg_file):
    ## svg_file with suffix as .svg
    mols=[get_mol(ismi) for ismi in smis if get_mol(ismi)!=None]
    svg=Draw.MolsToGridImage(mols,subImgSize=(300,150),molsPerRow=4,useSVG=True)
    png=Draw.MolsToGridImage(mols,subImgSize=(300,150),molsPerRow=4,useSVG=False)
    save_svg([png,svg], svg_file)


def compute_FP(mol, radius=2, nBits=1024):
    mol = get_mol(mol)
    FP = AllChem.GetMorganFingerprintAsBitVect(
        mol, radius, nBits=nBits)
    return FP

def compute_scaffold(mol, min_rings=2):
    mol = get_mol(mol)
    try:
        scaffold = MurckoScaffold.GetScaffoldForMol(mol)
    except (ValueError, RuntimeError):
        return None
    n_rings = get_n_rings(scaffold)
    scaffold_smiles = Chem.MolToSmiles(scaffold)
    if scaffold_smiles == '' or n_rings < min_rings:
        return None
    return scaffold_smiles

def compute_sim(smi, smi_list, mode='smi-smis'):
    if mode=='smi-smis':
        mol1 = Chem.MolFromSmiles(smi)
        FP1 = AllChem.GetMorganFingerprintAsBitVect(
        mol1, 2, nBits=1024)
        mols = [Chem.MolFromSmiles(ismi)
            for ismi in smi_list]
        FPs = [AllChem.GetMorganFingerprintAsBitVect(
        imol, 2, nBits=1024) for imol in mols]
    if mode=='smi-FPs':
        mol1 = Chem.MolFromSmiles(smi)
        FP1 = AllChem.GetMorganFingerprintAsBitVect(
        mol1, 2, nBits=1024)
        FPs=smi_list
    molSims = [DataStructs.TanimotoSimilarity(
                FP, FP1) for FP in FPs]
    return molSims

def remove_invalid(smi_list):
    valid_smis=[]
    for ismi in smi_list:
        try:
            mol=Chem.MolFromSmiles(ismi)
            if mol != None:
                valid_smis.append(ismi)
        except Exception as e:
            continue
    print(f'Total: {len(smi_list)} Valid: {len(valid_smis)}')
    return valid_smis

def fingerprints_from_mols(mols, desc_type):
    if desc_type == 'Trust':
        fps = [Generate.Gen2DFingerprint(mol, factory) for mol in mols]
        size = 4096
        X = np.zeros((len(mols), size))
        for i, fp in enumerate(fps):
            for k, v in fp.GetNonzeroElements().items():
                idx = k % size
                X[i, idx] = v
        return X
    elif desc_type == 'ECFP6_c':
        fps = [
            AllChem.GetMorganFingerprint(
                mol,
                3,
                useCounts=True,
                useFeatures=True,
            ) for mol in mols
        ]
        size = 2048
        nfp = np.zeros((len(fps), size), np.int32)
        for i, fp in enumerate(fps):
            for idx, v in fp.GetNonzeroElements().items():
                nidx = idx % size
                nfp[i, nidx] += int(v)
        return nfp
    elif desc_type == 'ECFP6':
        fps = [
            AllChem.GetMorganFingerprintAsBitVect(mol, 3, nBits=2048)
            for mol in mols
        ]
        size = 2048
        nfp = np.zeros((len(fps), size), np.int32)
        for i, fp in enumerate(fps):
            for idx, v in enumerate(fp):
                nfp[i, idx] = v
        return nfp

def mapper(n_jobs):
    '''
    Returns function for map call.
    If n_jobs == 1, will use standard map
    If n_jobs > 1, will use multiprocessing pool
    If n_jobs is a pool object, will return its map function
    '''
    if n_jobs == 1:
        def _mapper(*args, **kwargs):
            return list(map(*args, **kwargs))

        return _mapper
    if isinstance(n_jobs, int):
        pool = Pool(n_jobs)

        def _mapper(*args, **kwargs):
            try:
                result = pool.map(*args, **kwargs)
            finally:
                pool.terminate()
            return result

        return _mapper
    return n_jobs.map

def imapper(n_jobs):
    '''
    Returns function for map call.
    If n_jobs == 1, will use standard map
    If n_jobs > 1, will use multiprocessing pool
    If n_jobs is a pool object, will return its map function
    '''
    if n_jobs == 1:
        def _mapper(*args, **kwargs):
            return list(map(*args, **kwargs))
        return _mapper

    if isinstance(n_jobs, int):
        pool = Pool(n_jobs)
        def _mapper(*args,**kwargs):
            try:
                result = [x for x in tqdm(
            pool.imap(*args, kwargs['input']),
            total=len(kwargs['input']),
            miniters=n_jobs)]
            finally:
                pool.terminate()
            return result
        return _mapper
    return n_jobs.map

def read_txt(fname, cols=[], ftype='csv',header_pass=False):
    res_list=''
    with open(fname, "r") as f:
        if header_pass:
            next(f)
        for line in f:
            if ftype=='csv':
                fields = line.split(',')
            else:
                fields = line.split()
            if res_list=='':
                res_list=[[]]*len(fields)
            for icol in cols:
                res_list[icol].append(fields[icol])
    return res_list

class PhysChemDescriptors:
    """Molecular descriptors.
    The descriptors in this class are mostly calculated RDKit phys-chem properties.
    """

    def maximum_graph_length(self, mol) -> int:
        mol = get_mol(mol)
        if mol==None:
            return 0
        return int(np.max(GetDistanceMatrix(mol)))

    def hba_libinski(self, mol) -> int:
        mol = get_mol(mol)
        if mol==None:
            return 0
        return NumHAcceptors(mol)

    def hbd_libinski(self, mol) -> int:
        mol = get_mol(mol)
        if mol==None:
            return 0
        return NumHDonors(mol)

    def mol_weight(self, mol) -> float:
        mol = get_mol(mol)
        if mol==None:
            return 0
        return MolWt(mol)

    def number_of_rings(self, mol) -> int:
        mol = get_mol(mol)
        if mol==None:
            return 0
        return CalcNumRings(mol)

    def number_of_aromatic_rings(self, mol) -> int:
        mol = get_mol(mol)
        if mol==None:
            return 0
        return CalcNumAromaticRings(mol)

    def number_of_aliphatic_rings(self, mol) -> int:
        mol = get_mol(mol)
        if mol==None:
            return 0
        return CalcNumAliphaticRings(mol)

    def number_of_rotatable_bonds(self, mol) -> int:
        mol = get_mol(mol)
        if mol==None:
            return 0
        return NumRotatableBonds(mol)

    def slog_p(self, mol) -> float:
        mol = get_mol(mol)
        if mol==None:
            return 0
        return MolLogP(mol)

    def tpsa(self, mol) -> float:
        mol = get_mol(mol)
        if mol==None:
            return 0
        return TPSA(mol)
    
    def sa(self, mol) -> float:
        mol = get_mol(mol)
        if mol==None:
            return 0
        return SA(mol)
    
    def qed(self, mol) -> float:
        mol = get_mol(mol)
        if mol==None:
            return 0
        return qed(mol)

    def number_of_stereo_centers(self, mol) -> int:
        mol = get_mol(mol)
        if mol==None:
            return 0
        return CalcNumAtomStereoCenters(mol)

    def number_atoms_in_largest_ring(self, mol) -> int:
        mol = get_mol(mol)
        if mol==None:
            return 0
        ring_info = mol.GetRingInfo()
        ring_size = [len(ring) for ring in ring_info.AtomRings()]
        max_ring_size = max(ring_size) if ring_size else 0
        return int(max_ring_size)
    
def valid_index(smi_list):
    valid_mol_indices=[]
    for idx, ismi in enumerate(smi_list):
        mol = get_mol(ismi)
        if mol!=None:
            valid_mol_indices.append(idx)
    return valid_mol_indices
