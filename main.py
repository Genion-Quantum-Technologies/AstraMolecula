from contextlib import asynccontextmanager
import threading
from fastapi import FastAPI
from middleware import auth_middleware
from routers import auth, tasks, uploads, smiles, docking
from task_worker import main_loop

@asynccontextmanager
async def lifespan(app: FastAPI):
    # —— 应用启动时执行 —— 
    thread = threading.Thread(target=main_loop, daemon=True)
    thread.start()
    yield

app = FastAPI(lifespan=lifespan)

app.middleware("http")(auth_middleware)

app.include_router(auth.router)
app.include_router(uploads.router)
app.include_router(smiles.router)
app.include_router(docking.router)
app.include_router(tasks.router)
