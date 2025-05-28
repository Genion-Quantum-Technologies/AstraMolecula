import requests
import json

# 你的 FastAPI 服务运行地址（假设运行在本地端口 8000）
BASE_URL = "http://127.0.0.1:8000"

# 示例 SMILES 字符串
test_smiles = "CC(=O)Nc1cc(-c2cc(F)cc(OC3CCN(C)C3)c2)nc(-n2nc(C)cc2C)n1"

def test_fragmentize():
    print("Testing /fragmentize...")
    params = {"smiles": test_smiles}
    response = requests.get(f"{BASE_URL}/fragmentize", params=params)
    if response.ok:
        print("Fragmentize response:")
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))
    else:
        print("Error:", response.status_code, response.text)



def test_generate():
    print("Testing /generate...")
    payload = {
        "constSmiles": "c1ccccc1",       # 示例 constant fragment
        "varSmiles": "C=O",              # 示例 variable fragment
        "mainCls": "class1",             # 可根据你的模型设定填入有效类名
        "minorCls": "subclassA",
        "deltaValue": "1.0",             # 示例 delta
        "num": 2                         # 生成的数量
    }
    headers = {"Content-Type": "application/json"}
    response = requests.post(f"{BASE_URL}/generate", headers=headers, data=json.dumps(payload))
    if response.ok:
        print("Generate response:")
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))
    else:
        print("Error:", response.status_code, response.text)


if __name__ == "__main__":
    test_fragmentize()
    print("\n" + "="*50 + "\n")
    # test_generate()
