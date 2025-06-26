# test_smiles2img.py

import json
import requests
import io
from PIL import Image


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

def test_smiles2img(smiles: str, output_path: str = "molecule.png"):
    """
    调用 smiles2img 接口，将返回的 PNG 图片保存并展示。
    :param smiles: 要测试的 SMILES 字符串
    :param output_path: 保存图片的本地路径
    """
    token = get_token()
    if not token:
        return
    # 如果你的 FastAPI 服务跑在其他地址或端口，请修改下面的 URL
    url = f"{BASE_URL}/smiles2img"
    params = {"smiles": smiles}

    # 发起 GET 请求
    resp = requests.get(url, params=params,headers={"Authorization": f"Bearer {token}"},)
    if resp.status_code == 200 and resp.headers.get("Content-Type") == "image/png":
        # 保存到本地文件
        with open(output_path, "wb") as f:
            f.write(resp.content)
        print(f"[✔] 图片已保存到 {output_path}")

        # 可选：直接打开并展示
        img = Image.open(io.BytesIO(resp.content))
        img.show()
    else:
        # 如果 SMILES 无效或接口报错，打印错误信息
        print(f"[✖] 请求失败，状态码：{resp.status_code}")
        print("响应内容：", resp.text)

if __name__ == "__main__":
    # 示例：苯环的 SMILES（c1ccccc1）
    test_smiles2img("c1ccccc1", output_path="benzene.png")
