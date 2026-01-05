# SeaweedFS 对象存储迁移方案

## 一、架构概览

### 1.1 当前文件存储架构

| 文件类型 | 存储路径 | 相关模块 |
|---------|---------|---------|
| 用户上传文件 | `ROOT/uploads/{user_id}/` | `routers/uploads.py` |
| Docking 任务输入 | `ROOT/jobs/docking/{job_id}/input/` | `routers/docking.py` |
| Docking 任务输出 | `ROOT/jobs/docking/{job_id}/output/` | `async_task_processor.py` |
| Peptide 优化输入 | `ROOT/jobs/peptide_optimization/{task_id}/input/` | `routers/peptide.py` |
| Peptide 优化输出 | `ROOT/jobs/peptide_optimization/{task_id}/output/` | peptide_opt 服务 |
| Generate 任务输出 | `ROOT/jobs/generate/{job_id}/` | `async_task_processor.py` |

### 1.2 目标架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                       AstraMolecula 服务                              │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐     │
│  │ uploads.py │  │ docking.py │  │ peptide.py │  │  tasks.py  │     │
│  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘     │
│        │               │               │               │            │
│        └───────────────┴───────┬───────┴───────────────┘            │
│                                │                                     │
│                    ┌───────────┴───────────┐                        │
│                    │   Storage Service     │ ← 统一存储层            │
│                    │   (SeaweedStorage)    │                        │
│                    └───────────┬───────────┘                        │
└────────────────────────────────┼────────────────────────────────────┘
                                 │
                                 ▼
         ┌──────────────────────────────────────────────────┐
         │              SeaweedFS 集群 (Docker)              │
         │  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐  │
         │  │ Master │  │ Volume │  │ Filer  │  │   S3   │  │
         │  │ :9333  │  │ :8080  │  │ :8888  │  │ :8333  │  │
         │  └────────┘  └────────┘  └────────┘  └────────┘  │
         └──────────────────────────────────────────────────┘
```

---

## 二、SeaweedFS 服务部署

### 2.1 Docker Compose 配置

当前部署位置: `/home/songyou/projects/local_seaweedfs/docker-compose.yml`

```yaml
services:
  master:
    image: chrislusf/seaweedfs
    ports:
      - "9333:9333"   # Master HTTP
      - "19333:19333" # Master gRPC
    command: "master -ip=master -defaultReplication=000"

  volume:
    image: chrislusf/seaweedfs
    ports:
      - "8080:8080"   # Volume HTTP
      - "18080:18080" # Volume gRPC
    command: "volume -mserver=master:9333 -port=8080"
    depends_on:
      - master

  filer:
    image: chrislusf/seaweedfs
    ports:
      - "8888:8888"   # Filer HTTP
      - "18888:18888" # Filer gRPC
    command: "filer -master=master:9333"
    depends_on:
      - master
      - volume

  s3:
    image: chrislusf/seaweedfs
    ports:
      - "8333:8333"   # S3 Gateway
    command: "s3 -filer=filer:8888 -port=8333"
    depends_on:
      - filer
```

### 2.2 服务端口说明

| 服务 | 端口 | 用途 |
|------|------|------|
| Master | 9333 | 集群管理、文件分配 |
| Volume | 8080 | 实际数据存储 |
| Filer | 8888 | 文件系统抽象（支持目录） |
| S3 | 8333 | S3 兼容 API |

### 2.3 启动/检查命令

```bash
# 启动服务
cd /home/songyou/projects/local_seaweedfs
sudo docker compose up -d

# 检查服务状态
sudo docker compose ps

# 检查集群状态
curl http://localhost:9333/cluster/status
```

---

## 三、SeaweedFS 存储结构设计

### 3.1 Bucket/目录结构

使用 SeaweedFS S3 Gateway（端口 8333）兼容 S3 API：

```
Bucket: astramolecula
├── uploads/                          # 用户上传文件
│   └── {user_id}/
│       └── {filename}
│
├── jobs/                             # 任务相关文件
│   ├── docking/
│   │   └── {job_id}/
│   │       ├── input/
│   │       │   └── input.json
│   │       └── output/
│   │           ├── dockRes.json
│   │           ├── result.csv
│   │           └── *.pdbqt
│   │
│   ├── peptide_optimization/
│   │   └── {task_id}/
│   │       ├── input/
│   │       │   ├── 5ffg.pdb
│   │       │   └── peptide.fasta
│   │       └── output/
│   │           ├── result.json
│   │           └── *.pdb
│   │
│   └── generate/
│       └── {job_id}/
│           └── output.json
│
└── temp/                             # 临时文件（定期清理）
    └── {session_id}/
