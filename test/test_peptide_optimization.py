#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试蛋白优化接口的脚本
包括：创建优化任务、查询任务状态、获取任务配置
"""

import requests
import json
import time
import sys
from typing import Optional

BASE_URL = "http://127.0.0.1:8000"
USERNAME = "admin"
PASSWORD = "Admin#2024"

def get_token() -> Optional[str]:
    """登录获取JWT token"""
    payload = {"username": USERNAME, "password": PASSWORD}
    try:
        resp = requests.post(
            f"{BASE_URL}/login",
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload),
            timeout=10
        )
        if resp.status_code != 200:
            print(f"❌ 登录失败 [{resp.status_code}]: {resp.text}")
            return None
        
        token = resp.json().get("access_token")
        print(f"✅ 登录成功，token: {token[:50]}...")
        return token
    except Exception as e:
        print(f"❌ 登录请求失败: {e}")
        return None

def test_create_peptide_optimization_task(token: str) -> Optional[str]:
    """测试创建蛋白优化任务"""
    print("\n" + "="*50)
    print("🧪 测试创建蛋白优化任务")
    print("="*50)
    
    # 测试数据
    peptide_data = {
        "peptide_sequence": "MKFLVNVALVFMVVYISYIYA",  # 示例肽段序列
        "receptor_pdb_filename": "test1.pdb",  # 你已上传的文件
        "cores": 8,  # 使用8核
        "cleanup": True,  # 清理中间文件
        "step": None,  # 运行完整流程
        "proteinmpnn_enabled": True  # 启用ProteinMPNN
    }
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    try:
        print(f"📤 发送请求数据:")
        print(json.dumps(peptide_data, indent=2, ensure_ascii=False))
        
        resp = requests.post(
            f"{BASE_URL}/peptide/optimize",
            headers=headers,
            data=json.dumps(peptide_data),
            timeout=30
        )
        
        print(f"\n📥 响应状态码: {resp.status_code}")
        
        if resp.status_code == 200:
            result = resp.json()
            print("✅ 任务创建成功！")
            print("📋 任务详情:")
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return result.get("id")
        else:
            print(f"❌ 任务创建失败: {resp.text}")
            return None
            
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return None

def test_get_task_status(token: str, task_id: str):
    """测试获取任务状态"""
    print("\n" + "="*50)
    print("📊 测试获取任务状态")
    print("="*50)
    
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        resp = requests.get(
            f"{BASE_URL}/peptide/optimize/{task_id}",
            headers=headers,
            timeout=10
        )
        
        print(f"📥 响应状态码: {resp.status_code}")
        
        if resp.status_code == 200:
            result = resp.json()
            print("✅ 获取任务状态成功！")
            print("📋 任务状态:")
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print(f"❌ 获取任务状态失败: {resp.text}")
            
    except Exception as e:
        print(f"❌ 请求失败: {e}")

def test_get_task_config(token: str, task_id: str):
    """测试获取任务配置"""
    print("\n" + "="*50)
    print("⚙️  测试获取任务配置")
    print("="*50)
    
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        resp = requests.get(
            f"{BASE_URL}/peptide/optimize/{task_id}/config",
            headers=headers,
            timeout=10
        )
        
        print(f"📥 响应状态码: {resp.status_code}")
        
        if resp.status_code == 200:
            result = resp.json()
            print("✅ 获取任务配置成功！")
            print("⚙️  任务配置:")
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print(f"❌ 获取任务配置失败: {resp.text}")
            
    except Exception as e:
        print(f"❌ 请求失败: {e}")

def test_edge_cases(token: str):
    """测试边界情况和错误处理"""
    print("\n" + "="*50)
    print("🚨 测试边界情况和错误处理")
    print("="*50)
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # 测试1: 空的肽段序列
    print("\n🧪 测试1: 空的肽段序列")
    test_data_1 = {
        "peptide_sequence": "",
        "receptor_pdb_filename": "test1.pdb",
    }
    
    try:
        resp = requests.post(
            f"{BASE_URL}/peptide/optimize",
            headers=headers,
            data=json.dumps(test_data_1),
            timeout=10
        )
        print(f"状态码: {resp.status_code}")
        print(f"响应: {resp.text}")
    except Exception as e:
        print(f"请求失败: {e}")
    
    # 测试2: 不存在的PDB文件
    print("\n🧪 测试2: 不存在的PDB文件")
    test_data_2 = {
        "peptide_sequence": "MKFLVNVALVFMVVYISYIYA",
        "receptor_pdb_filename": "non_existent.pdb",
    }
    
    try:
        resp = requests.post(
            f"{BASE_URL}/peptide/optimize",
            headers=headers,
            data=json.dumps(test_data_2),
            timeout=10
        )
        print(f"状态码: {resp.status_code}")
        print(f"响应: {resp.text}")
    except Exception as e:
        print(f"请求失败: {e}")
    
    # 测试3: 无效的step参数
    print("\n🧪 测试3: 无效的step参数")
    test_data_3 = {
        "peptide_sequence": "MKFLVNVALVFMVVYISYIYA",
        "receptor_pdb_filename": "test1.pdb",
        "step": 10  # 超出有效范围(1-8)
    }
    
    try:
        resp = requests.post(
            f"{BASE_URL}/peptide/optimize",
            headers=headers,
            data=json.dumps(test_data_3),
            timeout=10
        )
        print(f"状态码: {resp.status_code}")
        print(f"响应: {resp.text}")
    except Exception as e:
        print(f"请求失败: {e}")

def test_get_nonexistent_task(token: str):
    """测试获取不存在的任务"""
    print("\n🧪 测试4: 获取不存在的任务")
    headers = {"Authorization": f"Bearer {token}"}
    
    fake_task_id = "nonexistent-task-id"
    
    try:
        resp = requests.get(
            f"{BASE_URL}/peptide/optimize/{fake_task_id}",
            headers=headers,
            timeout=10
        )
        print(f"状态码: {resp.status_code}")
        print(f"响应: {resp.text}")
    except Exception as e:
        print(f"请求失败: {e}")

def main():
    """主测试函数"""
    print("🚀 开始测试蛋白优化接口")
    print("="*60)
    
    # 1. 获取认证token
    token = get_token()
    if not token:
        print("❌ 无法获取token，终止测试")
        sys.exit(1)
    
    # 2. 测试创建优化任务
    task_id = test_create_peptide_optimization_task(token)
    
    if task_id:
        # 3. 测试获取任务状态
        test_get_task_status(token, task_id)
        
        # 4. 测试获取任务配置
        test_get_task_config(token, task_id)
        
        print(f"\n💡 任务ID: {task_id}")
        print("💡 你可以使用这个ID继续监控任务状态")
    
    # 5. 测试边界情况和错误处理
    test_edge_cases(token)
    test_get_nonexistent_task(token)
    
    print("\n" + "="*60)
    print("🎉 所有测试完成！")
    
    if task_id:
        print(f"\n📝 任务创建成功，任务ID: {task_id}")
        print("📂 你可以在以下位置查看任务文件:")
        print(f"   - 任务目录: jobs/peptide_optimization/{task_id}/")
        print(f"   - 输入文件: jobs/peptide_optimization/{task_id}/input/")
        print(f"   - 配置文件: jobs/peptide_optimization/{task_id}/optimization_config.txt")

if __name__ == "__main__":
    main()
