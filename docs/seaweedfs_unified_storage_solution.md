# SeaweedFS 统一存储方案

## 一、当前架构问题

### 1.1 现状

| 组件 | 当前行为 | 问题 |
|------|----------|------|
| **AstraMolecula (API)** | `job_dir` 存储本地临时路径 `/tmp/astramolecula/jobs/docking/{job_id}` | 路径在计算节点清理后失效 |
| **dockingvina (计算)** | 结果上传到 SeaweedFS 后清理临时目录 | ✅ 正确 |
| **tasks.py 端点** | 直接读取 `Path(task.job_dir) / "output" / ...` | ❌ 本地文件已不存在 |

### 1.2 问题根源

**错误现象**：
```
Request URL: http://localhost:8000/tasks/{task_id}/dockRes
Status Code: 500
Error: "dockRes not found"
```

**代码分析**：

在 `routers/tasks.py` 第 817-819 行：
```python
output_path = Path(task.job_dir) / "output" / "dockRes.json"
if not output_path.exists():
    raise HTTPException(status_code=500, detail="dockRes not found")
```

**失败原因**：
1. **AstraMolecula** 创建任务时，`job_dir` 存储的是本地临时路径：`/tmp/astramolecula/jobs/docking/{job_id}`
2. **dockingvina** 处理任务后：
   - 将结果上传到 **SeaweedFS**：`jobs/docking/{job_id}/output/dockRes.json`
   - 然后**清理临时目录**（`docking_task_processor.py` 第 158-162 行）
3. 当用户请求结果时，本地临时目录已不存在，导致 `output_path.exists()` 返回 `False`

### 1.3 当前数据流

```
┌─────────────────┐    创建任务     ┌──────────────────┐
│  AstraMolecula  │ ─────────────► │   数据库 tasks   │
│   (API 服务)    │                │  job_dir=本地路径 │
└─────────────────┘                └──────────────────┘
         │                                   │
         │ 上传 input.json                   │ 读取任务
         ▼                                   ▼
┌─────────────────┐                ┌──────────────────┐
│    SeaweedFS    │ ◄───────────── │    dockingvina   │
│   对象存储       │   上传结果     │   (计算服务)     │
└─────────────────┘                └──────────────────┘
         │                                   │
         │ ❌ API 未从此读取                  │ 清理临时目录
         ▼                                   ▼
┌─────────────────┐                ┌──────────────────┐
│  前端请求结果    │ ───────────► │  500 错误         │
└─────────────────┘                └──────────────────┘
```

---

## 二、统一方案设计

### 2.1 核心改动原则

1. **数据库 `job_dir` 字段**：存储 SeaweedFS 路径前缀（如 `jobs/docking/{job_id}`），而非本地路径
2. **所有文件读取**：统一通过 SeaweedFS API 获取，不再检查本地文件系统
3. **临时文件**：仅在需要处理时下载到内存或临时目录，处理完立即释放
4. **去除兼容逻辑**：不保留本地文件检查，完全依赖 SeaweedFS

### 2.2 新数据流

```
┌─────────────────┐    创建任务     ┌───────────────────────────┐
│  AstraMolecula  │ ─────────────► │      数据库 tasks         │
│   (API 服务)    │                │  job_dir=jobs/docking/xxx │
└─────────────────┘                └───────────────────────────┘
         │                                      │
         │ 上传 input.json                      │
         ▼                                      │
┌─────────────────┐                             │
│    SeaweedFS    │ ◄───────────────────────────┤
│   对象存储       │   dockingvina 上传结果      │
└─────────────────┘                             │
         │                                      │
         │ ✅ API 直接从此读取                   │
         ▼                                      │
┌─────────────────┐                ┌────────────┴───────────────┐
│  前端请求结果    │ ───────────► │  从 SeaweedFS 流式返回      │
└─────────────────┘                └────────────────────────────┘
```

---

## 三、详细修改步骤

### 步骤 1：修改任务创建逻辑

**文件**: `routers/docking.py`

**改动内容**:
- 创建任务时，`job_dir` 存储 SeaweedFS 路径前缀：`jobs/docking/{job_id}`
- 不再将本地临时路径存入数据库
- 本地临时目录仅用于准备 input.json 并上传，之后可立即清理

**处理流程**:
1. 生成 `job_id = uuid4()`
2. 构建 `storage_prefix = f"jobs/docking/{job_id}"`
3. 创建本地临时目录准备输入文件
4. 下载受体文件到本地临时目录
5. 构建 `input.json` 内容
6. 上传 `input.json` 到 SeaweedFS：`{storage_prefix}/input/input.json`
7. **关键修改**：创建任务时使用 `job_dir = storage_prefix` （而不是本地路径）
8. 可选：清理本地临时 input 目录（或保留给计算节点使用）

