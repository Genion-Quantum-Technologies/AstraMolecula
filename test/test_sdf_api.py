#!/usr/bin/env python3
"""
测试SDF API功能
"""
import time
import os
import sys

# 添加requests模块路径
sys.path.insert(0, '/Users/youngwild/dev_tools/miniconda3/envs/dockingvina_final/lib/python3.10/site-packages')

try:
    import requests
except ImportError:
    print("requests模块未安装，请运行: pip install requests")
    sys.exit(1)

BASE_URL = "http://localhost:8000"

def get_token():
    """获取认证token"""
    login_data = {
        "username": "admin",
        "password": "Admin#2024"
    }
    
    response = requests.post(f"{BASE_URL}/auth/login", json=login_data)
    if response.status_code == 200:
        return response.json().get("access_token")
    else:
        print(f"登录失败: {response.status_code} - {response.text}")
        return None

def test_existing_task():
    """测试现有任务的SDF文件获取"""
    token = get_token()
    if not token:
        print("无法获取token，可能服务器未运行")
        return
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # 使用现有的任务ID
    task_id = "44da692430db486eabc84f1a3154c1d0"
    
    print(f"1. 测试获取任务 {task_id} 的对接结果...")
    response = requests.get(f"{BASE_URL}/tasks/{task_id}/dockRes", headers=headers)
    if response.status_code != 200:
        print(f"获取结果失败: {response.status_code} - {response.text}")
        return
    
    results = response.json()
    print(f"获取到 {len(results)} 个结果")
    
    # 测试SDF文件获取
    if results:
        first_result = results[0]
        sdf_filename = first_result.get("file")
        
        if sdf_filename:
            print(f"2. 测试SDF文件获取: {sdf_filename}")
            response = requests.get(f"{BASE_URL}/tasks/{task_id}/sdf/{sdf_filename}", headers=headers)
            
            if response.status_code == 200:
                print("✅ SDF文件获取成功!")
                print(f"SDF文件大小: {len(response.text)} 字符")
                print(f"SDF文件前100个字符: {response.text[:100]}...")
            else:
                print(f"❌ SDF文件获取失败: {response.status_code} - {response.text}")
        else:
            print("❌ 结果中没有file字段")
    else:
        print("❌ 没有获取到结果")

def test_file_existence():
    """测试文件系统中的SDF文件是否存在"""
    task_id = "44da692430db486eabc84f1a3154c1d0"
    sdf_files = [
        f"jobs/docking/{task_id}/docked/ligand_1-1-p0.sdf",
        f"jobs/docking/{task_id}/docked/ligand_1-2-p0.sdf",
        f"jobs/docking/{task_id}/docked/ligand_1-3-p0.sdf"
    ]
    
    print("3. 检查文件系统中的SDF文件...")
    for sdf_file in sdf_files:
        if os.path.exists(sdf_file):
            print(f"✅ {sdf_file} 存在")
            with open(sdf_file, 'r') as f:
                content = f.read()
                print(f"   文件大小: {len(content)} 字符")
        else:
            print(f"❌ {sdf_file} 不存在")

if __name__ == "__main__":
    print("=== 分子对接SDF文件测试 ===")
    test_file_existence()
    test_existing_task() 