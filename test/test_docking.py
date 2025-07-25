import requests
import json
from pathlib import Path

BASE_URL = "http://127.0.0.1:8000"
# USERNAME = "bob"
# PASSWORD = "Pa$$w0rd123"
USERNAME = "admin"
PASSWORD = "Admin#2024"
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
    params = {"receptor_filename": "user2.pdbqt"}

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
            # 对接盒子参数
            "center_x": 61.105,
            "center_y": 24.325,
            "center_z": 17.161,
            "box_size_x": 20.0,
            "box_size_y": 25.0,
            "box_size_z": 30.0,
            # 可选：覆盖默认 pH 范围和线程数
            # "min_ph": 6.0,
            # "max_ph": 8.0,
            # "n_jobs": 4
        }),
        timeout=600
    )

    if resp.status_code == 200:
        result = resp.json()
        task_id = result.get("task_id")
        print("✅ 任务已加入队列，task_id:", task_id)
        if task_id:
            res = requests.get(
                f"{BASE_URL}/tasks/{task_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
            if res.ok:
                status = res.json().get("status")
                print("Task status:", status)
                if status == "finished":
                    down = requests.get(
                        f"{BASE_URL}/tasks/{task_id}/download",
                        headers={"Authorization": f"Bearer {token}"},
                    )
                    if down.ok:
                        print("Download size:", len(down.content))
                    else:
                        print(
                            f"❌ 下载结果失败 [{down.status_code}]",
                            down.text,
                        )
            else:
                print(
                    f"❌ 查询任务失败 [{res.status_code}]",
                    res.text,
                )
    else:
        print(f"❌ Docking 失败 [{resp.status_code}]:", resp.text)

if __name__ == "__main__":
    test_docking_with_uploaded_receptor()