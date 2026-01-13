#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试修改后的肽段优化结果接口（JSON格式）
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

def test_get_result_json(token: str, task_id: str):
    """测试获取结果数据（JSON格式）"""
    print(f"\n📋 测试获取result数据（JSON格式）")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        resp = requests.get(
            f"{BASE_URL}/tasks/{task_id}/peptide/result",
            headers=headers,
            timeout=30
        )
        
        print(f"📥 响应状态码: {resp.status_code}")
        
        if resp.status_code == 200:
            result_data = resp.json()
            print("✅ result数据获取成功！")
            
            # 显示基本信息
            print(f"🆔 任务ID: {result_data.get('task_id')}")
            print(f"📊 任务状态: {result_data.get('task_status')}")
            print(f"🕐 创建时间: {result_data.get('created_at')}")
            print(f"🏁 完成时间: {result_data.get('finished_at')}")
            
            # 显示数据结构
            data = result_data.get('data', {})
            columns = data.get('columns', [])
            rows = data.get('rows', [])
            
            print(f"📈 数据列数: {len(columns)}")
            print(f"📉 数据行数: {len(rows)}")
            print(f"🏷️  列名: {columns}")
            
            # 显示前几行数据
            print("\n📄 前3行数据预览:")
            for i, row in enumerate(rows[:3]):
                print(f"  行 {i+1} [{row['index']}]:")
                for col in columns[:3]:  # 只显示前3列
                    value = row['values'].get(col)
                    print(f"    {col}: {value}")
                if len(columns) > 3:
                    print(f"    ... (共{len(columns)}列)")
                print()
            
            # 保存完整数据到文件
            with open(f"result_{task_id}.json", "w", encoding="utf-8") as f:
                json.dump(result_data, f, indent=2, ensure_ascii=False)
            print(f"💾 完整数据已保存为: result_{task_id}.json")
            
        else:
            print(f"❌ 获取失败: {resp.text}")
            
    except Exception as e:
        print(f"❌ 请求失败: {e}")

def test_download_result_csv(token: str, task_id: str):
    """测试下载原始CSV文件"""
    print(f"\n📋 测试下载原始CSV文件")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        resp = requests.get(
            f"{BASE_URL}/tasks/{task_id}/peptide/result/download",
            headers=headers,
            timeout=30
        )
        
        print(f"📥 响应状态码: {resp.status_code}")
        
        if resp.status_code == 200:
            print("✅ CSV文件下载成功！")
            print(f"📊 文件大小: {len(resp.content)} bytes")
            
            # 保存文件
            with open(f"result_{task_id}.csv", "wb") as f:
                f.write(resp.content)
            print(f"💾 文件已保存为: result_{task_id}.csv")
            
            # 显示文件内容预览
            if len(resp.content) < 2000:  # 如果文件较小，显示内容
                print("📄 文件内容预览:")
                print(resp.text[:1000])
        else:
            print(f"❌ 下载失败: {resp.text}")
            
    except Exception as e:
        print(f"❌ 请求失败: {e}")

def compare_formats(token: str, task_id: str):
    """比较JSON和CSV格式的数据"""
    print(f"\n🔍 比较JSON和CSV格式的数据")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        # 获取JSON格式
        json_resp = requests.get(
            f"{BASE_URL}/tasks/{task_id}/peptide/result",
            headers=headers,
            timeout=30
        )
        
        # 获取CSV格式
        csv_resp = requests.get(
            f"{BASE_URL}/tasks/{task_id}/peptide/result/download",
            headers=headers,
            timeout=30
        )
        
        if json_resp.status_code == 200 and csv_resp.status_code == 200:
            json_data = json_resp.json()
            csv_content = csv_resp.text
            
            print("✅ 两种格式都获取成功！")
            print(f"📊 JSON数据大小: {len(json_resp.content)} bytes")
            print(f"📄 CSV文件大小: {len(csv_resp.content)} bytes")
            
            # 统计信息
            data = json_data.get('data', {})
            json_rows = len(data.get('rows', []))
            json_cols = len(data.get('columns', []))
            csv_lines = len(csv_content.split('\n')) - 1  # 减去标题行
            
            print(f"🔢 JSON格式: {json_rows} 行 x {json_cols} 列")
            print(f"🔢 CSV格式: {csv_lines} 行数据")
            
        else:
            print(f"❌ 获取失败 - JSON: {json_resp.status_code}, CSV: {csv_resp.status_code}")
            
    except Exception as e:
        print(f"❌ 比较失败: {e}")

def main():
    """主测试函数"""
    print("🧬 肽段优化结果接口测试（JSON格式）")
    print("=" * 50)
    
    # 获取任务ID
    task_id = input("请输入要测试的任务ID (或直接回车使用默认): ").strip()
    if not task_id:
        task_id = "027dcf9357624a57bc244797c3717663"
        print(f"使用默认任务ID: {task_id}")
    
    # 1. 获取认证token
    token = get_token()
    if not token:
        print("❌ 无法获取token，终止测试")
        sys.exit(1)
    
    # 2. 测试JSON格式接口
    test_get_result_json(token, task_id)
    
    # 3. 测试CSV下载接口
    test_download_result_csv(token, task_id)
    
    # 4. 比较两种格式
    compare_formats(token, task_id)
    
    print("\n🎉 所有测试完成！")
    print("\n📝 接口总结:")
    print("  - JSON格式: GET /tasks/{task_id}/peptide/result")
    print("  - CSV下载: GET /tasks/{task_id}/peptide/result/download")

if __name__ == "__main__":
    main()
