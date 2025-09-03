#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通过API提交Peptide优化任务的Python脚本
支持完整的工作流程：登录 -> 上传文件 -> 创建任务 -> 监控状态 -> 获取结果
"""

import requests
import json
import time
import sys
import argparse
from pathlib import Path
from typing import Optional, List, Dict, Any
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('peptide_api_client.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class PeptideAPIClient:
    """Peptide优化任务API客户端"""
    
    def __init__(self, base_url: str = "http://127.0.0.1:8000", 
                 username: str = "admin", password: str = "Admin#2024"):
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self.token = None
        self.session = requests.Session()
        
    def login(self) -> bool:
        """登录获取JWT token"""
        logger.info("正在登录...")
        payload = {"username": self.username, "password": self.password}
        
        try:
            resp = self.session.post(
                f"{self.base_url}/login",
                headers={"Content-Type": "application/json"},
                data=json.dumps(payload),
                timeout=10
            )
            
            if resp.status_code == 200:
                self.token = resp.json().get("access_token")
                self.session.headers.update({"Authorization": f"Bearer {self.token}"})
                logger.info("✅ 登录成功")
                return True
            else:
                logger.error(f"❌ 登录失败 [{resp.status_code}]: {resp.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ 登录请求失败: {e}")
            return False
    
    def upload_pdb_file(self, pdb_file_path: str) -> bool:
        """上传PDB文件"""
        logger.info(f"正在上传PDB文件: {pdb_file_path}")
        
        file_path = Path(pdb_file_path)
        if not file_path.exists():
            logger.error(f"❌ 文件不存在: {pdb_file_path}")
            return False
        
        if not file_path.suffix.lower() in ['.pdb', '.pdbqt']:
            logger.error(f"❌ 不支持的文件格式: {file_path.suffix}")
            return False
        
        try:
            with open(file_path, 'rb') as f:
                files = {'files': (file_path.name, f, 'chemical/x-pdb')}
                resp = self.session.post(
                    f"{self.base_url}/upload_pdbqt",
                    files=files,
                    timeout=60
                )
            
            if resp.status_code == 200:
                result = resp.json()
                logger.info(f"✅ 文件上传成功: {result.get('files', [])}")
                return True
            else:
                logger.error(f"❌ 文件上传失败 [{resp.status_code}]: {resp.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ 文件上传异常: {e}")
            return False
    
    def list_uploaded_files(self) -> List[Dict[str, Any]]:
        """查看已上传的文件列表"""
        logger.info("正在查询已上传的文件...")
        
        try:
            resp = self.session.get(
                f"{self.base_url}/users/me/uploads",
                timeout=10
            )
            
            if resp.status_code == 200:
                files = resp.json()
                logger.info(f"✅ 找到 {len(files)} 个已上传的文件")
                for file_info in files:
                    logger.info(f"   - {file_info.get('filename')} (上传于: {file_info.get('uploaded_at')})")
                return files
            else:
                logger.error(f"❌ 查询文件列表失败 [{resp.status_code}]: {resp.text}")
                return []
                
        except Exception as e:
            logger.error(f"❌ 查询文件列表异常: {e}")
            return []
    
    def create_peptide_task(self, 
                           peptide_sequence: str,
                           receptor_pdb_filename: str,
                           cores: int = 4,
                           cleanup: bool = False,
                           step: Optional[int] = None,
                           proteinmpnn_enabled: bool = True,
                           n_poses: int = 10,
                           num_seq_per_target: int = 10,
                           proteinmpnn_seed: int = 37,
                           n_iterations: int = 5,
                           n_rosetta_runs: int = 20) -> Optional[str]:
        """创建肽段优化任务"""
        logger.info("正在创建肽段优化任务...")
        
        # 验证肽段序列
        if not peptide_sequence.strip():
            logger.error("❌ 肽段序列不能为空")
            return None
        
        # 构造请求数据
        task_data = {
            "peptide_sequence": peptide_sequence.strip(),
            "receptor_pdb_filename": receptor_pdb_filename,
            "cores": cores,
            "cleanup": cleanup,
            "step": step,
            "proteinmpnn_enabled": proteinmpnn_enabled,
            "n_poses": n_poses,
            "num_seq_per_target": num_seq_per_target,
            "proteinmpnn_seed": proteinmpnn_seed,
            "n_iterations": n_iterations,
            "n_rosetta_runs": n_rosetta_runs
        }
        
        logger.info(f"任务参数:")
        logger.info(f"  - 肽段序列: {peptide_sequence[:50]}{'...' if len(peptide_sequence) > 50 else ''}")
        logger.info(f"  - 受体文件: {receptor_pdb_filename}")
        logger.info(f"  - CPU核心数: {cores}")
        logger.info(f"  - 清理中间文件: {cleanup}")
        logger.info(f"  - 指定步骤: {step if step else '完整流程'}")
        logger.info(f"  - ProteinMPNN: {proteinmpnn_enabled}")
        logger.info(f"  - 对接构象数: {n_poses}")
        logger.info(f"  - 优化迭代次数: {n_iterations}")
        logger.info(f"  - Rosetta运行次数: {n_rosetta_runs}")
        
        try:
            resp = self.session.post(
                f"{self.base_url}/peptide/optimize",
                headers={"Content-Type": "application/json"},
                data=json.dumps(task_data),
                timeout=30
            )
            
            if resp.status_code == 200:
                result = resp.json()
                task_id = result.get("id")
                logger.info(f"✅ 任务创建成功！任务ID: {task_id}")
                
                # 显示任务详情
                if "job_dir" in result:
                    logger.info(f"📂 任务目录: {result['job_dir']}")
                if "status" in result:
                    logger.info(f"📊 任务状态: {result['status']}")
                
                return task_id
            else:
                logger.error(f"❌ 任务创建失败 [{resp.status_code}]: {resp.text}")
                return None
                
        except Exception as e:
            logger.error(f"❌ 任务创建异常: {e}")
            return None
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态"""
        try:
            resp = self.session.get(
                f"{self.base_url}/peptide/optimize/{task_id}",
                timeout=10
            )
            
            if resp.status_code == 200:
                return resp.json()
            else:
                logger.error(f"❌ 获取任务状态失败 [{resp.status_code}]: {resp.text}")
                return None
                
        except Exception as e:
            logger.error(f"❌ 获取任务状态异常: {e}")
            return None
    
    def monitor_task_progress(self, task_id: str, max_wait_minutes: int = 60) -> bool:
        """监控任务进度"""
        logger.info(f"开始监控任务进度 (最大等待 {max_wait_minutes} 分钟)")
        
        start_time = time.time()
        max_wait_seconds = max_wait_minutes * 60
        check_interval = 30  # 30秒检查一次
        
        while True:
            try:
                # 检查是否超时
                elapsed = time.time() - start_time
                if elapsed > max_wait_seconds:
                    logger.warning(f"⏰ 监控超时 ({max_wait_minutes} 分钟)")
                    return False
                
                # 获取任务状态
                task_info = self.get_task_status(task_id)
                if not task_info:
                    logger.warning("⚠️  无法获取任务状态，继续等待...")
                    time.sleep(check_interval)
                    continue
                
                status = task_info.get("status", "unknown")
                elapsed_min = elapsed / 60
                
                logger.info(f"⏱️  [{elapsed_min:.1f}分钟] 任务状态: {status}")
                
                if status == "finished":
                    logger.info("🎉 任务完成！")
                    return True
                elif status == "failed":
                    logger.error("❌ 任务失败！")
                    return False
                elif status in ["pending", "running"]:
                    # 继续等待
                    time.sleep(check_interval)
                    continue
                else:
                    logger.warning(f"⚠️  未知状态: {status}")
                    time.sleep(check_interval)
                    continue
                    
            except KeyboardInterrupt:
                logger.info("👤 用户中断监控")
                return False
            except Exception as e:
                logger.warning(f"⚠️  监控过程中发生错误: {e}")
                time.sleep(check_interval)
                continue
        
        return False
    
    def get_task_config(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务配置"""
        try:
            resp = self.session.get(
                f"{self.base_url}/peptide/optimize/{task_id}/config",
                timeout=10
            )
            
            if resp.status_code == 200:
                return resp.json()
            else:
                logger.error(f"❌ 获取任务配置失败 [{resp.status_code}]: {resp.text}")
                return None
                
        except Exception as e:
            logger.error(f"❌ 获取任务配置异常: {e}")
            return None
    
    def get_task_results(self, task_id: str) -> None:
        """获取任务结果"""
        logger.info("正在获取任务结果...")
        
        # 获取任务状态
        task_info = self.get_task_status(task_id)
        if task_info:
            logger.info("📋 最终任务信息:")
            logger.info(json.dumps(task_info, indent=2, ensure_ascii=False))
            
            # 显示文件位置
            job_dir = task_info.get("job_dir")
            if job_dir:
                logger.info(f"\n📂 任务文件位置:")
                logger.info(f"   - 任务目录: {job_dir}")
                logger.info(f"   - 输出目录: {job_dir}/output/")
                logger.info(f"   - 结果文件: {job_dir}/output/result.csv")
        
        # 获取任务配置
        config_info = self.get_task_config(task_id)
        if config_info:
            logger.info("\n⚙️  任务配置:")
            logger.info(json.dumps(config_info, indent=2, ensure_ascii=False))
    
    def run_complete_workflow(self,
                             peptide_sequence: str,
                             receptor_pdb_file: str,
                             cores: int = 4,
                             cleanup: bool = False,
                             step: Optional[int] = None,
                             proteinmpnn_enabled: bool = True,
                             n_poses: int = 10,
                             n_iterations: int = 5,
                             n_rosetta_runs: int = 20,
                             max_wait_minutes: int = 60) -> bool:
        """运行完整的工作流程"""
        logger.info("🧬 开始Peptide优化完整工作流程")
        logger.info("=" * 60)
        
        # 1. 登录
        if not self.login():
            return False
        
        # 2. 上传受体文件
        receptor_filename = Path(receptor_pdb_file).name
        if not self.upload_pdb_file(receptor_pdb_file):
            # 检查文件是否已存在
            uploaded_files = self.list_uploaded_files()
            if not any(f.get('filename') == receptor_filename for f in uploaded_files):
                logger.error("❌ 受体文件上传失败且不在已上传列表中")
                return False
            else:
                logger.info(f"✅ 受体文件已存在: {receptor_filename}")
        
        # 3. 创建任务
        task_id = self.create_peptide_task(
            peptide_sequence=peptide_sequence,
            receptor_pdb_filename=receptor_filename,
            cores=cores,
            cleanup=cleanup,
            step=step,
            proteinmpnn_enabled=proteinmpnn_enabled,
            n_poses=n_poses,
            n_iterations=n_iterations,
            n_rosetta_runs=n_rosetta_runs
        )
        
        if not task_id:
            return False
        
        # 4. 监控任务进度
        success = self.monitor_task_progress(task_id, max_wait_minutes)
        
        # 5. 获取任务结果
        self.get_task_results(task_id)
        
        if success:
            logger.info("\n🎊 完整工作流程执行成功！")
        else:
            logger.warning("\n⚠️  工作流程未完全完成，但任务已创建")
        
        logger.info(f"\n💡 任务ID: {task_id}")
        logger.info("💡 你可以继续手动检查任务状态和结果文件")
        
        return success


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='通过API提交Peptide优化任务')
    
    # 必需参数
    parser.add_argument('--sequence', '-s', required=True, 
                       help='肽段序列（氨基酸单字母缩写）')
    parser.add_argument('--receptor', '-r', required=True,
                       help='受体PDB文件路径')
    
    # 可选参数
    parser.add_argument('--base-url', default='http://127.0.0.1:8000',
                       help='API服务器地址 (默认: http://127.0.0.1:8000)')
    parser.add_argument('--username', default='admin',
                       help='用户名 (默认: admin)')
    parser.add_argument('--password', default='Admin#2024',
                       help='密码 (默认: Admin#2024)')
    parser.add_argument('--cores', type=int, default=4,
                       help='CPU核心数 (默认: 4)')
    parser.add_argument('--cleanup', action='store_true',
                       help='完成后清理中间文件')
    parser.add_argument('--step', type=int, choices=range(1, 9),
                       help='只运行指定步骤 (1-8)，不指定则运行完整流程')
    parser.add_argument('--no-proteinmpnn', action='store_true',
                       help='禁用ProteinMPNN优化')
    parser.add_argument('--n-poses', type=int, default=10,
                       help='对接构象数量 (默认: 10)')
    parser.add_argument('--n-iterations', type=int, default=5,
                       help='优化迭代次数 (默认: 5)')
    parser.add_argument('--n-rosetta-runs', type=int, default=20,
                       help='每次迭代中Rosetta的运行次数 (默认: 20)')
    parser.add_argument('--max-wait', type=int, default=60,
                       help='最大等待时间(分钟) (默认: 60)')
    parser.add_argument('--only-upload', action='store_true',
                       help='只上传文件，不创建任务')
    parser.add_argument('--only-status', metavar='TASK_ID',
                       help='只查询指定任务的状态')
    parser.add_argument('--list-files', action='store_true',
                       help='列出已上传的文件')
    
    args = parser.parse_args()
    
    # 创建API客户端
    client = PeptideAPIClient(
        base_url=args.base_url,
        username=args.username,
        password=args.password
    )
    
    # 处理不同的操作模式
    if args.list_files:
        # 只列出文件
        if client.login():
            client.list_uploaded_files()
        return
    
    if args.only_status:
        # 只查询任务状态
        if client.login():
            task_info = client.get_task_status(args.only_status)
            if task_info:
                print(json.dumps(task_info, indent=2, ensure_ascii=False))
            client.get_task_results(args.only_status)
        return
    
    if args.only_upload:
        # 只上传文件
        if client.login():
            client.upload_pdb_file(args.receptor)
        return
    
    # 运行完整工作流程
    success = client.run_complete_workflow(
        peptide_sequence=args.sequence,
        receptor_pdb_file=args.receptor,
        cores=args.cores,
        cleanup=args.cleanup,
        step=args.step,
        proteinmpnn_enabled=not args.no_proteinmpnn,
        n_poses=args.n_poses,
        n_iterations=args.n_iterations,
        n_rosetta_runs=args.n_rosetta_runs,
        max_wait_minutes=args.max_wait
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