```

---

## 四、新增模块设计

### 4.1 目录结构

```
services/
└── storage/
    ├── __init__.py              # 导出 get_storage()
    ├── seaweed_storage.py       # SeaweedFS S3 实现
    └── config.py                # 存储配置
```

### 4.2 SeaweedStorage 实现

```python
# services/storage/seaweed_storage.py
import boto3
from botocore.config import Config
from pathlib import Path
from typing import List, AsyncIterator

class SeaweedStorage:
    """SeaweedFS S3 兼容存储实现"""
    
    def __init__(self):
        from .config import StorageConfig
        
        self.endpoint_url = StorageConfig.SEAWEED_S3_ENDPOINT
        self.bucket = StorageConfig.SEAWEED_BUCKET
        
        self.client = boto3.client(
            's3',
            endpoint_url=self.endpoint_url,
            aws_access_key_id=StorageConfig.SEAWEED_ACCESS_KEY or 'any',
            aws_secret_access_key=StorageConfig.SEAWEED_SECRET_KEY or 'any',
            config=Config(signature_version='s3v4')
        )
        
        # 确保 bucket 存在
        self._ensure_bucket_exists()
    
    def _ensure_bucket_exists(self):
        """确保 bucket 存在"""
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except:
            self.client.create_bucket(Bucket=self.bucket)
    
    async def upload_file(self, local_path: Path, remote_key: str) -> str:
        """上传本地文件"""
        self.client.upload_file(str(local_path), self.bucket, remote_key)
        return remote_key
    
    async def upload_bytes(self, data: bytes, remote_key: str, content_type: str = None) -> str:
        """上传字节数据"""
        extra_args = {}
        if content_type:
            extra_args['ContentType'] = content_type
        self.client.put_object(
            Bucket=self.bucket,
            Key=remote_key,
            Body=data,
            **extra_args
        )
        return remote_key
    
    async def download_file(self, remote_key: str, local_path: Path) -> Path:
        """下载文件到本地"""
        local_path.parent.mkdir(parents=True, exist_ok=True)
        self.client.download_file(self.bucket, remote_key, str(local_path))
        return local_path
    
    async def get_presigned_url(self, remote_key: str, expires: int = 3600) -> str:
        """生成预签名下载 URL"""
        return self.client.generate_presigned_url(
            'get_object',
            Params={'Bucket': self.bucket, 'Key': remote_key},
            ExpiresIn=expires
        )
    
    async def delete_file(self, remote_key: str) -> bool:
        """删除文件"""
        self.client.delete_object(Bucket=self.bucket, Key=remote_key)
        return True
    
    async def list_files(self, prefix: str) -> List[str]:
        """列出指定前缀的文件"""
        response = self.client.list_objects_v2(Bucket=self.bucket, Prefix=prefix)
        return [obj['Key'] for obj in response.get('Contents', [])]
    
    async def file_exists(self, remote_key: str) -> bool:
        """检查文件是否存在"""
        try:
            self.client.head_object(Bucket=self.bucket, Key=remote_key)
            return True
        except:
            return False
    
    async def copy_file(self, src_key: str, dest_key: str) -> str:
        """复制文件"""
        self.client.copy_object(
            Bucket=self.bucket,
            CopySource={'Bucket': self.bucket, 'Key': src_key},
            Key=dest_key
        )
        return dest_key
    
    async def get_file_stream(self, remote_key: str) -> AsyncIterator[bytes]:
        """获取文件流（用于流式下载）"""
        response = self.client.get_object(Bucket=self.bucket, Key=remote_key)
        for chunk in response['Body'].iter_chunks(chunk_size=8192):
            yield chunk
```

### 4.4 工厂函数

```python
# services/storage/__init__.py
from .seaweed_storage import SeaweedStorage
from .config import StorageConfig

_storage_instance = None

def get_storage() -> SeaweedStorage:
    """获取 SeaweedFS 存储实例（单例）"""
    global _storage_instance
    
    if _storage_instance is None:
        _storage_instance = SeaweedStorage()
    
    return _storage_instance

