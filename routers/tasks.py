import io
from pathlib import Path
import json
import zipfile
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse

from database.services import TaskService
from security.auth import get_current_user

router = APIRouter(prefix="/tasks", tags=["Tasks"])

@router.get("/{task_id}")
async def get_task_result(task_id: str, current_user = Depends(get_current_user)):
    task = TaskService.get_task(task_id)
    if not task or task.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="task not found")
    if task.status != "finished":
        return {"status": task.status}
    job_dir = Path(task.job_dir)
    if task.task_type == "generate":
        output = job_dir / "output.json"
        if not output.exists():
            raise HTTPException(status_code=500, detail="output not found")
        with open(output, "r", encoding="utf-8") as f:
            data = json.load(f)
        return JSONResponse(content={"status": task.status, "result": data})
    elif task.task_type == "docking":
        csv_file = job_dir / "dockRes.csv"
        if not csv_file.exists():
            raise HTTPException(status_code=500, detail="result csv not found")
        df = pd.read_csv(csv_file)
        records = df.to_dict(orient="records")
        return JSONResponse(content={"status": task.status, "results": records})
    else:
        raise HTTPException(status_code=400, detail="unknown task type")
    
@router.get("/{task_id}/download")
async def download_task_files(task_id: str, current_user = Depends(get_current_user)):
    """Download result files of a finished task as a zip archive."""
    task = TaskService.get_task(task_id)
    if not task or task.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="task not found")
    if task.status != "finished":
        raise HTTPException(status_code=400, detail="task not finished")
    job_dir = Path(task.job_dir)
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail="job directory missing")

    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, "w") as zf:
        for item in job_dir.iterdir():
            if item.is_file():
                zf.write(item, arcname=item.name)
    memory_file.seek(0)
    filename = f"{task_id}.zip"
    return StreamingResponse(
        memory_file,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )