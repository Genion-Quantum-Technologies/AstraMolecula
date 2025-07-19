# test_get_dock_results.py

import sys
import json
import requests

BASE_URL = "http://127.0.0.1:8000"
USERNAME = "admin"
PASSWORD = "admin123"

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

def test_get_dock_results(task_id: str):
    """
    调用 /tasks/{task_id}/dockRes 接口，获取并打印对接结果列表。
    """
    token = get_token()
    if not token:
        return

    url = f"{BASE_URL}/tasks/{task_id}/dockRes"
    headers = {"Authorization": f"Bearer {token}"}

    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        results = resp.json()
        print(f"[✔] 共返回 {len(results)} 条对接结果：")
        for idx, r in enumerate(results, 1):
            print(
                f"{idx}. title={r['title']}, "
                f"pose={r['pose']}, "
                f"score={r['score']}, "
                f"smiles={r['smiles']}, "
                f"file={r['file']}"
            )
    else:
        print(f"[✖] 请求失败 [{resp.status_code}]:", resp.text)

if __name__ == "__main__":
    test_get_dock_results("fa8d93436f93443d872e2a210b597f1c")