__all__ = ['get_storage', 'SeaweedStorage', 'StorageConfig']
```

---

## 五、配置设计

### 5.1 配置文件

```python
# config/storage_config.py
import os
from pathlib import Path

class StorageConfig:
    """SeaweedFS 存储配置"""
    
    # SeaweedFS 配置
    SEAWEED_S3_ENDPOINT = os.getenv("SEAWEED_S3_ENDPOINT", "http://localhost:8333")
    SEAWEED_FILER_ENDPOINT = os.getenv("SEAWEED_FILER_ENDPOINT", "http://localhost:8888")
    SEAWEED_BUCKET = os.getenv("SEAWEED_BUCKET", "astramolecula")
    SEAWEED_ACCESS_KEY = os.getenv("SEAWEED_ACCESS_KEY", "")
    SEAWEED_SECRET_KEY = os.getenv("SEAWEED_SECRET_KEY", "")
    
    # 临时文件目录（用于计算任务的本地缓存）
    TEMP_DIR = Path(os.getenv("TEMP_DIR", "/tmp/astramolecula"))
    
    # 预签名 URL 过期时间（秒）
    PRESIGNED_URL_EXPIRES = int(os.getenv("PRESIGNED_URL_EXPIRES", "3600"))
```

### 5.2 环境变量示例

```bash
# .env
SEAWEED_S3_ENDPOINT=http://localhost:8333
SEAWEED_FILER_ENDPOINT=http://localhost:8888
SEAWEED_BUCKET=astramolecula
SEAWEED_ACCESS_KEY=
SEAWEED_SECRET_KEY=
TEMP_DIR=/tmp/astramolecula
```

---

## 六、模块修改计划

### 6.1 需要修改的文件

| 文件 | 修改内容 | 优先级 |
|------|---------|--------|
| `routers/uploads.py` | 文件保存改为调用 StorageBackend | 高 |
| `routers/docking.py` | 受体文件获取、input.json 保存 | 高 |
| `routers/peptide.py` | PDB/FASTA 文件操作 | 高 |
| `routers/tasks.py` | 文件下载改为预签名 URL 或流式传输 | 高 |
| `async_task_processor.py` | 输入文件下载、结果上传 | 中 |
| `database/models/upload.py` | 增加 storage_type、storage_key 字段 | 中 |
| `database/models/task.py` | 增加 storage_prefix 字段 | 中 |

### 6.2 修改示例

#### uploads.py 修改

**Before:**
```python
dest = UPLOAD_DIR / f.filename
with open(dest, "wb") as fh:
    content = await f.read()
    fh.write(content)
```

**After:**
```python
from services.storage import get_storage

storage = get_storage()
content = await f.read()
remote_key = f"uploads/{user_id}/{f.filename}"
await storage.upload_bytes(content, remote_key)
```

#### docking.py 修改

**Before:**
```python
receptor_path = Path(match.file_path)
if not receptor_path.exists():
    raise HTTPException(...)
```

**After:**
```python
from services.storage import get_storage

storage = get_storage()
remote_key = f"uploads/{current_user.id}/{receptor_filename}"
if not await storage.file_exists(remote_key):
    raise HTTPException(...)

# 下载到临时目录供计算使用
temp_path = StorageConfig.TEMP_DIR / job_id / receptor_filename
await storage.download_file(remote_key, temp_path)
receptor_path = str(temp_path)
```

#### tasks.py 下载修改

**Before:**
```python
return FileResponse(file_path, filename=filename)
```

**After:**
```python
from services.storage import get_storage

storage = get_storage()
# 方案1: 预签名 URL 重定向（推荐大文件）
url = await storage.get_presigned_url(remote_key)
return RedirectResponse(url)

# 方案2: 流式传输（小文件）
stream = await storage.get_file_stream(remote_key)
return StreamingResponse(stream, media_type="application/octet-stream")
```

---

## 七、Peptide 服务协同方案

由于 `peptide_opt` 是独立服务，推荐采用**混合模式**：

```
┌──────────────────────────────────────────────────────────────────┐
│                          工作流程                                 │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. 任务创建 (AstraMolecula)                                      │
│     ├─ 从 SeaweedFS 下载 receptor.pdb                            │
│     ├─ 创建 peptide.fasta                                        │
│     └─ 保存到本地共享目录: /data/shared/peptide/{task_id}/input/  │
│                                                                  │
│  2. 任务执行 (peptide_opt)                                        │
│     ├─ 从本地共享目录读取输入                                      │
│     └─ 将结果写入: /data/shared/peptide/{task_id}/output/        │
│                                                                  │
│  3. 结果同步 (AstraMolecula - 定时任务)                            │
│     ├─ 检查任务完成状态                                           │
│     ├─ 将 output/ 目录上传到 SeaweedFS                           │
│     └─ 清理本地临时文件                                           │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## 八、数据库扩展

