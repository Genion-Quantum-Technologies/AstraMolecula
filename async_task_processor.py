"""
异步任务处理器
支持并发处理和进度更新
"""

import asyncio
import logging
import json
import time
from pathlib import Path
from typing import Optional, Dict, Any, Callable
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from database.services import TaskService
from database.models.task import Task, TaskStatus
from utils.tools import run_generate_runner
from Vina.vina_workflow import vina_docking_from_list
import config

logger = logging.getLogger("async_task_processor")


class TaskProgressCallback:
    """任务进度回调类"""
    
    def __init__(self, task_id: str):
        self.task_id = task_id
        
    def update_progress(self, progress: float, info: str = None):
        """更新任务进度"""
        try:
            TaskService.update_task_status(
                self.task_id, 
                TaskStatus.PROCESSING, 
                info
            )
            logger.debug("Task %s progress updated: %.1f%% - %s", 
                        self.task_id, progress, info or "")
        except Exception as e:
            logger.error("Failed to update progress for task %s: %s", 
                        self.task_id, e)


class AsyncTaskProcessor:
    """异步任务处理器"""
    
    def __init__(self, max_workers: int = 3, max_concurrent_docking: int = 2):
        self.max_workers = max_workers
        self.max_concurrent_docking = max_concurrent_docking
        self.thread_executor = ThreadPoolExecutor(max_workers=max_workers)
        self.process_executor = ProcessPoolExecutor(max_workers=max_concurrent_docking)
        self.running_tasks: Dict[str, asyncio.Task] = {}
        self.task_locks: Dict[str, asyncio.Lock] = {}
        
    async def process_task(self, task: Task) -> None:
        """处理单个任务"""
        task_id = task.id
        
        # 防止重复处理
        if task_id in self.running_tasks:
            logger.warning("Task %s is already being processed", task_id)
            return
            
        logger.info("Starting async processing for task %s (type: %s)", 
                   task_id, task.task_type)
        
        try:
            # 更新任务状态为运行中
            TaskService.update_task_status(task_id, TaskStatus.RUNNING, "Task started")
            
            # 创建进度回调
            progress_callback = TaskProgressCallback(task_id)
            
            # 根据任务类型选择处理器
            if task.task_type == "generate":
                result_task = asyncio.create_task(
                    self._process_generate_async(task, progress_callback)
                )
            elif task.task_type == "docking":
                result_task = asyncio.create_task(
                    self._process_docking_async(task, progress_callback)
                )
            else:
                raise ValueError(f"Unknown task type: {task.task_type}")
            
            self.running_tasks[task_id] = result_task
            
            # 等待任务完成
            await result_task
            
            # 任务成功完成
            TaskService.update_task_status(
                task_id, TaskStatus.FINISHED, "Task completed successfully"
            )
            logger.info("Task %s completed successfully", task_id)
            
        except asyncio.CancelledError:
            TaskService.update_task_status(
                task_id, TaskStatus.CANCELLED, "Task was cancelled"
            )
            logger.info("Task %s was cancelled", task_id)
            
        except Exception as e:
            error_msg = f"Task failed: {str(e)}"
            TaskService.update_task_status(
                task_id, TaskStatus.FAILED, "Task failed"
            )
            logger.exception("Task %s failed: %s", task_id, e)
            
        finally:
            # 清理
            if task_id in self.running_tasks:
                del self.running_tasks[task_id]
            if task_id in self.task_locks:
                del self.task_locks[task_id]
    
    async def _process_generate_async(self, task: Task, callback: TaskProgressCallback) -> None:
        """异步处理生成任务"""
        job_dir = Path(task.job_dir)
        input_json = job_dir / "input.json"
        
        callback.update_progress(10.0, "Loading input parameters")
        
        with open(input_json, "r", encoding="utf-8") as f:
            params = json.load(f)
        
        callback.update_progress(20.0, "Preparing generation model")
        
        # 在线程池中运行CPU密集型任务
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            self.thread_executor,
            self._run_generate_with_progress,
            params, callback
        )
        
        callback.update_progress(90.0, "Saving results")
        
        # 保存结果
        output_path = job_dir / "output.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
            
        callback.update_progress(100.0, "Generation completed")
    
    def _run_generate_with_progress(self, params: dict, callback: TaskProgressCallback) -> list:
        """带进度的生成任务运行器"""
        try:
            callback.update_progress(30.0, "Initializing generation")
            
            # 处理 generateRequestList 格式
            if 'generateRequestList' in params:
                # 取第一个请求作为主要参数
                request_list = params['generateRequestList']
                if not request_list:
                    raise ValueError("generateRequestList is empty")
                
                first_request = request_list[0]
                const_smiles = first_request.get('constSmiles', '')
                var_smiles = first_request.get('varSmiles', '')
                main_cls = first_request.get('mainCls', 'activity')
                minor_cls = first_request.get('minorCls', 'IC50')
                delta_value = first_request.get('deltaValue', '(-inf, -10.5]')
                num_samples = int(first_request.get('num', 3))
                
                # 收集所有变化部分
                all_var_smiles = []
                for req in request_list:
                    var_smile = req.get('varSmiles', '')
                    if var_smile and var_smile not in all_var_smiles:
                        all_var_smiles.append(var_smile)
                
                # 如果没有收集到变化部分，使用第一个
                if not all_var_smiles:
                    all_var_smiles = [var_smiles] if var_smiles else ['CC']
                
            else:
                # 旧格式兼容
                const_smiles = params.get('constSmiles') or params.get('constantSMILES', '')
                var_smiles_raw = params.get('varSmiles') or params.get('fromVarSMILES', [])
                main_cls = params.get('mainCls', params.get('main_cls', 'activity'))
                minor_cls = params.get('minorCls', params.get('minor_cls', 'IC50'))
                delta_value = params.get('deltaValue', params.get('Delta_Value', '(-inf, -10.5]'))
                num_samples = int(params.get('num', params.get('num_samples', 3)))
                
                # 确保 var_smiles 是列表
                if isinstance(var_smiles_raw, str):
                    all_var_smiles = [var_smiles_raw]
                else:
                    all_var_smiles = var_smiles_raw
            
            logger.info("生成参数: const_smiles=%s, var_smiles=%s, num_samples=%d", 
                       const_smiles, all_var_smiles, num_samples)
            
            # 确保参数格式正确
            if not const_smiles:
                raise ValueError("constantSMILES is required")
            if not all_var_smiles:
                raise ValueError("fromVarSMILES is required")
            
            # 将 var_smiles 列表转换为字符串（取第一个或连接）
            var_smiles_str = all_var_smiles[0] if all_var_smiles else ""
            
            # 转换参数为 run_generate_runner 期望的格式
            result = run_generate_runner(
                const_smiles=const_smiles,      # 内部会转换为 constantSMILES
                var_smiles=var_smiles_str,      # 内部会转换为 fromVarSMILES（字符串格式）
                main_cls=main_cls,
                minor_cls=minor_cls,
                delta_value=delta_value,
                num_samples=num_samples
            )
            
            callback.update_progress(80.0, f"Generated {len(result)} molecules")
            return result
            
        except Exception as e:
            logger.exception("Generation failed: %s", e)
            raise
    
    async def _process_docking_async(self, task: Task, callback: TaskProgressCallback) -> None:
        """异步处理对接任务"""
        job_dir = Path(task.job_dir)
        input_json = job_dir / "input.json"
        
        callback.update_progress(10.0, "Loading docking parameters")
        
        with open(input_json, "r", encoding="utf-8") as f:
            params = json.load(f)
        
        callback.update_progress(20.0, "Preparing docking environment")
        
        # 使用线程池而不是进程池来避免序列化问题
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            self.thread_executor,
            self._run_docking_with_progress,
            params, str(job_dir), task.id
        )
        
        callback.update_progress(90.0, "Docking completed")
        
        # vina_docking_from_list 已经创建了 dockRes.json 文件
        # 检查文件是否存在
        output_path = job_dir / "dockRes.json"
        if not output_path.exists():
            raise RuntimeError("Docking completed but dockRes.json was not created")
            
        callback.update_progress(100.0, "Results saved")
    
    def _run_docking_with_progress(self, params: dict, job_dir: str, task_id: str) -> str:
        """带进度的对接任务运行器"""
        try:
            # 从参数中提取配体信息
            ligands = params.get('ligands', [])
            if not ligands:
                raise ValueError("No ligands provided")
            
            # 获取受体文件路径
            receptor_pdbqt = params.get('receptor_pdbqt', '')
            if not receptor_pdbqt:
                raise ValueError("No receptor file specified")
            
            # 获取pH参数
            min_ph = float(params.get('min_ph', 6.0))
            max_ph = float(params.get('max_ph', 8.0))
            n_jobs = int(params.get('n_jobs', 1))
            
            # 获取中心坐标和盒子大小参数 (都是必填项)
            center_x = float(params['center_x'])
            center_y = float(params['center_y'])
            center_z = float(params['center_z'])
            
            # 获取盒子大小参数 (必填的xyz三个维度)
            size_x = float(params['box_size_x'])
            size_y = float(params['box_size_y'])
            size_z = float(params['box_size_z'])
            
            # 获取其他可选参数
            exhaustiveness = int(params.get('exhaustiveness', 4))
            n_poses = int(params.get('n_poses', 20))
            
            logger.info("Docking parameters: ligands=%d, receptor=%s, pH=[%.1f-%.1f], jobs=%d, center=[%.2f,%.2f,%.2f], size=[%.2f,%.2f,%.2f]", 
                       len(ligands), receptor_pdbqt, min_ph, max_ph, n_jobs, center_x, center_y, center_z, size_x, size_y, size_z)
            
            # 创建临时的 vina_box.json 文件
            import shutil
            from pathlib import Path
            
            # 备份原始的 vina_box.json
            original_box_json = Path(__file__).parent / "resource" / "vina_box.json"
            backup_path = None
            if original_box_json.exists():
                backup_path = original_box_json.with_suffix('.json.backup')
                shutil.copy2(original_box_json, backup_path)
            
            # 创建新的 box 配置
            box_config = {
                "center": [center_x, center_y, center_z],
                "box_size": [size_x, size_y, size_z],
                "exhaustiveness": exhaustiveness,
                "n_poses": n_poses
            }
            
            # 写入临时配置
            with open(original_box_json, 'w') as f:
                json.dump(box_config, f, indent=2)
            
            try:
                # 创建简单的进度更新机制
                def progress_updater():
                    for i in range(30, 80, 10):
                        time.sleep(5)  # 模拟处理时间
                        try:
                            TaskService.update_task_status(
                                task_id, TaskStatus.PROCESSING, f"Docking in progress ({i}%)"
                            )
                        except:
                            pass
                
                import threading
                progress_thread = threading.Thread(target=progress_updater, daemon=True)
                progress_thread.start()
                
                # 调用实际的docking函数
                result_dir = vina_docking_from_list(
                    ligands=ligands,
                    receptor_pdbqt=receptor_pdbqt,
                    min_ph=min_ph,
                    max_ph=max_ph,
                    n_jobs=n_jobs
                )
                
                # vina_docking_from_list 返回的是结果目录路径
                # 需要将 dockRes.json 和相关文件复制到任务目录
                import shutil
                source_result_file = Path(result_dir) / "dockRes.json"
                target_result_file = Path(job_dir) / "dockRes.json"
                
                if source_result_file.exists():
                    shutil.copy2(source_result_file, target_result_file)
                    logger.info("Copied dockRes.json from %s to %s", source_result_file, target_result_file)
                else:
                    raise RuntimeError(f"dockRes.json not found in result directory: {result_dir}")
                
                # 复制docked目录及其内容到任务目录
                source_docked_dir = Path(result_dir) / "docked"
                target_docked_dir = Path(job_dir) / "docked"
                
                if source_docked_dir.exists():
                    if target_docked_dir.exists():
                        shutil.rmtree(target_docked_dir)
                    shutil.copytree(source_docked_dir, target_docked_dir)
                    logger.info("Copied docked directory from %s to %s", source_docked_dir, target_docked_dir)
                else:
                    logger.warning("Source docked directory not found: %s", source_docked_dir)
                
                return str(result_dir)
            
            finally:
                # 恢复原始的 vina_box.json
                if backup_path and backup_path.exists():
                    shutil.move(backup_path, original_box_json)
            
        except Exception as e:
            logger.exception("Docking failed: %s", e)
            raise
    
    async def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        if task_id in self.running_tasks:
            self.running_tasks[task_id].cancel()
            logger.info("Task %s cancellation requested", task_id)
            return True
        return False
    
    def get_running_tasks(self) -> list:
        """获取正在运行的任务列表"""
        return list(self.running_tasks.keys())
    
    async def shutdown(self):
        """关闭处理器"""
        logger.info("Shutting down async task processor")
        
        # 取消所有运行中的任务
        for task_id, task in self.running_tasks.items():
            task.cancel()
        
        # 等待所有任务完成
        if self.running_tasks:
            await asyncio.gather(*self.running_tasks.values(), return_exceptions=True)
        
        # 关闭执行器
        self.thread_executor.shutdown(wait=True)
        self.process_executor.shutdown(wait=True)
        
        logger.info("Async task processor shutdown complete")


def main_loop():
    """
    兼容旧系统的主循环函数
    定期检查并处理pending状态的任务
    """
    import time
    from database.services import TaskService
    
    logger.info("Task worker main loop started")
    
    while True:
        try:
            # 获取pending状态的任务
            pending_tasks = TaskService.fetch_pending(limit=5)
            
            for task in pending_tasks:
                logger.info(f"Processing pending task {task.id}")
                # 使用全局任务处理器异步处理任务
                asyncio.run(task_processor.process_task(task))
                
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            
        # 等待5秒后继续检查
        time.sleep(5)


# 全局任务处理器实例
task_processor = AsyncTaskProcessor()