**当前代码位置**: 第 175 行
```python
# 修改前
task_id = TaskService.create_task(
    user_id=current_user.id,
    task_type="docking",
    job_dir=str(local_job_dir)  # ❌ 本地路径
)

# 修改后
task_id = TaskService.create_task(
    user_id=current_user.id,
    task_type="docking",
    job_dir=job_prefix  # ✅ SeaweedFS 路径前缀
)
```

---

### 步骤 2：修改 dockingvina 任务处理逻辑

**文件**: `dockingvina/docking_task_processor.py`

**改动内容**:
- 从数据库读取的 `job_dir` 现在是 SeaweedFS 路径前缀
- 无需再从本地路径提取 job_id
- 保持现有的下载→处理→上传→清理流程

**处理流程**:
1. 获取任务的 `job_dir`（现在是 `jobs/docking/{job_id}`）
2. 直接使用 `job_dir` 作为 storage_prefix
3. 从 SeaweedFS 下载 `{job_dir}/input/input.json`
4. 从 SeaweedFS 下载受体文件
5. 在本地临时目录执行计算
6. 处理完成后上传结果到 `{job_dir}/output/`
7. 清理本地临时目录

**当前代码位置**: 第 47-50 行
```python
# 修改前
# 从 job_dir 中提取 job_id（AstraMolecula 使用独立的 job_id 存储文件）
# job_dir 格式: /tmp/astramolecula/jobs/docking/{job_id}
job_id = Path(job_dir).name
logger.info(f"从 job_dir 提取 job_id: {job_id}")

# 修改后
# job_dir 现在直接是 SeaweedFS 路径前缀
storage_prefix = job_dir  # jobs/docking/{job_id}
job_id = Path(job_dir).name  # 提取 job_id 用于日志
logger.info(f"处理任务，存储前缀: {storage_prefix}")
```

**配置文件下载位置**: 第 66-72 行
```python
# 修改前
remote_config_key = f"jobs/docking/{job_id}/input/input.json"

# 修改后
remote_config_key = f"{storage_prefix}/input/input.json"
```

**结果上传位置**: 第 132-136 行
```python
# 修改前
remote_key = f"jobs/docking/{job_id}/output/{relative_path}"

# 修改后
remote_key = f"{storage_prefix}/output/{relative_path}"
```

---

### 步骤 3：修改结果获取端点

**文件**: `routers/tasks.py`

#### 3.1 涉及端点列表

| 端点 | 当前问题 | 修改方案 |
|------|----------|----------|
| `GET /{task_id}/dockRes` | 直接读取本地文件 | 从 SeaweedFS 下载 JSON 内容并返回 |
| `GET /{task_id}/output` | 直接读取本地文件 | 从 SeaweedFS 读取 JSON |
| `GET /{task_id}/sdf/{filename}` | 直接读取本地文件 | 从 SeaweedFS 获取预签名 URL 或流式返回 |
| `GET /{task_id}/pdbqt/{filename}` | 直接读取本地文件 | 从 SeaweedFS 获取预签名 URL 或流式返回 |
| `GET /{task_id}/download` | 构建本地路径打包 | 从 SeaweedFS 列出文件并打包下载 |
| `GET /{task_id}/csv` | 读取本地 JSON 生成 CSV | 从 SeaweedFS 读取 JSON 后生成 |
| `GET /{task_id}/binding-analysis` | 读取本地文件 | 从 SeaweedFS 获取并打包 |

#### 3.2 通用处理模式

**模式 A：返回 JSON 数据（小文件）**
```
1. 获取 task.job_dir (SeaweedFS 前缀)
2. 构建 remote_key = f"{task.job_dir}/output/xxx.json"
3. 使用 storage.download_bytes() 下载到内存
4. json.loads() 解析
5. 返回 JSON 响应
```

**模式 B：单文件下载（预签名 URL - 统一方案）**
```
1. 获取 task.job_dir
2. 构建 remote_key = f"{task.job_dir}/output/{filename}"
3. 使用 storage.get_presigned_url() 获取临时 URL（有效期 1-24 小时）
4. 返回 RedirectResponse(url)
```

