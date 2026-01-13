#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试肽段优化结果文件下载接口
"""

import requests
import json
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
        print(f"✅ 登录成功")
        return token
    except Exception as e:
        print(f"❌ 登录请求失败: {e}")
        return None

def test_download_result_csv(token: str, task_id: str):
    """测试下载result.csv文件"""
    print(f"\n📋 测试下载result.csv文件")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        resp = requests.get(
            f"{BASE_URL}/tasks/{task_id}/peptide/result",
            headers=headers,
            timeout=30
        )
        
        print(f"📥 响应状态码: {resp.status_code}")
        
        if resp.status_code == 200:
            print("✅ result.csv下载成功！")
            print(f"📊 文件大小: {len(resp.content)} bytes")
            
            # 保存文件
            with open(f"result_{task_id}.csv", "wb") as f:
                f.write(resp.content)
            print(f"💾 文件已保存为: result_{task_id}.csv")
            
            # 显示文件内容预览
            if len(resp.content) < 1000:  # 如果文件较小，显示内容
                print("📄 文件内容预览:")
                print(resp.text[:500])
        else:
            print(f"❌ 下载失败: {resp.text}")
            
    except Exception as e:
        print(f"❌ 请求失败: {e}")

def test_download_output_folder(token: str, task_id: str):
    """测试下载output文件夹压缩包"""
    print(f"\n📦 测试下载output文件夹压缩包")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        resp = requests.get(
            f"{BASE_URL}/tasks/{task_id}/peptide/output",
            headers=headers,
            timeout=60  # 压缩包可能较大，增加超时时间
        )
        
        print(f"📥 响应状态码: {resp.status_code}")
        
        if resp.status_code == 200:
            print("✅ output文件夹压缩包下载成功！")
            print(f"📦 压缩包大小: {len(resp.content)} bytes")
            
            # 保存压缩包
            filename = f"peptide_optimization_{task_id}_output.zip"
            with open(filename, "wb") as f:
                f.write(resp.content)
            print(f"💾 压缩包已保存为: {filename}")
            
        else:
            print(f"❌ 下载失败: {resp.text}")
            
    except Exception as e:
        print(f"❌ 请求失败: {e}")

def test_task_status(token: str, task_id: str):
    """测试获取任务状态"""
    print(f"\n📊 测试获取任务状态")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        resp = requests.get(
            f"{BASE_URL}/peptide/optimize/{task_id}",
            headers=headers,
            timeout=10
        )
        
        print(f"📥 响应状态码: {resp.status_code}")
        
        if resp.status_code == 200:
            task_info = resp.json()
            print("✅ 获取任务状态成功！")
            print(f"📋 任务状态: {task_info.get('status')}")
            print(f"🆔 任务ID: {task_info.get('id')}")
            print(f"📁 任务目录: {task_info.get('job_dir')}")
            return task_info.get('status')
        else:
            print(f"❌ 获取状态失败: {resp.text}")
            return None
            
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return None

def main():
    """主测试函数"""
    print("🧬 肽段优化结果文件下载接口测试")
    print("=" * 50)
    
    # 获取任务ID (如果已知可以直接设置)
    task_id = input("请输入要测试的任务ID (或直接回车使用默认): ").strip()
    if not task_id:
        # 使用一个示例任务ID，实际使用时需要替换
        task_id = "027dcf9357624a57bc244797c3717663"
        print(f"使用默认任务ID: {task_id}")
    
    # 1. 获取认证token
    token = get_token()
    if not token:
        print("❌ 无法获取token，终止测试")
        sys.exit(1)
    
    # 2. 测试获取任务状态
    status = test_task_status(token, task_id)
    
    if status == "finished":
        # 3. 测试下载result.csv
        test_download_result_csv(token, task_id)
        
        # 4. 测试下载output文件夹
        test_download_output_folder(token, task_id)
        
        print("\n🎉 所有测试完成！")
    elif status in ["pending", "processing"]:
        print(f"\n⏳ 任务状态为 {status}，无法下载结果文件")
    elif status == "failed":
        print(f"\n❌ 任务状态为 {status}，任务执行失败")
    else:
        print(f"\n⚠️  任务状态未知: {status}")

if __name__ == "__main__":
    main()
