
from typing import List
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from config import ROOT
from database.services.upload_service import UploadService
from security.auth import get_current_user

router = APIRouter(tags=["Uploads"])

@router.get("/users/me/uploads")
async def list_my_uploads(current_user=Depends(get_current_user)):
    uploads = UploadService.list_by_user(current_user.id)
    return [u.__dict__ for u in uploads]

@router.post("/upload_pdbqt")
async def upload_pdbqt(
    files: List[UploadFile] = File(...),
    current_user = Depends(get_current_user),       # ← 使用 token 校验
):
    """
    只有拿到合法 Token（通过 /token 获得）的用户才能上传，
    上传文件会保存到 uploads/{user_id}/ 目录下。
    """
    user_id = current_user.id
    UPLOAD_DIR = ROOT / "uploads" / user_id
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    saved = []
    for f in files:
        if not f.filename.endswith(".pdbqt"):
            raise HTTPException(status_code=400, detail=f"不支持的文件类型: {f.filename}")
        dest = UPLOAD_DIR / f.filename
        with open(dest, "wb") as fh:
            fh.write(await f.read())
        saved.append(dest.name)
        # —— 新增：把记录写入数据库 —— 
        UploadService.record_upload(
            user_id=current_user.id,
            filename=dest.name,
            file_path=str(dest)
        )
    return {"message": "上传成功", "user_id": user_id, "files": saved}