**模式 C：多文件打包（生成缓存 + 预签名 URL）**
```
1. 检查缓存：查看 {task.job_dir}/cache/{archive_name}.zip 是否存在
2. 如果不存在：
   a. 使用 storage.list_files() 列出所有文件
   b. 逐个下载并打包成 ZIP（在内存或临时目录）
   c. 上传 ZIP 到 SeaweedFS 缓存路径
3. 生成 ZIP 文件的预签名 URL
4. 返回 RedirectResponse(url)
```

**模式 D：动态生成文件（CSV 等）+ 缓存**
```
1. 检查缓存：查看生成的文件是否已存在
2. 如果不存在：
   a. 从 SeaweedFS 读取源数据（如 dockRes.json）
   b. 生成目标文件（如 CSV）
   c. 上传到 SeaweedFS 缓存路径
3. 生成预签名 URL
4. 返回 RedirectResponse(url)
```

#### 3.3 具体端点修改

##### 端点 1: `GET /{task_id}/dockRes` (第 782 行)

**当前代码**:
```python
output_path = Path(task.job_dir) / "output" / "dockRes.json"
if not output_path.exists():
    raise HTTPException(status_code=500, detail="dockRes not found")
data = json.loads(output_path.read_text(encoding="utf-8"))
```

**修改方案**:
```python
storage = get_storage()
remote_key = f"{task.job_dir}/output/dockRes.json"

if not await storage.file_exists(remote_key):
    raise HTTPException(status_code=500, detail="dockRes not found")

# 下载到内存并解析
content = await storage.download_bytes(remote_key)
data = json.loads(content.decode('utf-8'))
```

##### 端点 2: `GET /{task_id}/sdf/{filename}` (第 842 行)

**当前代码**:
```python
sdf_path = Path(task.job_dir) / "output" / "docked" / filename
if not sdf_path.exists():
    raise HTTPException(status_code=404, detail="SDF file not found")
return FileResponse(sdf_path, ...)
```

**修改方案（预签名 URL）**:
```python
storage = get_storage()
remote_key = f"{task.job_dir}/output/docked/{filename}"

if not await storage.file_exists(remote_key):
    raise HTTPException(status_code=404, detail="SDF file not found")

# 生成临时访问 URL 并重定向（有效期 1 小时）
url = await storage.get_presigned_url(remote_key, expires_in=3600)
return RedirectResponse(url)
```

##### 端点 3: `GET /{task_id}/pdbqt/{filename}` (第 882 行)

**修改方案（预签名 URL）**:
```python
storage = get_storage()
remote_key = f"{task.job_dir}/output/docked/{filename}"

if not await storage.file_exists(remote_key):
    raise HTTPException(status_code=404, detail="PDBQT file not found")

# 生成临时访问 URL 并重定向
url = await storage.get_presigned_url(remote_key, expires_in=3600)
return RedirectResponse(url)
```

##### 端点 4: `GET /{task_id}/download` (第 920 行)

**当前代码**:
```python
output_dir = Path(task.job_dir) / "output"
if not output_dir.exists():
    raise HTTPException(...)
# 打包 output_dir 中的所有文件
```

**修改方案（生成缓存 + 预签名 URL）**:
```python
storage = get_storage()
output_prefix = f"{task.job_dir}/output/"
cache_key = f"{task.job_dir}/cache/results.zip"

# 检查缓存的 ZIP 是否存在
if not await storage.file_exists(cache_key):
    # 列出所有输出文件
    files = await storage.list_files(output_prefix)
    if not files:
        raise HTTPException(status_code=404, detail="No output files found")
    
    # 创建内存 ZIP
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for file_key in files:
            # 获取相对路径（去掉 output_prefix）
            relative_path = file_key.replace(output_prefix, '')
            
            # 下载文件内容
            content = await storage.download_bytes(file_key)
            
            # 添加到 ZIP
            zip_file.writestr(relative_path, content)
    
    # 上传 ZIP 到缓存路径
    zip_buffer.seek(0)
    await storage.upload_bytes(zip_buffer.getvalue(), cache_key)
    logger.info(f"Generated and cached ZIP for task {task_id}")

# 生成预签名 URL（有效期 24 小时）
url = await storage.get_presigned_url(cache_key, expires_in=86400)
return RedirectResponse(url)
```

##### 端点 5: `GET /{task_id}/csv` (第 1327 行)

**当前代码**:
```python
dockres_path = Path(task.job_dir) / "output" / "dockRes.json"
if not dockres_path.exists():
    return JSONResponse(...)
docking_results = json.loads(dockres_path.read_text(encoding="utf-8"))
# 生成 CSV 并返回
```

