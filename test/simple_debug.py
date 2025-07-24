#!/usr/bin/env python3
"""
简单的token调试脚本
"""
import requests
import json

# 配置
API_BASE = "http://3.133.131.124:8000"
USERNAME = "admin"
PASSWORD = "Admin#2024"

def test_login():
    """测试登录并获取token"""
    print("1. 测试登录...")
    
    login_data = {
        "username": USERNAME,
        "password": PASSWORD
    }
    
    response = requests.post(f"{API_BASE}/login", json=login_data)
    print(f"登录响应状态码: {response.status_code}")
    print(f"登录响应内容: {response.text}")
    
    if response.status_code == 200:
        data = response.json()
        token = data.get("access_token")
        print(f"✅ 获取到token: {token}")
        return token
    else:
        print("❌ 登录失败")
        return None

def test_protected_endpoint(token):
    """测试受保护的端点"""
    print("\n2. 测试受保护的端点...")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # 测试获取任务列表
    response = requests.get(f"{API_BASE}/tasks/", headers=headers)
    print(f"任务列表响应状态码: {response.status_code}")
    print(f"任务列表响应内容: {response.text}")
    
    if response.status_code == 200:
        print("✅ 受保护端点访问成功")
        return True
    else:
        print("❌ 受保护端点访问失败")
        return False

def main():
    print("开始调试token问题...")
    
    # 1. 测试登录
    token = test_login()
    if not token:
        return
    
    # 2. 测试受保护端点
    success = test_protected_endpoint(token)
    
    if success:
        print("\n✅ 所有测试通过！")
    else:
        print("\n❌ 存在问题需要修复")

if __name__ == "__main__":
    main()
