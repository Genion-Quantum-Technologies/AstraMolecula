import requests
import json

BASE_URL = "http://127.0.0.1:8000"
# USERNAME = "bob"
# PASSWORD = "Pa$$w0rd123"
USERNAME = "admin"
PASSWORD = "Admin#2024"
def get_token():
    """先登录拿到 JWT"""
    payload = {"username": USERNAME, "password": PASSWORD}
    resp = requests.post(f"{BASE_URL}/login",
                         headers={"Content-Type": "application/json"},
                         data=json.dumps(payload))
    if resp.status_code != 200:
        print(f"❌ 登录失败 [{resp.status_code}]:", resp.text)
        return None
    token = resp.json().get("access_token")
    print("✅ 登录成功，token:", token)
    return token

def test_upload_pdbqt():
    """使用拿到的 token 上传 example.pdbqt"""
    token = get_token()
    if not token:
        return

    # 准备文件列表
    # 多文件上传时，把文件 tuple 都放到列表里
    files = [
        ("files", ("test1.pdb", open("test1.pdb", "rb"), "application/octet-stream")),
        # 如果还有别的 pdbqt 文件，可继续追加
        # ("files", ("another.pdbqt", open("another.pdbqt", "rb"), "application/octet-stream")),
    ]

    headers = {
        "Authorization": f"Bearer {token}"
    }

# 上传
    resp = requests.post(
        f"{BASE_URL}/upload_pdbqt",
        headers=headers,
        files=files,
        timeout=60
    )
    if resp.status_code == 200:
        print("✅ 上传成功，返回：")
        print(json.dumps(resp.json(), indent=2, ensure_ascii=False))
    else:
        print(f"❌ 上传失败 [{resp.status_code}]:", resp.text)
        return

    # 再调用 /users/me/uploads 验证记录
    resp2 = requests.get(
        f"{BASE_URL}/users/me/uploads",
        headers=headers,
        timeout=10
    )
    if resp2.status_code == 200:
        uploads = resp2.json()
        print("\n✅ 上传记录：")
        print(json.dumps(uploads, indent=2, ensure_ascii=False))
    else:
        print(f"❌ 拉取上传记录失败 [{resp2.status_code}]:", resp2.text)

if __name__ == "__main__":
    test_upload_pdbqt()