**修改方案（生成缓存 + 预签名 URL）**:
```python
storage = get_storage()
cache_key = f"{task.job_dir}/cache/results.csv"

# 检查缓存的 CSV 是否存在
if not await storage.file_exists(cache_key):
    # 读取 dockRes.json
    json_key = f"{task.job_dir}/output/dockRes.json"
    if not await storage.file_exists(json_key):
        raise HTTPException(status_code=404, detail="Results not found")
    
    content = await storage.download_bytes(json_key)
    docking_results = json.loads(content.decode('utf-8'))
    
    # 生成 CSV
    csv_buffer = io.StringIO()
    writer = csv.DictWriter(csv_buffer, fieldnames=['title', 'smiles', 'score', 'file'])
    writer.writeheader()
    writer.writerows(docking_results)
    
    # 上传 CSV 到缓存路径
    csv_content = csv_buffer.getvalue().encode('utf-8')
    await storage.upload_bytes(csv_content, cache_key)
    logger.info(f"Generated and cached CSV for task {task_id}")

# 生成预签名 URL（有效期 24 小时）
url = await storage.get_presigned_url(cache_key, expires_in=86400)
return RedirectResponse(url)
```

##### 端点 6: `GET /{task_id}/binding-analysis` (第 1384 行)

**当前代码**:
```python
analysis_dir = Path(task.job_dir) / "output" / "binding_analysis"
if not analysis_dir.exists():
    raise HTTPException(...)
# 打包 CSV 文件
```

**修改方案（生成缓存 + 预签名 URL）**:
```python
storage = get_storage()
analysis_prefix = f"{task.job_dir}/output/binding_analysis/"
cache_key = f"{task.job_dir}/cache/binding_analysis.zip"

# 检查缓存的 ZIP 是否存在
if not await storage.file_exists(cache_key):
    # 列出所有 CSV 文件
    files = await storage.list_files(analysis_prefix)
    csv_files = [f for f in files if f.endswith('.csv')]
    
    if not csv_files:
        raise HTTPException(status_code=404, detail="No binding analysis files found")
    
    # 打包成 ZIP
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for file_key in csv_files:
            relative_path = file_key.replace(analysis_prefix, '')
            content = await storage.download_bytes(file_key)
            zip_file.writestr(relative_path, content)
    
    # 上传 ZIP 到缓存路径
    zip_buffer.seek(0)
    await storage.upload_bytes(zip_buffer.getvalue(), cache_key)
    logger.info(f"Generated and cached binding analysis ZIP for task {task_id}")

# 生成预签名 URL（有效期 24 小时）
url = await storage.get_presigned_url(cache_key, expires_in=86400)
return RedirectResponse(url)
```

---

### 步骤 4：删除或重构辅助函数

**文件**: `routers/tasks.py`

#### 4.1 移除本地文件检查

**当前函数**: `get_file_from_storage_or_local` (第 27-68 行)

**改动**:
- 删除本地文件检查逻辑 (`if local_path.exists()`)
- 简化为纯 SeaweedFS 读取函数

**重构后函数**:
```python
async def get_file_from_storage(storage_prefix: str, relative_path: str) -> bytes:
    """
    从 SeaweedFS 获取文件内容
    
    Args:
        storage_prefix: SeaweedFS 路径前缀 (如 jobs/docking/{job_id})
        relative_path: 相对路径 (如 output/dockRes.json)
    
    Returns:
        文件字节内容
    
    Raises:
        HTTPException: 文件不存在时抛出 404
    """
    storage = get_storage()
    remote_key = f"{storage_prefix}/{relative_path}".replace('//', '/')
    
    if not await storage.file_exists(remote_key):
        raise HTTPException(status_code=404, detail=f"File not found: {relative_path}")
    
    return await storage.download_bytes(remote_key)
```

#### 4.2 添加新的辅助函数

**函数 1：读取 JSON 文件**
```python
async def read_json_from_storage(storage_prefix: str, relative_path: str) -> dict | list:
    """从 SeaweedFS 读取并解析 JSON 文件"""
    content = await get_file_from_storage(storage_prefix, relative_path)
    return json.loads(content.decode('utf-8'))
```

**函数 2：获取文件预签名 URL（核心函数）**
```python
async def get_file_presigned_url(
    storage_prefix: str, 
    relative_path: str, 
    expires_in: int = 3600
) -> str:
    """获取文件的临时访问 URL"""
    storage = get_storage()
    remote_key = f"{storage_prefix}/{relative_path}".replace('//', '/')
    
    if not await storage.file_exists(remote_key):
        raise HTTPException(status_code=404, detail=f"File not found: {relative_path}")
    
    return await storage.get_presigned_url(remote_key, expires_in=expires_in)
```

