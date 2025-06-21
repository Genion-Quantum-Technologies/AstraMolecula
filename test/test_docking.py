import requests
import json
from pathlib import Path

BASE_URL = "http://127.0.0.1:8000"
USERNAME = "bob"
PASSWORD = "Pa$$w0rd123"

def get_token() -> str:
    """先登录拿到 JWT"""
    payload = {"username": USERNAME, "password": PASSWORD}
    resp = requests.post(
        f"{BASE_URL}/login",
        headers={"Content-Type": "application/json"},
        data=json.dumps(payload)
    )
    if resp.status_code != 200:
        print(f"❌ 登录失败 [{resp.status_code}]:", resp.text)
        return ""
    token = resp.json().get("access_token", "")
    print("✅ 登录成功，token:", token)
    return token

def test_docking_with_uploaded_receptor():
    print("Testing /docking with uploaded receptor 'user1.pdbqt' …")
    token = get_token()
    if not token:
        return

    # 构造 Ligand 列表
    ligands = [
        {"smiles": "C=CCNC(=O)CSC1=NC(=C(O1)C2=CC=CC=C2)C3=CC=CC=C3", "title": "LIG1"},
        {"smiles": "COCCN(CC1=NC2=C(C=CC=C2)C(=O)N1)C(=O)C3=C(C)C4=C(O3)C=CC(F)=C4", "title": "LIG2"},
    ]

    # 设置 query 参数指定之前上传的 user1.pdbqt
    params = {"receptor_filename": "user1.pdbqt"}

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # 发起请求
    resp = requests.post(
        f"{BASE_URL}/docking",
        headers=headers,
        params=params,
        data=json.dumps({
            "ligands": ligands,
            # 可选：覆盖默认 pH 范围和线程数
            # "min_ph": 6.0,
            # "max_ph": 8.0,
            # "n_jobs": 4
        }),
        timeout=600
    )

    if resp.status_code == 200:
        result = resp.json()
        print("✅ Docking 成功，run_id:", result.get("run_id"))
        print("Results:")
        for idx, row in enumerate(result.get("results", []), start=1):
            print(f"  {idx}. title={row.get('title')}, score={row.get('score')}, file={row.get('file')}")
    else:
        print(f"❌ Docking 失败 [{resp.status_code}]:", resp.text)

if __name__ == "__main__":
    test_docking_with_uploaded_receptor()
