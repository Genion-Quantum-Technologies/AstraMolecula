import requests
import json

# 你的 FastAPI 服务运行地址（假设运行在本地端口 8000）
BASE_URL = "http://127.0.0.1:8000"

# 示例 SMILES 字符串
test_smiles = "CC(=O)Nc1cc(-c2cc(F)cc(OC3CCN(C)C3)c2)nc(-n2nc(C)cc2C)n1"

# USERNAME = "bob"
# PASSWORD = "Pa$$w0rd123"

USERNAME = "admin "
PASSWORD = "Admin#2024"

def get_token() -> str:
    payload = {"username": USERNAME, "password": PASSWORD}
    resp = requests.post(
        f"{BASE_URL}/login",
        headers={"Content-Type": "application/json"},
        data=json.dumps(payload),
    )
    if resp.status_code == 200:
        return resp.json().get("access_token", "")
    print(f"❌ 登录失败 [{resp.status_code}]:", resp.text)
    return ""

def test_login():
    print("Testing /login …")
    payload = {
        "username": "bob",
        "password": "Pa$$w0rd123"
    }
    headers = {"Content-Type": "application/json"}
    resp = requests.post(f"{BASE_URL}/login", headers=headers, data=json.dumps(payload))
    if resp.status_code == 200:
        data = resp.json()
        token = data.get("access_token")
        print("✅ 登录成功，获得 token：", token)
    else:
        print(f"❌ 登录失败 [{resp.status_code}]:", resp.text)

def test_fragmentize():
    print("Testing /fragmentize…")
    token = get_token()
    if not token:
        print("❌ 无法获取 token，跳过 fragmentize 测试")
        return

    params = {"smiles": test_smiles}
    headers = {
        "Authorization": f"Bearer {token}",
    }
    response = requests.get(f"{BASE_URL}/fragmentize", params=params, headers=headers)
    if response.ok:
        print("✅ Fragmentize response:")
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))
    else:
        print(f"❌ Fragmentize 失败 [{response.status_code}]:", response.text)




def test_generate():
    print("Testing /generate...")
    token = get_token()
    if not token:
        return
    payload = {
        "generateRequestList": [
            {
                "constSmiles": "c1ccccc1",
                "varSmiles": "C=O",
                "mainCls": "class1",
                "minorCls": "subclassA",
                "deltaValue": "1.0",
                "num": 2
            },
            {
                "constSmiles": "CCO",
                "varSmiles": "N",
                "mainCls": "class2",
                "minorCls": "subclassB",
                "deltaValue": "0.5",
                "num": 3
            }
        ]
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }
    response = requests.post(
        f"{BASE_URL}/generate", headers=headers, data=json.dumps(payload)
    )
    if response.ok:
        data = response.json()
        task_id = data.get("task_id")
        print("✅ 任务已加入队列，task_id:", task_id)
        if task_id:
            res = requests.get(
                f"{BASE_URL}/tasks/{task_id}/geneRes",
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
        print("Error:", response.status_code, response.text)


def test_create_user():
    print("Testing POST /users …")
    # payload = {
    #     "username": "bob",
    #     "password": "Pa$$w0rd123",
    #     "phone": "13900001111",
    #     "email": "bob@example.com"
    # }
    payload = {
        "username": "TOM2",
        "password": "321312",
        "phone": "13922221111",
        "email": "TOM2@example.com"
    }
    headers = {"Content-Type": "application/json"}
    resp = requests.post(f"{BASE_URL}/users", headers=headers, data=json.dumps(payload))
    if resp.status_code == 201:
        print("✅ 创建用户成功：", resp.json())
    else:
        print(f"❌ 创建用户失败 [{resp.status_code}]:\n", resp.text)

if __name__ == "__main__":
    # test_fragmentize()
    # print("\n" + "="*50 + "\n")
    test_generate()
    # test_create_user()
    # test_login()