**函数 3：生成并缓存 ZIP 文件**
```python
async def generate_and_cache_zip(
    storage_prefix: str,
    source_prefix: str,
    cache_name: str,
    file_filter: callable = None
) -> str:
    """
    生成 ZIP 文件并缓存到 SeaweedFS，返回缓存的 remote_key
    
    Args:
        storage_prefix: 任务的存储前缀 (如 jobs/docking/{job_id})
        source_prefix: 源文件路径前缀 (如 output/或 output/binding_analysis/)
        cache_name: 缓存文件名 (如 results.zip)
        file_filter: 可选的文件过滤函数
    
    Returns:
        缓存文件的 remote_key
    """
    storage = get_storage()
    cache_key = f"{storage_prefix}/cache/{cache_name}"
    
    # 如果缓存已存在，直接返回
    if await storage.file_exists(cache_key):
        return cache_key
    
    # 列出源文件
    file_prefix = f"{storage_prefix}/{source_prefix}"
    files = await storage.list_files(file_prefix)
    
    # 应用过滤器
    if file_filter:
        files = [f for f in files if file_filter(f)]
    
    if not files:
        raise HTTPException(status_code=404, detail="No files found to archive")
    
    # 创建 ZIP
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for file_key in files:
            relative_path = file_key.replace(file_prefix, '')
            content = await storage.download_bytes(file_key)
            zip_file.writestr(relative_path, content)
    
    # 上传到缓存
    zip_buffer.seek(0)
    await storage.upload_bytes(zip_buffer.getvalue(), cache_key)
    
    return cache_key
```

**函数 4：生成并缓存 CSV 文件**
```python
async def generate_and_cache_csv(
    storage_prefix: str,
    json_relative_path: str,
    cache_name: str,
    csv_generator: callable
) -> str:
    """
    从 JSON 生成 CSV 并缓存到 SeaweedFS
    
    Args:
        storage_prefix: 任务的存储前缀
        json_relative_path: JSON 文件相对路径
        cache_name: 缓存文件名 (如 results.csv)
        csv_generator: CSV 生成函数，接收 JSON 数据，返回 CSV 字符串
    
    Returns:
        缓存文件的 remote_key
    """
    storage = get_storage()
    cache_key = f"{storage_prefix}/cache/{cache_name}"
    
    # 如果缓存已存在，直接返回
    if await storage.file_exists(cache_key):
        return cache_key
    
    # 读取 JSON 数据
    json_data = await read_json_from_storage(storage_prefix, json_relative_path)
    
    # 生成 CSV
    csv_content = csv_generator(json_data)
    
    # 上传到缓存
    await storage.upload_bytes(csv_content.encode('utf-8'), cache_key)
    
    return cache_key
```

---

### 步骤 5：处理公开分享链接

**文件**: `routers/public.py`

**改动内容**:
- 公开访问的 3D 查看器端点也需要从 SeaweedFS 获取文件
- 确保预签名 URL 的有效期配置合理（建议 1-24 小时）
- 对于公开端点，考虑添加访问频率限制

**处理流程**:
1. 解析公开访问链接参数（taskId, filename）
2. **不需要验证用户身份**（公开访问）
3. 从数据库获取任务的 `job_dir`
4. 构建 remote_key
5. 返回预签名 URL 或流式传输文件

---

## 四、数据库迁移

### 4.1 迁移需求

对于已存在的任务记录，`job_dir` 存储的是旧的本地路径格式，需要迁移到 SeaweedFS 格式。

**旧格式示例**:
```
/tmp/astramolecula/jobs/docking/ca082f15-533a-4238-81a4-a4434f574f49
```

**新格式**:
```
jobs/docking/ca082f15-533a-4238-81a4-a4434f574f49
```

### 4.2 迁移脚本逻辑

**迁移脚本位置**: `database/migrations/002_job_dir_to_storage_path.sql` 或 `migrate_job_dir_format.py`

