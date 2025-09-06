#!/usr/bin/env python3
"""
测试任务列表带成本信息的API
"""

import requests
import json

def test_tasks_with_cost():
    """测试带成本信息的任务列表API"""
    
    # API基础URL（需要根据实际情况修改）
    BASE_URL = "http://localhost:8080"
    
    # 假设有一个测试token（需要根据实际情况修改）
    headers = {
        "Authorization": "Bearer your_test_token_here",
        "Content-Type": "application/json"
    }
    
    try:
        # 测试任务列表API
        response = requests.get(f"{BASE_URL}/tasks/", headers=headers)
        
        if response.status_code == 200:
            tasks = response.json()
            print("✅ 任务列表获取成功")
            print(f"任务数量: {len(tasks)}")
            
            # 检查是否包含成本信息
            for task in tasks[:3]:  # 只显示前3个任务
                print(f"\n任务 ID: {task['id'][:8]}...")
                print(f"类型: {task['task_type']}")
                print(f"状态: {task['status']}")
                print(f"计算成本: {task.get('total_compute_units', 'N/A')} CU")
                
        else:
            print(f"❌ 请求失败: {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"❌ 测试出错: {e}")

def test_task_cost_api():
    """测试单个任务成本API"""
    
    BASE_URL = "http://localhost:8080"
    headers = {
        "Authorization": "Bearer your_test_token_here",
        "Content-Type": "application/json"
    }
    
    # 这里需要一个实际的任务ID
    task_id = "your_test_task_id_here"
    
    try:
        response = requests.get(f"{BASE_URL}/tasks/{task_id}/cost", headers=headers)
        
        if response.status_code == 200:
            cost_info = response.json()
            print("✅ 任务成本信息获取成功")
            print(json.dumps(cost_info, indent=2, ensure_ascii=False))
        else:
            print(f"❌ 请求失败: {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"❌ 测试出错: {e}")

if __name__ == "__main__":
    print("🧪 测试任务列表成本功能")
    print("=" * 50)
    
    print("\n1. 测试任务列表API...")
    test_tasks_with_cost()
    
    print("\n2. 测试任务成本API...")
    test_task_cost_api()
    
    print("\n📝 注意:")
    print("- 请修改BASE_URL为实际的API地址")
    print("- 请提供有效的认证token")
    print("- 请提供实际的任务ID进行测试")
