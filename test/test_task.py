import requests
import json

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

def check_result_with_id(task_id:str):
    print("Testing /docking with uploaded receptor 'user1.pdbqt' …")
    token = get_token()
    if not token:
        return

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
                    with open("result.zip", "wb") as f:
                        f.write(down.content)
                    print("✅ 文件已保存到当前目录下的 result.zip")
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

if __name__ == "__main__":
    check_result_with_id("34901446a2674d139a406ebdb7587330")