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



def test_docking_api():
    # 1. 定义要发送的 Ligand 数据（对应 CSV 中的 smiles, title）
    ligands = [
        {
            "smiles": "C=CCNC(=O)CSC1=NC(=C(O1)C2=CC=CC=C2)C3=CC=CC=C3",
            "title":  "NCGC00280631-03"
        },
        {
            "smiles": "COCCN(CC1=NC2=C(C=CC=C2)C(=O)N1)C(=O)C3=C(C)C4=C(O3)C=CC(F)=C4",
            "title":  "NCGC00280769-03"
        },
        {
            "smiles": "CC(NC(=O)C1CCN(CC1)C(=O)C2=C3C=CC=CC3=CC=C2)C4=CC=CC=C4",
            "title":  "NCGC00300872-03"
        }
    ]

    # 2. 构造要发送的 JSON payload
    payload = {
        "ligands": ligands,
        # 下面三项可以省略，使用服务端默认值 (6.0, 8.0, 10)
        # "min_ph": 6.0,
        # "max_ph": 8.0,
        # "n_jobs": 10
    }

    # 3. API 服务地址（根据你实际部署的地址及端口修改）
    API_URL = "http://localhost:8000/docking"

    try:
        # 4. 发送 POST 请求
        headers = {"Content-Type": "application/json"}
        response = requests.post(API_URL, headers=headers, data=json.dumps(payload), timeout=600)

        # 5. 检查响应状态码
        if response.status_code != 200:
            print(f"Error: HTTP {response.status_code}")
            print("Response body:", response.text)
            return

        # 6. 解析并打印返回的 JSON 结果
        result = response.json()
        print("Run ID:", result.get("run_id"))
        print("Docking Results:")
        for idx, row in enumerate(result.get("results", []), start=1):
            title = row.get("title")
            pose  = row.get("pose")
            score = row.get("score")
            smiles= row.get("smiles")
            file  = row.get("file")
            print(f"  {idx}. title={title}, pose={pose}, score={score}, smiles={smiles}, file={file}")

    except requests.exceptions.RequestException as e:
        print("Request failed:", str(e))

if __name__ == "__main__":
    # test_fragmentize()
    # print("\n" + "="*50 + "\n")
    # test_generate()
    test_docking_api()