### 8.1 user_uploads 表

```sql
ALTER TABLE user_uploads 
ADD COLUMN storage_key VARCHAR(512) DEFAULT NULL,
ADD COLUMN file_size BIGINT DEFAULT NULL,
ADD COLUMN content_type VARCHAR(128) DEFAULT NULL;
```

### 8.2 tasks 表

```sql
ALTER TABLE tasks 
ADD COLUMN storage_prefix VARCHAR(512) DEFAULT NULL;
```

---

## 九、实施路线图

| 阶段 | 任务 | 工时 | 状态 |
|------|------|------|------|
| **阶段 1** | **基础设施** | **1 天** | |
| | • 创建 SeaweedFS Bucket | | ⬜ |
| | • 实现 SeaweedStorage 类 | | ✅ |
| | • 添加存储配置模块 | | ✅ |
| **阶段 2** | **数据库扩展** | **0.5 天** | |
| | • 编写迁移脚本 | | ✅ |
| | • 更新 ORM 模型 | | ✅ |
| **阶段 3** | **上传模块迁移** | **1 天** | |
| | • 修改 uploads.py | | ✅ |
| | • 单元测试 | | ⬜ |
| **阶段 4** | **任务创建迁移** | **1-2 天** | |
| | • 修改 docking.py | | ✅ |
| | • 修改 peptide.py | | ✅ |
| | • 集成测试 | | ⬜ |
| **阶段 5** | **下载接口迁移** | **1 天** | |
| | • 修改 tasks.py | | ✅ |
| | • 实现预签名 URL | | ✅ |
| **阶段 6** | **历史数据迁移** | **1-2 天** | |
| | • 编写迁移脚本 | | ✅ |
| | • 分批迁移验证 | | ⬜ |
| **总计** | | **4-6 天** | |

---

## 十、SeaweedFS vs 其他方案对比

| 对比项 | SeaweedFS | 阿里云 OSS | MinIO |
|--------|-----------|-----------|-------|
| 部署方式 | Docker 自建 | 云托管 | Docker 自建 |
| 成本 | 服务器成本 | 按量付费 | 服务器成本 |
| 延迟 | 本地极低 | 取决于网络 | 本地极低 |
| S3 兼容 | ✅ | ✅ | ✅ |
| 数据主权 | 完全自主 | 依赖云商 | 完全自主 |
| 扩展性 | 动态扩容 | 无限 | 动态扩容 |
| 运维成本 | 需维护 | 托管 | 需维护 |
| 适用场景 | 私有化部署 | 生产环境 | 开发测试 |

---

## 十一、依赖包

```txt
# requirements.txt 新增
boto3>=1.26.0
botocore>=1.29.0
```

---

## 十二、测试检查清单

- [ ] SeaweedFS 服务正常运行
- [ ] Bucket 创建成功
- [ ] 文件上传测试通过
- [ ] 文件下载测试通过
- [ ] 预签名 URL 测试通过
- [ ] 文件列表测试通过
- [ ] 文件删除测试通过
- [ ] 文件复制测试通过
- [ ] 完整任务流程测试通过

---

## 附录：快速验证命令

```bash
# 创建 bucket
aws --endpoint-url http://localhost:8333 s3 mb s3://astramolecula

# 上传文件
aws --endpoint-url http://localhost:8333 s3 cp test.txt s3://astramolecula/uploads/test.txt

# 列出文件
aws --endpoint-url http://localhost:8333 s3 ls s3://astramolecula/

# 下载文件
aws --endpoint-url http://localhost:8333 s3 cp s3://astramolecula/uploads/test.txt ./downloaded.txt

# 使用 curl 直接访问 Filer
curl -F file=@test.txt "http://localhost:8888/uploads/test.txt"
curl "http://localhost:8888/uploads/test.txt"
```
