
from pathlib import Path
from pydantic import BaseModel
import pandas as pd
from rdkit import Chem
from rdkit.Chem import Descriptors, QED, Draw
from typing import List, Optional
import io
# 你的其他 imports 保持不变 … 
from utils.generate import GenerateRunner
from utils.dataset import Dataset
from utils.combine_mol import connect_constVar_try
import torch
import utils.sascorer as sascorer


class Options:
    def __init__(self, **entries):
        self.__dict__.update(entries)

# ============================================
# 2. 一些已有的工具函数（calculate_descriptors, run_generate_runner 等）
# ============================================
def calculate_descriptors(smiles):
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    
    molwt = round(Descriptors.MolWt(mol), 1)
    tpsa = round(Descriptors.TPSA(mol), 1)
    slogp = round(Descriptors.MolLogP(mol), 1)
    sa    = round(sascorer.calculateScore(mol), 1)
    qed_v = round(QED.qed(mol), 1)

    # 检查除法前是否为 0
    some_ratio = None
    if tpsa != 0:
        some_ratio = molwt / tpsa

    return {"molwt": molwt, "tpsa": tpsa, "slogp": slogp, "sa": sa, "qed": qed_v}

def run_generate_runner(const_smiles, var_smiles, main_cls, minor_cls, delta_value, num_samples):
    from config import ROOT
    
    opt = {
        'batch_size': num_samples,
        'data_path' :  str(ROOT),
        'decode_type' :  'multinomial',
        'dev_no' :  0,
        'epoch' :  20,
        'model_choice' :  'transformer',
        'model_path' :  str(ROOT / 'resource'),
        'num_samples' :  50,
        'overwrite' :  True,
        'test_file_name' :  'test_cut',
        'vocab_path' :  str(ROOT / 'resource')
    }
    opt = Options(**opt)
    runner = GenerateRunner(opt)

    data = {
        "constantSMILES": const_smiles,
        "fromVarSMILES": var_smiles,
        "main_cls": main_cls,
        "minor_cls": minor_cls,
        "Delta_Value": delta_value
    }
    test_data = pd.DataFrame([data])
    dataset = Dataset(test_data, vocabulary=runner.vocab, tokenizer=runner.tokenizer, prediction_mode=True)
    dataloader = torch.utils.data.DataLoader(dataset, batch_size=num_samples, shuffle=False, collate_fn=Dataset.collate_fn)
    result = []

    for batch in dataloader:
        src, source_length, _, src_mask, _, _, df = batch
        src = src.to(runner.device)
        src_mask = src_mask.to(runner.device)
        source_length = source_length.to(runner.device)
        smiles_list = runner.sample(
            model_choice="transformer", 
            model=runner.model, 
            src=src, 
            src_mask=src_mask, 
            source_length=source_length, 
            decode_type="multinomial", 
            num_samples=num_samples
        )
        for smiles_group in smiles_list:
            for smile in smiles_group:
                newsmile = connect_constVar_try(const_smiles, smile)
                descriptors = calculate_descriptors(newsmile)
                if descriptors:
                    result.append({
                        "smile": newsmile,
                        "molwt": descriptors['molwt'],
                        "tpsa": descriptors['tpsa'],
                        "slogp": descriptors['slogp'],
                        "sa": descriptors['sa'],
                        "qed": descriptors['qed']
                    })
    return result


def validate_pdbqt_format(pdbqt_text: str) -> List[str]:
    """
    验证 .pdbqt 文件内容是否符合 Vina 所需的基本格式。
    返回错误信息列表，若为空则表示格式合格。
    """
    errors = []

    # 检查关键结构关键词是否存在
    required_keywords = ["ROOT", "ENDROOT", "TORSDOF"]
    for keyword in required_keywords:
        if keyword not in pdbqt_text:
            errors.append(f"缺少关键字: {keyword}")

    # 检查至少存在一个 ATOM 或 HETATM 行
    if not any(line.startswith(("ATOM", "HETATM")) for line in pdbqt_text.splitlines()):
        errors.append("缺少 ATOM 或 HETATM 行（原子坐标信息）")

    # 检查是否存在坐标列（粗略判断是否包含 X Y Z 信息）
    for line in pdbqt_text.splitlines():
        if line.startswith(("ATOM", "HETATM")):
            try:
                float(line[30:38])  # X
                float(line[38:46])  # Y
                float(line[46:54])  # Z
            except ValueError:
                errors.append("存在无法解析的原子坐标行")
                break

    return errors