**SQL 方案（适用于 PostgreSQL）**:
```sql
-- 备份原始数据
CREATE TABLE tasks_backup AS 
SELECT * FROM tasks 
WHERE job_dir LIKE '/tmp/%' OR job_dir LIKE '/%';

-- 迁移 docking 任务
-- PostgreSQL 使用 split_part() 提取路径最后一部分
UPDATE tasks 
SET job_dir = 'jobs/' || task_type || '/' || 
              split_part(job_dir, '/', 
                        array_length(string_to_array(job_dir, '/'), 1))
WHERE job_dir LIKE '/tmp/%' 
  AND task_type = 'docking'
  AND status IN ('finished', 'processing');

-- 迁移 generate 任务
UPDATE tasks 
SET job_dir = 'jobs/' || task_type || '/' || 
              split_part(job_dir, '/', 
                        array_length(string_to_array(job_dir, '/'), 1))
WHERE job_dir LIKE '/tmp/%' 
  AND task_type = 'generate'
  AND status IN ('finished', 'processing');

-- 更简洁的方式：使用正则表达式提取最后的 UUID
-- 适用于标准格式的路径 /tmp/astramolecula/jobs/{task_type}/{uuid}
UPDATE tasks
SET job_dir = 'jobs/' || task_type || '/' || 
              (regexp_match(job_dir, '[^/]+$'))[1]
WHERE job_dir ~ '^/.*'
  AND status IN ('finished', 'processing')
  AND task_type IN ('docking', 'generate');

-- 验证迁移结果
SELECT 
    task_type,
    status,
    COUNT(*) as count,
    MIN(job_dir) as sample_old_path,
    MAX(job_dir) as sample_new_path
FROM tasks
GROUP BY task_type, status;
```

**Python 脚本方案**:
```python
# database/migrations/migrate_job_dir_format.py

import re
from pathlib import Path
from database.db import get_db_connection
from database.repositorys.task_repository import TaskRepository

def migrate_job_dir_format():
    """迁移 job_dir 从本地路径到 SeaweedFS 格式"""
    
    with get_db_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        
        # 查询需要迁移的任务
        cursor.execute("""
            SELECT id, task_type, job_dir, status 
            FROM tasks 
            WHERE job_dir LIKE '/tmp/%' OR job_dir LIKE '/%'
        """)
        
        tasks = cursor.fetchall()
        print(f"找到 {len(tasks)} 个需要迁移的任务")
        
        migrated = 0
        for task in tasks:
            task_id = task['id']
            old_job_dir = task['job_dir']
            task_type = task['task_type']
            
            # 提取 job_id（路径最后一部分）
            job_id = Path(old_job_dir).name
            
            # 构建新的 storage 路径
            new_job_dir = f"jobs/{task_type}/{job_id}"
            
            # 更新数据库
            cursor.execute(
                "UPDATE tasks SET job_dir = %s WHERE id = %s",
                (new_job_dir, task_id)
            )
            
            print(f"迁移任务 {task_id}: {old_job_dir} -> {new_job_dir}")
            migrated += 1
        
        conn.commit()
        print(f"成功迁移 {migrated} 个任务")

if __name__ == "__main__":
    migrate_job_dir_format()
```

### 4.3 迁移执行计划

1. **准备阶段**
   - 备份数据库
   - 确认所有历史任务的结果已上传到 SeaweedFS
   - 在测试环境验证迁移脚本

2. **执行迁移**
   - 停止 AstraMolecula 和 dockingvina 服务
   - 运行迁移脚本
   - 验证迁移结果（抽样检查）

3. **部署新代码**
   - 部署修改后的代码
   - 启动服务
   - 监控日志和错误

4. **回滚方案**
   - 如果出现问题，从备份表恢复数据
   - 回退到旧版本代码

### 4.4 兼容期处理（可选，不推荐）

如果不希望一次性迁移所有历史数据，可以在代码中添加格式检测逻辑：

```python
def normalize_job_dir(job_dir: str) -> str:
    """
    规范化 job_dir 格式
    
    将旧的本地路径格式转换为 SeaweedFS 格式
    """
    if job_dir.startswith('/'):
        # 旧格式: /tmp/astramolecula/jobs/docking/{job_id}
        # 提取 task_type 和 job_id
        parts = Path(job_dir).parts
        try:
            jobs_idx = parts.index('jobs')
            return '/'.join(parts[jobs_idx:])  # jobs/docking/{job_id}
        except ValueError:
            # 无法解析，返回原值
            return job_dir
    else:
        # 已经是新格式
        return job_dir
```

**不推荐原因**：增加代码复杂度，且兼容逻辑会长期存在于代码中。

---

## 五、测试计划

### 5.1 单元测试

**测试文件**: `test/test_storage_integration.py`

**测试用例**:
1. **任务创建**：验证 `job_dir` 格式正确
2. **文件上传**：验证 input.json 上传到正确路径
3. **结果读取**：验证能从 SeaweedFS 读取 dockRes.json
4. **文件下载**：验证单文件和批量下载功能
5. **公开分享**：验证公开链接能正确访问文件

