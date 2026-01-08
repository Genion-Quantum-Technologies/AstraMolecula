from contextlib import asynccontextmanager
import threading
import logging
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from middleware import auth_middleware
from routers import auth, tasks, uploads, smiles, docking, peptide, logs, admin, public, payments
from config import setup_logging, server, cors as cors_config
from async_task_processor import AsyncTaskProcessor

# 设置日志系统（从配置文件读取日志级别）
setup_logging()
logger = logging.getLogger(__name__)

# 全局异步任务处理器
async_processor = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # —— 应用启动时执行 —— 
    global async_processor
    
    logger.info("Starting application...")
    
    # 初始化异步任务处理器（仅处理生成任务）
    logger.info("Initializing async task processor...")
    async_processor = AsyncTaskProcessor()
    
    # docking 任务不在此处处理，由 dockingVinaApp 负责
    # 本应用只负责接收 docking 任务请求并创建任务记录
    logger.info("DockingVina configured to delegate docking tasks to dockingVinaApp")
    
    logger.info("Application startup complete")
    yield
    
    # —— 应用关闭时执行 ——
    logger.info("Shutting down application...")
    if async_processor:
        await async_processor.shutdown()
    logger.info("Application shutdown complete")

app = FastAPI(
    lifespan=lifespan,
    title=server.title, 
    description=server.description,
    version=server.version
)

# 添加CORS中间件 - 必须在其他中间件之前（配置从 settings.yaml 读取）
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_config.allow_origins,
    allow_credentials=cors_config.allow_credentials,
    allow_methods=cors_config.allow_methods,
    allow_headers=cors_config.allow_headers,
)

# 添加认证中间件
app.middleware("http")(auth_middleware)

# 健康检查端点（无需认证）
@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {
        "status": "healthy",
        "message": f"{server.title} is running",
        "version": server.version
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
app.include_router(public.router)     # 公开访问路由（无需认证，最先注册）
app.include_router(payments.router)   # 支付接口
app.include_router(tasks.router)      # 最高优先级，任务查询接口
app.include_router(auth.router)       # 认证接口
app.include_router(admin.router)      # 管理员接口
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
