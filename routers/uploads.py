
import logging
from typing import List
from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from database.services.upload_service import UploadService
from services.storage import get_storage
from config import ROOT

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
    
    # 详细日志：记录上传请求信息
    filenames = [f.filename for f in files]
    logger.info("User %s (user_id: %s) uploading %d PDBQT files: %s", 
                current_user.username, user_id, len(files), filenames)
    
    # 获取存储服务
    storage = get_storage()

    saved = []
    for f in files:
        allowed_extensions = [".pdb", ".pdbqt"]
        if not any(f.filename.endswith(ext) for ext in allowed_extensions):
            logger.warning("User %s upload rejected - unsupported file type: %s", 
                          current_user.username, f.filename)
            raise HTTPException(status_code=400, detail=f"不支持的文件类型: {f.filename}")
        
        # 读取文件内容
        content = await f.read()
        
        # 上传到 SeaweedFS
        remote_key = f"uploads/{user_id}/{f.filename}"
        await storage.upload_bytes(content, remote_key)
        
        saved.append(f.filename)
        
        # 记录上传信息（storage_key 替代 file_path）
        UploadService.record_upload(
            user_id=user_id,
            filename=f.filename,
            file_path=remote_key,  # 现在存储的是 remote_key
            file_size=len(content),
            content_type=f.content_type
        )
        logger.info("User %s uploaded file: %s (size: %d bytes, storage_key: %s)", 
                   current_user.username, f.filename, len(content), remote_key)
    
    logger.info("User %s upload complete - %d files saved: %s", 
               current_user.username, len(saved), saved)
    return {"message": "上传成功", "user_id": user_id, "files": saved, "name": saved[0] if len(saved) == 1 else saved}