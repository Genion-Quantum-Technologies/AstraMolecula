#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
完整的肽段优化工作流程测试
包括：创建任务、监控任务状态、查看结果
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
        print(f"✅ 登录成功")
        return token
    except Exception as e:
        print(f"❌ 登录请求失败: {e}")
        return None

def create_peptide_task(token: str) -> Optional[str]:
    """创建肽段优化任务"""
    print("\n🚀 创建肽段优化任务")
    
    # 测试数据 - 使用一个较短的肽段序列进行快速测试
    peptide_data = {
        "peptide_sequence": "MKFLVNVAL",  # 较短的测试序列
        "receptor_pdb_filename": "5ffg.pdb",
        "cores": 4,  # 使用较少的核心以便更快完成
        "cleanup": False,  # 保留中间文件以便检查
        "step": None,  # 运行完整流程
        "proteinmpnn_enabled": False  # 暂时禁用ProteinMPNN以加快测试
    }
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    try:
        resp = requests.post(
            f"{BASE_URL}/peptide/optimize",
            headers=headers,
            data=json.dumps(peptide_data),
            timeout=30
        )
        
        if resp.status_code == 200:
            result = resp.json()
            task_id = result.get("id")
            print(f"✅ 任务创建成功！任务ID: {task_id}")
            print(f"📋 任务详情: {json.dumps(result, indent=2, ensure_ascii=False)}")
            return task_id
        else:
            print(f"❌ 任务创建失败: {resp.text}")
            return None
            
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return None

def monitor_task_progress(token: str, task_id: str, max_wait_minutes: int = 30):
    """监控任务进度"""
    print(f"\n👀 开始监控任务进度 (最大等待 {max_wait_minutes} 分钟)")
    
    headers = {"Authorization": f"Bearer {token}"}
    start_time = time.time()
    max_wait_seconds = max_wait_minutes * 60
    
    while True:
        try:
            # 检查是否超时
            elapsed = time.time() - start_time
            if elapsed > max_wait_seconds:
                print(f"⏰ 监控超时 ({max_wait_minutes} 分钟)")
                break
            
            # 获取任务状态
            resp = requests.get(
                f"{BASE_URL}/peptide/optimize/{task_id}",
                headers=headers,
                timeout=10
            )
            
            if resp.status_code == 200:
                task_info = resp.json()
                status = task_info.get("status", "unknown")
                
                elapsed_min = elapsed / 60
                print(f"⏱️  [{elapsed_min:.1f}分钟] 任务状态: {status}")
                
                if status == "finished":
                    print("🎉 任务完成！")
                    return True
                elif status == "failed":
                    print("❌ 任务失败！")
                    return False
                elif status in ["pending", "running"]:
                    # 继续等待
                    pass
                else:
                    print(f"⚠️  未知状态: {status}")
            else:
                print(f"⚠️  获取任务状态失败: {resp.text}")
            
            # 等待30秒后再次检查
            time.sleep(30)
            
        except Exception as e:
            print(f"⚠️  监控过程中发生错误: {e}")
            time.sleep(30)
    
    return False

def get_task_results(token: str, task_id: str):
    """获取任务结果"""
    print("\n📊 获取任务结果")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        # 获取任务状态
        resp = requests.get(
            f"{BASE_URL}/peptide/optimize/{task_id}",
            headers=headers,
            timeout=10
        )
        
        if resp.status_code == 200:
            task_info = resp.json()
            print("📋 最终任务信息:")
            print(json.dumps(task_info, indent=2, ensure_ascii=False))
            
            # 获取任务配置
            config_resp = requests.get(
                f"{BASE_URL}/peptide/optimize/{task_id}/config",
                headers=headers,
                timeout=10
            )
            
            if config_resp.status_code == 200:
                config_info = config_resp.json()
                print("\n⚙️  任务配置:")
                print(json.dumps(config_info, indent=2, ensure_ascii=False))
            
            # 显示输出文件位置
            job_dir = task_info.get("job_dir")
            if job_dir:
                print(f"\n📂 任务文件位置:")
                print(f"   - 任务目录: {job_dir}")
                print(f"   - 输出目录: {job_dir}/output/")
                print(f"   - 结果文件: {job_dir}/output/result.csv")
                
        else:
            print(f"❌ 获取任务结果失败: {resp.text}")
            
    except Exception as e:
        print(f"❌ 获取结果时发生错误: {e}")

def main():
    """主函数"""
    print("🧬 肽段优化完整工作流程测试")
    print("=" * 50)
    
    # 1. 获取认证token
    token = get_token()
    if not token:
        print("❌ 无法获取token，终止测试")
        sys.exit(1)
    
    # 2. 创建肽段优化任务
    task_id = create_peptide_task(token)
    if not task_id:
        print("❌ 无法创建任务，终止测试")
        sys.exit(1)
    
    # 3. 监控任务进度
    success = monitor_task_progress(token, task_id, max_wait_minutes=30)
    
    # 4. 获取任务结果
    get_task_results(token, task_id)
    
    if success:
        print("\n🎊 完整工作流程测试成功完成！")
    else:
        print("\n⚠️  工作流程测试未完全完成，但已创建任务")
    
    print(f"\n💡 任务ID: {task_id}")
    print("💡 你可以继续手动检查任务状态和结果文件")

if __name__ == "__main__":
    main()
