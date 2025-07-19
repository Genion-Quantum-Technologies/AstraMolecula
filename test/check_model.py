# check_model.py
import torch
import sys

def check_model(path):
    try:
        checkpoint = torch.load(path, map_location="cpu")
    except Exception as exc:
        print(f"无法读取 {path}: {exc}")
        return

    required = {"model_parameters", "model_state_dict"}
    missing = required.difference(checkpoint.keys())

    if missing:
        print(f"{path} 加载成功，但缺少字段: {', '.join(missing)}")
    else:
        print(f"{path} 加载并包含所有必需字段，可能是有效模型。")
        print("包含的键:", list(checkpoint.keys()))


check_model("/Users/youngwild/Dev/jingyuan/dockingVina/resource/model_20.pt")
