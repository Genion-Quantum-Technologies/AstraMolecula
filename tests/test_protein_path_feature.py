#!/usr/bin/env python3
"""
测试 protein_path 功能
验证在 GET /tasks/{task_id}/dockRes 请求中能够获取到 protein 路径信息
"""

import requests
import json

BASE_URL = "http://127.0.0.1:8000"

def get_token():
    """获取认证token"""
    login_data = {
        "username": "admin",
        "password": "admin123"
    }
    response = requests.post(f"{BASE_URL}/login", json=login_data)
    if response.status_code == 200:
        return response.json().get("access_token")
    return None

def test_protein_path_in_docking_results():
    """测试docking结果中是否包含protein_path字段"""
    token = get_token()
    if not token:
        print("❌ 无法获取token")
        return

    headers = {"Authorization": f"Bearer {token}"}
    
    # 1. 获取所有任务
    response = requests.get(f"{BASE_URL}/tasks/", headers=headers)
    if response.status_code != 200:
        print(f"❌ 获取任务列表失败: {response.status_code}")
        return
    
    tasks = response.json()
    
    # 2. 找到已完成的docking任务
    finished_docking_tasks = [
        task for task in tasks 
        if task['task_type'] == 'docking' and task['status'] == 'finished'
    ]
    
    if not finished_docking_tasks:
        print("❌ 没有找到已完成的docking任务")
        return
    
    # 3. 测试第一个已完成的docking任务
    task = finished_docking_tasks[0]
    task_id = task['id']
    print(f"🔍 测试任务 {task_id}")
    
    response = requests.get(f"{BASE_URL}/tasks/{task_id}/dockRes", headers=headers)
    if response.status_code != 200:
        print(f"❌ 获取docking结果失败: {response.status_code} - {response.text}")
        return
    
    results = response.json()
    print(f"✅ 获取到 {len(results)} 个docking结果")
    
    # 4. 检查是否包含protein_path字段
    if results:
        first_result = results[0]
        print(f"📋 第一个结果的字段: {list(first_result.keys())}")
        
        if 'protein_path' in first_result:
            protein_path = first_result['protein_path']
            print(f"✅ 找到 protein_path 字段: {protein_path}")
            
            # 验证路径格式
            if protein_path and '.pdbqt' in protein_path:
                print("✅ protein_path 格式正确")
            else:
                print("⚠️  protein_path 格式可能不正确")
        else:
            print("❌ 未找到 protein_path 字段")
    else:
        print("❌ 结果为空")

if __name__ == "__main__":
    test_protein_path_in_docking_results() 