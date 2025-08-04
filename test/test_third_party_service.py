#!/usr/bin/env python3
"""
第三方服务模拟脚本
演示如何使用API Key认证，上传文件并提交docking任务
"""

import requests
import json
import time
from pathlib import Path
from typing import Dict, Any

# 配置信息
API_BASE_URL = "http://localhost:8000"  # 修改为你的API地址
SERVICE_API_KEY = "third-party-service-key-123"  # 替换为你的服务API Key
EXTERNAL_USER_ID = "user123@third-party-service"  # 第三方服务中的用户ID

# 测试文件路径
TEST_PDBQT_FILE = "/home/davis/projects/AstraMolecula/dockingVina/test/user3.pdbqt"

class ThirdPartyServiceSimulator:
    """第三方服务模拟器"""
    
    def __init__(self, base_url: str, api_key: str, external_user_id: str):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.external_user_id = external_user_id
        self.session = requests.Session()
        
        # 设置默认请求头
        self.session.headers.update({
            "X-API-Key": self.api_key,
            "X-External-User-ID": self.external_user_id,
            "User-Agent": "ThirdPartyService/1.0"
        })
    
    def upload_file(self, file_path: str) -> Dict[str, Any]:
        """上传文件到服务器"""
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")
        
        print(f"📤 上传文件: {file_path.name}")
        
        url = f"{self.base_url}/upload_pdbqt"
        
        with open(file_path, 'rb') as f:
            files = {
                'files': (file_path.name, f, 'application/octet-stream')
            }
            
            response = self.session.post(url, files=files)
            
        if response.status_code == 200:  # upload_pdbqt 返回200而不是201
            result = response.json()
            print(f"✅ 文件上传成功!")
            print(f"   用户ID: {result.get('user_id')}")
            print(f"   文件列表: {result.get('files')}")
            # 返回第一个上传文件的名称
            files = result.get('files', [])
            if files:
                result['filename'] = files[0]  # 添加filename字段以保持兼容性
            return result
        else:
            print(f"❌ 文件上传失败: {response.status_code}")
            print(f"   错误信息: {response.text}")
            raise Exception(f"文件上传失败: {response.status_code} - {response.text}")
    
    def submit_docking_task(self, receptor_filename: str) -> Dict[str, Any]:
        """提交对接任务"""
        print(f"🧪 提交对接任务，使用受体文件: {receptor_filename}")
        
        url = f"{self.base_url}/docking"
        
        # 构建对接请求数据
        docking_data = {
            "ligands": [
                {
                    "title": "test_ligand_1",
                    "smiles": "CCO"  # 乙醇的SMILES
                },
                {
                    "title": "test_ligand_2", 
                    "smiles": "CC(=O)O"  # 乙酸的SMILES
                }
            ],
            "center_x": 61.105,
            "center_y": 65.466,
            "center_z": 37.021,
            "box_size_x": 20.0,
            "box_size_y": 20.0,
            "box_size_z": 20.0,
            "exhaustiveness": 8,
            "n_poses": 9,
            "min_ph": 6.0,
            "max_ph": 8.0,
            "n_jobs": 1
        }
        
        # 添加受体文件参数
        params = {"receptor_filename": receptor_filename}
        
        response = self.session.post(
            url, 
            json=docking_data,
            params=params
        )
        
        if response.status_code == 201:
            result = response.json()
            print(f"✅ 对接任务提交成功!")
            print(f"   任务ID: {result.get('task_id')}")
            print(f"   状态: {result.get('status')}")
            return result
        else:
            print(f"❌ 对接任务提交失败: {response.status_code}")
            print(f"   错误信息: {response.text}")
            raise Exception(f"对接任务提交失败: {response.status_code} - {response.text}")
    
    def check_task_status(self, task_id: str) -> Dict[str, Any]:
        """检查任务状态"""
        url = f"{self.base_url}/tasks/{task_id}/status"
        
        response = self.session.get(url)
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"❌ 检查任务状态失败: {response.status_code}")
            print(f"   错误信息: {response.text}")
            raise Exception(f"检查任务状态失败: {response.status_code} - {response.text}")
    
    def wait_for_task_completion(self, task_id: str, max_wait_time: int = 600):
        """等待任务完成"""
        print(f"⏳ 等待任务 {task_id} 完成...")
        
        start_time = time.time()
        last_status = None
        
        while time.time() - start_time < max_wait_time:
            try:
                status_info = self.check_task_status(task_id)
                current_status = status_info.get('status')
                
                if current_status != last_status:
                    print(f"📊 任务状态: {current_status}")
                    if 'progress' in status_info:
                        print(f"   进度: {status_info['progress']}%")
                    last_status = current_status
                
                if current_status == 'finished':
                    print(f"🎉 任务完成!")
                    return status_info
                elif current_status == 'failed':
                    print(f"💥 任务失败!")
                    return status_info
                
                # 根据建议的轮询间隔等待
                poll_interval = status_info.get('poll_interval', 5)
                if poll_interval > 0:
                    time.sleep(poll_interval)
                else:
                    break  # 任务已结束
                    
            except Exception as e:
                print(f"⚠️ 检查状态时出错: {e}")
                time.sleep(5)
        
        print(f"⏰ 等待超时 ({max_wait_time}秒)")
        return None
    
    def get_docking_results(self, task_id: str) -> Dict[str, Any]:
        """获取对接结果"""
        print(f"📋 获取任务 {task_id} 的对接结果...")
        
        url = f"{self.base_url}/tasks/{task_id}/dockRes"
        
        response = self.session.get(url)
        
        if response.status_code == 200:
            results = response.json()
            print(f"✅ 成功获取对接结果!")
            print(f"   结果数量: {len(results) if isinstance(results, list) else 1}")
            return results
        else:
            print(f"❌ 获取对接结果失败: {response.status_code}")
            print(f"   错误信息: {response.text}")
            raise Exception(f"获取对接结果失败: {response.status_code} - {response.text}")
    
    def list_user_tasks(self) -> Dict[str, Any]:
        """列出用户任务"""
        print(f"📝 获取用户任务列表...")
        
        url = f"{self.base_url}/tasks/"
        
        response = self.session.get(url)
        
        if response.status_code == 200:
            tasks = response.json()
            print(f"✅ 成功获取任务列表!")
            print(f"   任务数量: {len(tasks) if isinstance(tasks, list) else 0}")
            return tasks
        else:
            print(f"❌ 获取任务列表失败: {response.status_code}")
            print(f"   错误信息: {response.text}")
            raise Exception(f"获取任务列表失败: {response.status_code} - {response.text}")


