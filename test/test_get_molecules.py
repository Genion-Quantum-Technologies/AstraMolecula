# test_get_molecules.py

import sys
import json
import requests

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

def test_get_generated_molecules(task_id: str):
    """
    调用 /tasks/{task_id}/molecules 接口，获取并打印生成的分子列表。
    """
    token = get_token()
    if not token:
        return

    url = f"{BASE_URL}/tasks/{task_id}/molecules"
    headers = {"Authorization": f"Bearer {token}"}

    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        molecules = resp.json()
        print(f"[✔] 共返回 {len(molecules)} 条分子结果：")
        for idx, m in enumerate(molecules, 1):
            print(
                f"{idx}. smile={m['smile']}, "
                f"molwt={m['molwt']}, "
                f"tpsa={m['tpsa']}, "
                f"slogp={m['slogp']}, "
                f"sa={m['sa']}, "
                f"qed={m['qed']}"
            )
    else:
        print(f"[✖] 请求失败 [{resp.status_code}]:", resp.text)

if __name__ == "__main__":
    test_get_generated_molecules("37250d1e5b674ab4b83c5888824dc122")
