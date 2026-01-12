"""
异步任务处理器
支持并发处理和进度更新
支持 SeaweedFS 对象存储
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
from services.storage import get_storage
from config import ROOT, storage as storage_config

logger = logging.getLogger("async_task_processor")


class TaskProgressCallback:
    """任务进度回调类"""
    
    def __init__(self, task_id: str):
        self.task_id = task_id
        self._is_completed = False  # 添加完成标志
        
    def update_progress(self, progress: float, info: str = None):
        """更新任务进度"""
        # 如果任务已完成，不再更新状态
        if self._is_completed:
            logger.debug("Task %s already completed, skipping progress update", self.task_id)
            return
            
        try:
            # 检查当前任务状态，避免覆盖终态状态
            current_task = TaskService.get_task(self.task_id)
            if current_task and current_task.status in ["finished", "failed", "cancelled"]:
                logger.debug("Task %s is in final state (%s), skipping progress update", 
                           self.task_id, current_task.status)
                self._is_completed = True
                return
                
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
    
    def mark_completed(self):
        """标记任务已完成，停止后续进度更新"""
        self._is_completed = True


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
                # docking 任务不在此处处理，交给 dockingVinaApp
                logger.info("Docking task %s delegated to dockingVinaApp", task_id)
                return
            else:
                raise ValueError(f"Unknown task type: {task.task_type}")
            
            self.running_tasks[task_id] = result_task
            
            # 等待任务完成
            await result_task
            
            # 任务成功完成
            TaskService.update_task_status(
                task_id, TaskStatus.FINISHED, "Task completed successfully"
            )
            # 标记进度回调已完成，防止后续更新覆盖状态
            progress_callback.mark_completed()
            logger.info("Task %s completed successfully", task_id)
            
        except asyncio.CancelledError:
            TaskService.update_task_status(
                task_id, TaskStatus.CANCELLED, "Task was cancelled"
            )
            progress_callback.mark_completed()
            logger.info("Task %s was cancelled", task_id)
            
        except Exception as e:
            error_msg = f"Task failed: {str(e)}"
            TaskService.update_task_status(
                task_id, TaskStatus.FAILED, "Task failed"
            )
            progress_callback.mark_completed()
            logger.exception("Task %s failed: %s", task_id, e)
            
        finally:
            # 清理
            if task_id in self.running_tasks:
                del self.running_tasks[task_id]
            if task_id in self.task_locks:
                del self.task_locks[task_id]
    
    async def _process_generate_async(self, task: Task, callback: TaskProgressCallback) -> None:
        """异步处理生成任务"""
        storage = get_storage()
        storage_prefix = task.job_dir  # job_dir 现在存储的是 SeaweedFS 路径
        
        callback.update_progress(10.0, "Loading input parameters")
        
        # 从 SeaweedFS 下载 input.json
        input_remote_key = f"{storage_prefix}/input.json"
        try:
            input_data = await storage.download_bytes(input_remote_key)
            params = json.loads(input_data.decode('utf-8'))
            logger.info("Task %s: Loaded input.json from SeaweedFS: %s", task.id, input_remote_key)
        except FileNotFoundError:
            logger.error("Task %s: input.json not found in SeaweedFS: %s", task.id, input_remote_key)
            raise Exception(f"Input file not found: {input_remote_key}")
        except Exception as e:
            logger.error("Task %s: Failed to load input.json: %s", task.id, e)
            raise
        
        callback.update_progress(20.0, "Preparing generation model")
        
        # 在线程池中运行CPU密集型任务
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            self.thread_executor,
            self._run_generate_with_progress,
            params, callback
        )
        
        callback.update_progress(90.0, "Saving results to SeaweedFS")
        
        # 将结果直接上传到 SeaweedFS（不再保存到本地）
        output_json_bytes = json.dumps(result, ensure_ascii=False, indent=2).encode('utf-8')
        output_remote_key = f"{storage_prefix}/output.json"
        
        await storage.upload_bytes(output_json_bytes, output_remote_key, content_type="application/json")
        logger.info("Task %s: Results uploaded to SeaweedFS: %s", task.id, output_remote_key)
            
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
                # 在新线程中处理任务，避免阻塞主循环
                import threading
                thread = threading.Thread(
                    target=_process_task_sync, 
                    args=(task,), 
                    daemon=True
                )
                thread.start()
                
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            
        # 等待5秒后继续检查
        time.sleep(5)


def _process_task_sync(task):
    """同步处理任务的包装函数"""
    try:
        # 在新的事件循环中运行异步任务
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(task_processor.process_task(task))
        finally:
            loop.close()
    except Exception as e:
        logger.error(f"Error processing task {task.id}: {e}")


# 全局任务处理器实例
task_processor = AsyncTaskProcessor()
