import time
import uuid
import shutil
from pathlib import Path
from typing import List
from fastapi import FastAPI, HTTPException, Query
import pandas as pd
from fastapi.responses import JSONResponse, StreamingResponse
from rdkit import Chem
from rdkit.Chem import Draw
from io import BytesIO
from PIL import Image
import io
from Vina.vina_workflow import vina_docking_from_list
from database.services.upload_service import UploadService
from requests.basic_request import UserCreateRequest, UserLoginRequest
from database.services.user_service import UserService
from security.auth import TokenResponse, create_access_token, get_current_user
from utils.fragment_processor import fragmentize_molecule
import sys
import json
from utils.tools  import DockingRequest, FragmentResponse, GenerateRequest, MoleculeOutput, run_generate_runner

ROOT = Path(__file__).resolve().parent
VINA_DIR = ROOT / "Vina"
if str(VINA_DIR) not in sys.path:
    sys.path.insert(0, str(VINA_DIR))
app = FastAPI()

from fastapi import UploadFile, File
from fastapi.responses import JSONResponse
from fastapi import Depends, HTTPException

@app.post("/login", response_model=TokenResponse)
async def login_for_token(request: UserLoginRequest):
    """
    登录接口：校验用户名/密码，成功后返回 JWT
    """
    if not UserService.authenticate(request.username, request.password):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    # 载荷中放 sub = username，也可以放 user_id
    access_token = create_access_token(
        data={"sub": request.username}
    )
    return {"access_token": access_token}

@app.post("/users", status_code=201)
async def create_user(request: UserCreateRequest):
    """
    创建一个新用户。
    """
    try:
        # 调用业务层做注册
        UserService.register(
            username=request.username,
            password=request.password,
            phone=request.phone,
            email=request.email
        )
        return {"message": "User created successfully"}
    except Exception as e:
        # 你可以根据不同的异常类型返回不同的 status_code
        raise HTTPException(status_code=500, detail=f"Failed to create user: {e}")

@app.get("/users/me/uploads")
async def list_my_uploads(current_user=Depends(get_current_user)):
    uploads = UploadService.list_by_user(current_user.id)
    return [u.__dict__ for u in uploads]

@app.post("/upload_pdbqt")
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


# ============================================
# 3. 已有的 /smiles2img, /fragmentize, /generate 接口 保持不变
# ============================================
@app.get("/smiles2img")
async def smiles2img(smiles: str = Query(..., description="SMILES string of the molecule")):
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return {"error": "Invalid SMILES string"}

    drawer = Draw.MolDraw2DCairo(200, 200)
    drawer.SetFontSize(1.0)
    drawer.DrawMolecule(mol)
    drawer.FinishDrawing()

    pil_image = Image.open(io.BytesIO(drawer.GetDrawingText()))
    strIO = BytesIO()
    pil_image.save(strIO, "PNG")
    strIO.seek(0)
    return StreamingResponse(strIO, media_type="image/png")

@app.get("/fragmentize", response_model=FragmentResponse)
async def fragmentize(smiles: str = Query(..., description="SMILES string of the molecule")):
    try:
        fragment_df = fragmentize_molecule(smiles)
        fragments = fragment_df.to_dict(orient="records")
        return FragmentResponse(fragments=fragments)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"发生错误: {str(e)}")