def main():
    """主函数 - 完整的第三方服务工作流程演示"""
    
    print("🚀 开始第三方服务模拟测试")
    print("=" * 50)
    
    # 创建模拟器实例
    simulator = ThirdPartyServiceSimulator(
        base_url=API_BASE_URL,
        api_key=SERVICE_API_KEY,
        external_user_id=EXTERNAL_USER_ID
    )
    
    try:
        # 步骤1: 上传PDBQT文件
        print("\n📤 步骤1: 上传受体文件")
        upload_result = simulator.upload_file(TEST_PDBQT_FILE)
        receptor_filename = upload_result['filename']
        
        # 步骤2: 提交对接任务
        print("\n🧪 步骤2: 提交对接任务")
        task_result = simulator.submit_docking_task(receptor_filename)
        task_id = task_result['task_id']
        
        # 步骤3: 等待任务完成
        print("\n⏳ 步骤3: 等待任务完成")
        final_status = simulator.wait_for_task_completion(task_id, max_wait_time=300)
        
        if final_status and final_status.get('status') == 'finished':
            # 步骤4: 获取结果
            print("\n📋 步骤4: 获取对接结果")
            results = simulator.get_docking_results(task_id)
            
            # 显示结果摘要
            if isinstance(results, list) and results:
                print(f"\n📊 结果摘要:")
                for i, result in enumerate(results[:3]):  # 只显示前3个结果
                    print(f"   结果 {i+1}:")
                    print(f"     标题: {result.get('title', 'N/A')}")
                    print(f"     对接分数: {result.get('docking_score', 'N/A')}")
                    if 'sdf_file' in result:
                        print(f"     SDF文件: {result['sdf_file']}")
        
        # 步骤5: 列出所有任务
        print("\n📝 步骤5: 查看任务历史")
        tasks = simulator.list_user_tasks()
        
        if isinstance(tasks, list):
            print(f"\n📋 用户任务历史:")
            for task in tasks[-5:]:  # 显示最近5个任务
                print(f"   任务ID: {task.get('id', 'N/A')}")
                print(f"     类型: {task.get('task_type', 'N/A')}")
                print(f"     状态: {task.get('status', 'N/A')}")
                print(f"     创建时间: {task.get('created_at', 'N/A')}")
                print()
        
        print("🎉 第三方服务模拟测试完成!")
        
    except Exception as e:
        print(f"\n💥 测试过程中发生错误: {e}")
        print("请检查:")
        print("1. API服务是否正在运行")
        print("2. API Key是否正确配置")
        print("3. 网络连接是否正常")
        print("4. 测试文件是否存在")
        return 1
    
    return 0


if __name__ == "__main__":
    # 配置检查
    print("🔧 配置检查:")
    print(f"   API地址: {API_BASE_URL}")
    print(f"   服务API Key: {SERVICE_API_KEY}")
    print(f"   外部用户ID: {EXTERNAL_USER_ID}")
    print(f"   测试文件: {TEST_PDBQT_FILE}")
    
    # 检查测试文件是否存在
    if not Path(TEST_PDBQT_FILE).exists():
        print(f"❌ 测试文件不存在: {TEST_PDBQT_FILE}")
        print("请确保测试文件存在后再运行脚本")
        exit(1)
    
    # 运行主程序
    exit_code = main()
    exit(exit_code)
