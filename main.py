from contextlib import asynccontextmanager
import threading
import logging
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from middleware import auth_middleware
from routers import auth, tasks, uploads, smiles, docking, peptide, logs
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
    # 注意：已禁用旧的轮询机制以避免与新异步处理器冲突
    # logger.info("Starting background task worker thread...")
    # thread = threading.Thread(target=main_loop, daemon=True)
    # thread.start()
    logger.info("Legacy task worker disabled - using new async processor only")
    
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

# 添加CORS中间件 - 必须在其他中间件之前
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "*"],  # 允许前端域名
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# 添加认证中间件
app.middleware("http")(auth_middleware)

# 健康检查端点（无需认证）
@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {
        "status": "healthy",
        "message": "DockingVina API is running",
        "timestamp": "2025-08-27T14:40:00Z",
        "version": "2.0.0"
    }

# 根路径重定向到日志查看器
@app.get("/")
async def root():
    """根路径重定向到日志查看器"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/static/log-viewer.html")

# 全局异常处理器
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """处理HTTP异常，提供更友好的错误响应"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": f"HTTP {exc.status_code}",
            "message": exc.detail,
            "path": request.url.path,
            "method": request.method,
            "error_code": f"HTTP_{exc.status_code}"
        },
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "Authorization, X-API-Key, Content-Type"
        }
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """处理请求验证错误"""
    return JSONResponse(
        status_code=422,
        content={
            "error": "Validation Error",
            "message": "Request validation failed",
            "details": exc.errors(),
            "path": request.url.path,
            "method": request.method,
            "error_code": "VALIDATION_ERROR"
        },
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "Authorization, X-API-Key, Content-Type"
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """处理其他未捕获的异常"""
    logger.exception("Unhandled exception occurred: %s", exc)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred. Please try again later.",
            "path": request.url.path,
            "method": request.method,
            "error_code": "INTERNAL_SERVER_ERROR",
            "suggestion": "Please contact the administrator if this error persists."
        },
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "Authorization, X-API-Key, Content-Type"
        }
    )

# 注册路由 - 按优先级顺序排列，tasks路由优先
app.include_router(tasks.router)      # 最高优先级，任务查询接口
app.include_router(auth.router)       # 认证接口
app.include_router(uploads.router)    # 上传接口
app.include_router(smiles.router)     # 生成接口
app.include_router(peptide.router)    # 蛋白优化接口
app.include_router(docking.router)    # 对接接口（计算密集型，最后处理）
app.include_router(logs.router)       # 日志查看接口（免认证）

# 挂载静态文件目录（用于提供日志查看器等静态资源）
try:
    from pathlib import Path
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=static_dir), name="static")
        logger.info(f"Static files mounted at /static from {static_dir}")
    else:
        logger.warning(f"Static directory not found: {static_dir}")
except Exception as e:
    logger.error(f"Failed to mount static files: {e}")

# 全局访问异步处理器的函数
def get_async_processor() -> AsyncTaskProcessor:
    """获取全局异步任务处理器实例"""
    global async_processor
    if async_processor is None:
        raise RuntimeError("Async processor not initialized")
    return async_processor