@app.post("/generate", response_model=List[MoleculeOutput])
async def generate_molecules(request: GenerateRequest):
    """
    1. 先将请求参数保存到 jobs/<job_id>/input.json
    2. 执行 run_generate_runner 生成结果
    3. 将结果保存到 jobs/<job_id>/output.json
    4. 返回结果给调用者
    """
    # （1）生成一个唯一的 job_id，并创建对应文件夹
    try:
        JOBS_DIR = ROOT / "jobs/generate"
        JOBS_DIR.mkdir(exist_ok=True)

        job_id = uuid.uuid4().hex
        job_dir = JOBS_DIR / job_id
        job_dir.mkdir()

        # （2）将请求体内容保存到 job_dir/input.json
        input_data = request.model_dump()
        with open(job_dir / "input.json", "w", encoding="utf-8") as f_in:
            json.dump(input_data, f_in, indent=2, ensure_ascii=False)

        # （3）启动生成逻辑
        start_time = time.time()
        result = run_generate_runner(
            request.constSmiles,
            request.varSmiles,
            request.mainCls,
            request.minorCls,
            request.deltaValue,
            request.num
        )
        end_time = time.time()

        # （4）将生成结果写入 job_dir/output.json
        with open(job_dir / "output.json", "w", encoding="utf-8") as f_out:
            json.dump(result, f_out, indent=2, ensure_ascii=False)

        # （5）可以记录耗时
        duration = end_time - start_time
        # 你也可以将耗时写入一份 log.txt
        with open(job_dir / "log.txt", "w", encoding="utf-8") as log_f:
            log_f.write(f"Started at: {time.ctime(start_time)}\n")
            log_f.write(f"Finished at: {time.ctime(end_time)}\n")
            log_f.write(f"Duration: {duration:.2f} seconds\n")

        # （6）把结果返回给调用者
        return result

    except Exception as e:
        # 捕获异常并记录详细的错误信息，包括堆栈追踪
        error_message = f"Error occurred: {str(e)}"
        print(error_message)  # 打印到控制台，或者使用 logging 模块记录到日志文件
        raise HTTPException(status_code=500, detail=f"Error occurred: {str(e)}")


# ============================================
# 4. 新增 /docking 接口：接受 Ligand 列表 以及 min_ph, max_ph, n_jobs
# ============================================
# ────────────────────────────────────────────────────────────────────
#  修改后的 /docking 接口：直接传递 ligands 列表，不再手动写临时 CSV
# ────────────────────────────────────────────────────────────────────
@app.post("/docking")
async def docking_endpoint(request: DockingRequest):
    """
    1. 创建 jobs/docking/<job_id>
    2. 调用 vina_docking_from_list → 在 resource 下生成临时 run_dir
    3. 将 run_dir 下所有内容“整体”移动到 jobs/docking/<job_id> 下
    4. 从 jobs/docking/<job_id>/dockRes.csv 读取结果、返回
    """
    try:
        # 1. 创建 jobs/docking/<job_id> 目录
        JOBS_DOCK_DIR = ROOT / "jobs" / "docking"
        JOBS_DOCK_DIR.mkdir(parents=True, exist_ok=True)

        job_id = uuid.uuid4().hex
        job_dir = JOBS_DOCK_DIR / job_id
        job_dir.mkdir()

        # 2. 调用 vina_docking_from_list，得到临时 run_dir（位于 resource/<uuid2>）
        receptor_path = str(ROOT / "resource" / "protein_7UDP.pdbqt")
        lig_list = [lig.model_dump() for lig in request.ligands]

        run_dir = vina_docking_from_list(
            ligands=lig_list,
            receptor_pdbqt=receptor_path,
            min_ph=request.min_ph,
            max_ph=request.max_ph,
            n_jobs=request.n_jobs
        )
        # run_dir ≈ /home/davis/projects/dockingVina/resource/<uuid2>

        # 3. 把临时 run_dir 下的所有文件/文件夹移动到 job_dir
        #    (比如 run_dir: /.../resource/123abc; job_dir: /.../jobs/docking/789def)
        for item in Path(run_dir).iterdir():
            # 将 resource/<uuid2>/dockRes.csv 等文件 或 子文件夹 移到 jobs/docking/<job_id>/
            shutil.move(str(item), str(job_dir / item.name))
        # 3b. 删除空的 run_dir（原 resource/<uuid2> 文件夹）
        Path(run_dir).rmdir()

        # 4. 读取最终结果
        result_csv = job_dir / "dockRes.csv"
        if not result_csv.exists():
            raise HTTPException(status_code=500, detail="docking 过程中未生成 dockRes.csv")

        df_result = pd.read_csv(result_csv)
        json_result = df_result.to_dict(orient="records")

        return JSONResponse(content={"run_id": job_id, "results": json_result})

    except Exception as e:
        error_message = f"docking 失败: {str(e)}"
        print(error_message)
        raise HTTPException(status_code=500, detail=error_message)