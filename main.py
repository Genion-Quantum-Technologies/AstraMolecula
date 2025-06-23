import threading
from fastapi import FastAPI
from routers import auth, tasks, uploads, smiles, docking
from task_worker import main_loop

app = FastAPI()
app.include_router(auth.router)
app.include_router(uploads.router)
app.include_router(smiles.router)
app.include_router(docking.router)
app.include_router(tasks.router)

@app.on_event("startup")
def launch_worker():
    threading.Thread(target=main_loop, daemon=True).start()