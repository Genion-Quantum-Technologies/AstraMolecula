from contextlib import asynccontextmanager
import threading
import logging
from fastapi import FastAPI
from middleware import auth_middleware
from routers import auth, tasks, uploads, smiles, docking
from async_task_processor import main_loop
from config.logging_config import setup_logging
from async_task_processor import AsyncTaskProcessor

# 设置日志系统
setup_logging(level="INFO")
logger = logging.getLogger(__name__)

# 全局异步任务处理器
async_processor = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # —— 应用启动时执行 —— 
    global async_processor
    
    logger.info("Starting application...")
    
    # 初始化异步任务处理器
    logger.info("Initializing async task processor...")
    async_processor = AsyncTaskProcessor()
    
    # 启动传统任务工作线程（用于兼容现有系统）
    logger.info("Starting background task worker thread...")
    thread = threading.Thread(target=main_loop, daemon=True)
    thread.start()
    
    logger.info("Application startup complete")
    yield
    
    # —— 应用关闭时执行 ——
    logger.info("Shutting down application...")
    if async_processor:
        await async_processor.shutdown()
    logger.info("Application shutdown complete")

app = FastAPI(
    lifespan=lifespan,
    title="DockingVina API", 
    description="Molecular docking and generation service with real-time progress tracking",
    version="2.0.0"
)

# 添加中间件
app.middleware("http")(auth_middleware)

# 注册路由
app.include_router(auth.router)
app.include_router(uploads.router)
app.include_router(smiles.router)
app.include_router(docking.router)
app.include_router(tasks.router)

# 全局访问异步处理器的函数
def get_async_processor() -> AsyncTaskProcessor:
    """获取全局异步任务处理器实例"""
    global async_processor
    if async_processor is None:
        raise RuntimeError("Async processor not initialized")
    return async_processor