### 5.2 集成测试

**测试场景**:
1. **完整对接流程**
   - 提交对接任务 → 任务处理 → 结果查询 → 文件下载
   - 验证所有环节正常

2. **多节点测试**
   - 在不同的计算节点执行任务
   - 验证结果都能正确上传和访问

3. **故障恢复**
   - 模拟计算节点崩溃后重启
   - 验证已上传的结果不受影响

### 5.3 性能测试

**测试指标**:
1. **文件读取延迟**
   - 本地文件 vs SeaweedFS（预期增加 10-50ms）
2. **并发访问**
   - 100 个并发请求读取结果文件
3. **大文件下载**
   - ZIP 打包下载 100+ 个文件的耗时

---

## 六、影响范围总结

### 6.1 代码修改

| 模块 | 文件 | 改动类型 | 优先级 |
|------|------|----------|--------|
| API 路由 | `routers/docking.py` | 任务创建时 job_dir 格式 | 🔴 高 |
| API 路由 | `routers/tasks.py` | 所有文件读取端点（6+ 处） | 🔴 高 |
| API 路由 | `routers/public.py` | 公开分享端点 | 🟡 中 |
| 计算服务 | `docking_task_processor.py` | 路径解析逻辑 | 🔴 高 |
| 数据库 | `tasks` 表 | 现有数据迁移 | 🔴 高 |
| 测试 | `test/` | 新增集成测试 | 🟢 低 |

### 6.2 配置修改

| 配置项 | 位置 | 说明 |
|--------|------|------|
| SeaweedFS 连接 | `config/storage.py` | 确认配置正确 |
| 预签名 URL 有效期 | `config/api_config.py` | 建议 3600 秒（1 小时） |
| 临时目录路径 | `config/storage.py` | 清理策略 |

---

## 七、实施优势

### 7.1 架构优势

| 优势 | 说明 |
|------|------|
| **存储统一** | 所有持久化数据集中在 SeaweedFS，消除本地/远程二元性 |
| **可扩展性** | 支持多计算节点，无需共享文件系统 |
| **容错性** | 计算节点重启不影响结果访问 |
| **简化运维** | 无需管理本地临时目录生命周期 |

### 7.2 性能优势

| 场景 | 优化效果 |
|------|----------|
| **结果访问** | 通过预签名 URL 直接访问，减少 API 服务器压力 |
| **并发下载** | 利用 SeaweedFS 的分布式特性，支持高并发 |
| **存储成本** | 自动去重和压缩，节省存储空间 |

### 7.3 开发优势

| 优势 | 说明 |
|------|------|
| **代码简化** | 移除本地文件检查逻辑，减少分支判断 |
| **测试容易** | 统一的存储接口，便于 Mock 和测试 |
| **错误处理** | 集中的错误处理逻辑（存储不可用、文件不存在等） |

---

## 八、潜在风险与缓解措施

### 8.1 风险清单

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| SeaweedFS 服务不可用 | 所有文件访问失败 | 低 | 部署 SeaweedFS 集群，启用高可用 |
| 网络延迟增加 | API 响应变慢 | 中 | 使用预签名 URL，利用 CDN 加速 |
| 数据迁移失败 | 历史任务无法访问 | 低 | 充分测试迁移脚本，保留数据备份 |
| 存储成本增加 | 运维成本上升 | 中 | 启用生命周期管理，定期清理旧任务 |

### 8.2 回滚计划

如果部署后发现严重问题，可按以下步骤回滚：

1. **停止服务**
2. **恢复数据库备份**（还原 job_dir 字段）
3. **部署旧版本代码**
4. **重启服务**
5. **验证功能**

---

## 九、后续优化建议

### 9.1 短期优化（1-2 周）

1. **CDN 集成**
   - 在 SeaweedFS 前添加 CDN 层
   - 加速静态文件（SDF、PDBQT）访问

2. **缓存机制**
   - 对频繁访问的 JSON 结果添加 Redis 缓存
   - 设置合理的缓存过期时间

3. **预签名 URL 优化**
   - 缓存已生成的预签名 URL
   - 避免重复生成

### 9.2 中期优化（1-2 月）

1. **异步处理**
   - 大文件下载改为后台任务
   - 完成后通过 WebSocket 或轮询通知用户

2. **生命周期管理**
   - 自动清理 N 天前的任务文件
   - 提供用户主动删除接口

