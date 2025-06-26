# test_list_user_tasks.py

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

def test_list_user_tasks():
    """
    调用 /tasks/list_user_tasks 接口，打印当前用户的所有任务列表。
    """
    token = get_token()
    if not token:
        return

    url = f"{BASE_URL}/tasks/"
    headers = {"Authorization": f"Bearer {token}"}

    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        tasks = resp.json()
        print(f"[✔] 共返回 {len(tasks)} 个任务：")
        for idx, t in enumerate(tasks, 1):
            print(f"  {idx}. id={t['id']}, type={t['task_type']}, status={t['status']}, created_at={t['created_at']}")
    else:
        print(f"[✖] 请求失败 [{resp.status_code}]:", resp.text)

if __name__ == "__main__":
    test_list_user_tasks()
