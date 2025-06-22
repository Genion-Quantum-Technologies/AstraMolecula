from fastapi import FastAPI
from routers import auth, uploads, smiles, docking

app = FastAPI()
app.include_router(auth.router)
app.include_router(uploads.router)
app.include_router(smiles.router)
app.include_router(docking.router)