3. **监控告警**
   - SeaweedFS 存储空间监控
   - API 响应时���监控
   - 文件访问成功率监控

### 9.3 长期优化（3-6 月）

1. **多区域部署**
   - SeaweedFS 跨区域同步
   - 就近访问优化

2. **智能分层存储**
   - 热数据存储在 SSD
   - 冷数据归档到对象存储

---

## 十、相关文档

### 10.1 现有文档

- [SEAWEEDFS_MIGRATION_COMPLETE.md](./SEAWEEDFS_MIGRATION_COMPLETE.md) - SeaweedFS 迁移完成文档
- [seaweedfs_migration_plan.md](./seaweedfs_migration_plan.md) - 原始迁移计划
- [DATABASE_SETUP.md](./DATABASE_SETUP.md) - 数据库设置文档

### 10.2 API 文档

需要更新以下 API 端点说明：
- `GET /tasks/{task_id}/dockRes` - 更新为"从对象存储获取"
- `GET /tasks/{task_id}/download` - 说明文件来源
- `GET /public/docking-viewer` - 公开访问说明

### 10.3 部署文档

需要更新：
- `cicd/docs/DEPLOYMENT_GUIDE.md` - 添加数据库迁移步骤
- `README.md` - 更新架构图和说明

---

## 十一、实施时间线

### 阶段 1：准备（1-2 天）
- [ ] Review 本文档，确认方案
- [ ] 创建功能分支
- [ ] 准备测试环境
- [ ] 备份生产数据库

### 阶段 2：开发（3-5 天）
- [ ] 修改任务创建逻辑（docking.py）
- [ ] 修改任务处理逻辑（docking_task_processor.py）
- [ ] 修改所有结果获取端点（tasks.py）
- [ ] 重构辅助函数
- [ ] 编写单元测试

### 阶段 3：测试（2-3 天）
- [ ] 单元测试
- [ ] 集成测试
- [ ] 性能测试
- [ ] 用户验收测试

### 阶段 4：迁移（1 天）
- [ ] 在测试环境执行数据迁移
- [ ] 验证迁移结果
- [ ] 准备生产环境迁移脚本

### 阶段 5：部署（1 天）
- [ ] 停服维护通知
- [ ] 执行生产数据库迁移
- [ ] 部署新版本代码
- [ ] 启动服务并监控
- [ ] 验证核心功能

### 阶段 6：监控优化（1 周）
- [ ] 监控日志和错误率
- [ ] 收集性能指标
- [ ] 处理用户反馈
- [ ] 优化瓶颈环节

**预计总时间**: 10-15 个工作日

---

## 附录：常见问题

### Q1: 为什么不保留本地文件检查的兼容逻辑？

**A**: 保留兼容逻辑会带来以下问题：
1. 代码复杂度增加，每个端点都需要处理两种情况
2. 维护成本高，新功能需要同时适配两种模式
3. 错误处理困难（是本地文件损坏还是远程文件缺失？）
4. 性能不确定（无法预测使用哪种路径）

统一到 SeaweedFS 后，代码更简洁、行为更可预测。

### Q2: 如果 SeaweedFS 不可用怎么办？

**A**: 
1. 部署 SeaweedFS 集群（master + volume servers）确保高可用
2. 配置健康检查和自动重启
3. 监控 SeaweedFS 状态，及时告警
4. 在 API 层添加重试机制
5. 考虑降级方案（如返回 503 Service Unavailable）

### Q3: 迁移后旧的本地文件怎么处理？

**A**:
1. 确认所有旧任务的结果已上传到 SeaweedFS
2. 迁移完成并验证后，可以安全删除本地临时目录
3. 建议保留 7-30 天作为缓冲期
4. 定期清理过期的临时文件

### Q4: 预签名 URL 的有效期如何设置？

**A**:
- **结果查看**: 1 小时（3600 秒）- 用户即时查看
- **文件下载**: 24 小时（86400 秒）- 允许分享和离线下载
- **公开分享**: 7 天（604800 秒）- 长期有效的分享链接
- 根据实际使用场景调整

### Q5: 如何处理大文件下载超时？

**A**:
1. 使用预签名 URL 让客户端直接从 SeaweedFS 下载
2. 对于 ZIP 打包，考虑后台任务异步生成
3. 增加超时配置（Nginx、FastAPI）
4. 使用分片上传/下载（如果文件 > 100MB）

---

**文档版本**: 1.0  
**创建日期**: 2026-01-05  
**作者**: GitHub Copilot  
**审核状态**: 待审核
