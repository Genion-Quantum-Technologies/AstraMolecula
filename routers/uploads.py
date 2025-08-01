
import logging
from typing import List
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from database.services.upload_service import UploadService
from security.auth import get_current_user
import config

logger = logging.getLogger("uploads_router")
router = APIRouter(tags=["Uploads"])

@router.get("/users/me/uploads")
async def list_my_uploads(request: Request):
    current_user = request.state.user
    logger.info("User %s listing uploads", current_user.username)
    uploads = UploadService.list_by_user(current_user.id)
    logger.debug("Found %d uploads for user %s", len(uploads), current_user.username)
    return [u.__dict__ for u in uploads]

@router.post("/upload_pdbqt")
async def upload_pdbqt(
    request: Request,
    files: List[UploadFile] = File(...)
):
    current_user = request.state.user
    user_id = current_user.id
    logger.info("User %s uploading %d PDBQT files", current_user.username, len(files))
    UPLOAD_DIR = config.ROOT / "uploads" / user_id
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    saved = []
    for f in files:
        allowed_extensions = [".pdb", ".pdbqt"]
        if not any(f.filename.endswith(ext) for ext in allowed_extensions):
            raise HTTPException(status_code=400, detail=f"不支持的文件类型: {f.filename}")
        dest = UPLOAD_DIR / f.filename
        with open(dest, "wb") as fh:
            fh.write(await f.read())
        saved.append(dest.name)
        UploadService.record_upload(
            user_id=user_id,
            filename=dest.name,
            file_path=str(dest)
        )
    return {"message": "上传成功", "user_id": user_id, "files": saved}