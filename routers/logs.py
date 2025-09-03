import os
from pathlib import Path
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse, PlainTextResponse
from config import ROOT

router = APIRouter(prefix="/logs", tags=["Logs"])

# 允许查看的日志文件列表（安全性考虑）
ALLOWED_LOG_FILES = {
    "docking_service.log": ROOT / "logs" / "docking_service.log",
    "tasks.log": ROOT / "logs" / "tasks.log",
}

@router.get("/", 
           summary="获取可查看的日志文件列表",
           description="返回系统中可以查看的日志文件列表")
async def list_log_files():
    """获取可查看的日志文件列表"""
    available_logs = []
    
    for log_name, log_path in ALLOWED_LOG_FILES.items():
        if log_path.exists():
            # 获取文件大小和修改时间
            stat = log_path.stat()
            available_logs.append({
                "name": log_name,
                "size": stat.st_size,
                "modified": stat.st_mtime,
                "path": f"/logs/{log_name}"
            })
    
    return {
        "available_logs": available_logs,
        "count": len(available_logs)
    }

@router.get("/docking_service.log",
           response_class=PlainTextResponse,
           summary="查看对接服务日志",
           description="查看对接服务的实时日志，支持行数限制和实时查看")
async def get_docking_service_log(
    lines: Optional[int] = Query(100, description="返回最后N行日志，默认100行"),
    format: Optional[str] = Query("text", description="返回格式：text或json")
):
    """查看对接服务日志"""
    return await get_log_content("docking_service.log", lines, format)

@router.get("/tasks.log",
           response_class=PlainTextResponse,
           summary="查看任务日志",
           description="查看任务处理的日志")
async def get_tasks_log(
    lines: Optional[int] = Query(100, description="返回最后N行日志，默认100行"),
    format: Optional[str] = Query("text", description="返回格式：text或json")
):
    """查看任务日志"""
    return await get_log_content("tasks.log", lines, format)

@router.get("/{log_name}",
           summary="查看指定日志文件",
           description="查看指定的日志文件内容")
async def get_log_file(
    log_name: str,
    lines: Optional[int] = Query(100, description="返回最后N行日志，默认100行"),
    format: Optional[str] = Query("text", description="返回格式：text或json")
):
    """查看指定日志文件"""
    return await get_log_content(log_name, lines, format)

async def get_log_content(log_name: str, lines: int, format: str):
    """获取日志内容的通用方法"""
    # 安全性检查：只允许访问预定义的日志文件
    if log_name not in ALLOWED_LOG_FILES:
        raise HTTPException(
            status_code=404, 
            detail=f"Log file '{log_name}' not found or not accessible. Available files: {list(ALLOWED_LOG_FILES.keys())}"
        )
    
    log_path = ALLOWED_LOG_FILES[log_name]
    
    if not log_path.exists():
        raise HTTPException(
            status_code=404, 
            detail=f"Log file '{log_name}' does not exist"
        )
    
    try:
        # 读取文件的最后N行
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            all_lines = f.readlines()
        
        # 限制行数
        if lines and lines > 0:
            content_lines = all_lines[-lines:]
        else:
            content_lines = all_lines
        
        if format == "json":
            # 返回JSON格式
            log_entries = []
            for i, line in enumerate(content_lines):
                log_entries.append({
                    "line_number": len(all_lines) - len(content_lines) + i + 1,
                    "content": line.rstrip('\n\r')
                })
            
            return JSONResponse({
                "log_file": log_name,
                "total_lines": len(all_lines),
                "returned_lines": len(content_lines),
                "entries": log_entries
            })
        else:
            # 返回纯文本格式
            content = ''.join(content_lines)
            return PlainTextResponse(
                content=content,
                headers={
                    "X-Log-File": log_name,
                    "X-Total-Lines": str(len(all_lines)),
                    "X-Returned-Lines": str(len(content_lines))
                }
            )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error reading log file: {str(e)}"
        )

@router.get("/live/docking_service",
           summary="实时查看对接服务日志",
           description="获取对接服务日志的最新内容，适合用于实时监控")
async def get_live_docking_log(
    lines: int = Query(50, description="返回最后N行日志")
):
    """实时查看对接服务日志 - 返回最新内容"""
    log_path = ALLOWED_LOG_FILES["docking_service.log"]
    
    if not log_path.exists():
        return JSONResponse({
            "status": "file_not_found",
            "message": "Log file does not exist yet",
            "entries": []
        })
    
    try:
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            all_lines = f.readlines()
        
        recent_lines = all_lines[-lines:] if lines > 0 else all_lines
        
        log_entries = []
        for i, line in enumerate(recent_lines):
            # 尝试解析日志级别和时间戳
            line_content = line.rstrip('\n\r')
            log_level = "INFO"  # 默认级别
            
            if "ERROR" in line_content:
                log_level = "ERROR"
            elif "WARNING" in line_content:
                log_level = "WARNING"
            elif "DEBUG" in line_content:
                log_level = "DEBUG"
            
            log_entries.append({
                "line_number": len(all_lines) - len(recent_lines) + i + 1,
                "level": log_level,
                "content": line_content,
                "timestamp": extract_timestamp(line_content)
            })
        
        return JSONResponse({
            "status": "success",
            "log_file": "docking_service.log",
            "total_lines": len(all_lines),
            "returned_lines": len(recent_lines),
            "last_update": log_path.stat().st_mtime,
            "entries": log_entries
        })
    
    except Exception as e:
        return JSONResponse({
            "status": "error",
            "message": f"Error reading log file: {str(e)}",
            "entries": []
        })

def extract_timestamp(line: str) -> Optional[str]:
    """从日志行中提取时间戳"""
    try:
        # 尝试匹配格式：2025-09-03 16:55:03
        import re
        timestamp_pattern = r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})'
        match = re.search(timestamp_pattern, line)
        if match:
            return match.group(1)
    except Exception:
        pass
    return None
