# 对象存储迁移方案

## 一、现状分析

### 1.1 当前文件存储架构

项目当前使用**本地文件系统**存储所有用户上传的文件和任务执行结果：

| 文件类型 | 存储路径 | 相关代码 |
|---------|---------|---------|
| 用户上传文件 | `ROOT/uploads/{user_id}/` | `routers/uploads.py` |
| Docking任务输入 | `ROOT/jobs/docking/{job_id}/input/` | `routers/docking.py` |
| Docking任务输出 | `ROOT/jobs/docking/{job_id}/output/` | `async_task_processor.py` |
| Peptide优化输入 | `ROOT/jobs/peptide_optimization/{task_id}/input/` | `routers/peptide.py` |
| Peptide优化输出 | `ROOT/jobs/peptide_optimization/{task_id}/output/` | 外部peptide_opt服务 |
| Generate任务输出 | `ROOT/jobs/generate/{job_id}/` | `async_task_processor.py` |

### 1.2 当前存在的问题

1. **单点故障**：文件存储在单机，服务器故障会导致数据丢失
2. **扩展性差**：无法支持多实例部署和水平扩展
3. **存储容量受限**：受单机磁盘容量限制
4. **无冗余备份**：缺乏自动备份和容灾能力
5. **文件访问效率**：大文件下载需要通过应用服务器中转

### 1.3 涉及的核心模块

```
routers/
├── uploads.py          # 文件上传入口
├── docking.py          # Docking任务创建，文件读写
├── peptide.py          # Peptide任务创建，文件复制
├── tasks.py            # 任务结果下载，文件读取

database/
├── models/upload.py    # 上传记录模型
├── repositorys/upload_repository.py  # 上传记录持久化
├── services/upload_service.py        # 上传业务逻辑

utils/
├── file.py             # 文件工具函数

async_task_processor.py # 异步任务处理，文件读写
```

---

## 二、对象存储方案设计

### 2.1 推荐的对象存储服务

| 云服务商 | 对象存储服务 | 推荐场景 |
|---------|------------|---------|
| 阿里云 | OSS | 国内部署首选 |
| AWS | S3 | 海外部署/AWS生态 |
| 腾讯云 | COS | 腾讯云生态 |
| MinIO | 自建 | 私有化部署 |

> 建议使用 **阿里云 OSS**（基于现有阿里云部署环境），或使用兼容 S3 协议的存储服务以保持代码通用性。

### 2.2 对象存储结构设计

```
bucket: astramolecula-storage
├── uploads/                          # 用户上传文件
│   └── {user_id}/
│       └── {filename}
├── jobs/                             # 任务相关文件
│   ├── docking/
│   │   └── {job_id}/
│   │       ├── input/
│   │       │   └── input.json
│   │       └── output/
│   │           ├── dockRes.json
│   │           ├── result.csv
│   │           └── *.pdbqt
│   ├── peptide_optimization/
│   │   └── {task_id}/
│   │       ├── input/
│   │       │   ├── 5ffg.pdb
│   │       │   └── peptide.fasta
│   │       └── output/
│   │           ├── result.json
│   │           └── *.pdb
│   └── generate/
│       └── {job_id}/
│           └── output.json
└── temp/                             # 临时文件（自动清理）
    └── {session_id}/
```

### 2.3 数据库模型扩展

#### 2.3.1 `user_uploads` 表扩展

```sql
ALTER TABLE user_uploads ADD COLUMN storage_type ENUM('local', 'oss') DEFAULT 'local';
ALTER TABLE user_uploads ADD COLUMN oss_key VARCHAR(512) DEFAULT NULL;
ALTER TABLE user_uploads ADD COLUMN oss_bucket VARCHAR(128) DEFAULT NULL;
ALTER TABLE user_uploads ADD COLUMN file_size BIGINT DEFAULT NULL;
ALTER TABLE user_uploads ADD COLUMN content_type VARCHAR(128) DEFAULT NULL;
```

#### 2.3.2 `tasks` 表扩展

```sql
ALTER TABLE tasks ADD COLUMN storage_type ENUM('local', 'oss') DEFAULT 'local';
ALTER TABLE tasks ADD COLUMN oss_prefix VARCHAR(512) DEFAULT NULL;
```

---

## 三、模块修改方案

### 3.1 新增对象存储服务模块

创建 `services/storage/` 目录，统一封装存储操作：

```
services/
└── storage/
    ├── __init__.py
    ├── base.py              # 存储接口抽象基类
    ├── local_storage.py     # 本地文件系统实现
    ├── oss_storage.py       # 阿里云OSS实现
    ├── s3_storage.py        # AWS S3实现（可选）
    └── storage_factory.py   # 存储服务工厂
```

**核心接口设计：**

| 方法 | 说明 |
|------|------|
| `upload_file(local_path, remote_key)` | 上传文件 |
| `download_file(remote_key, local_path)` | 下载文件到本地 |
| `get_file_stream(remote_key)` | 获取文件流（用于直接返回响应） |
| `get_presigned_url(remote_key, expires)` | 生成预签名URL |
| `delete_file(remote_key)` | 删除文件 |
| `list_files(prefix)` | 列出指定前缀的文件 |
| `file_exists(remote_key)` | 检查文件是否存在 |
| `copy_file(src_key, dest_key)` | 复制文件 |

### 3.2 配置模块修改

在 `config/` 目录新增存储配置：

**新增文件 `config/storage_config.py`：**

```
配置项：
- STORAGE_TYPE: 'local' | 'oss' | 's3'
- OSS_ACCESS_KEY_ID: 访问密钥ID
- OSS_ACCESS_KEY_SECRET: 访问密钥
- OSS_ENDPOINT: OSS服务端点
- OSS_BUCKET: 存储桶名称
- OSS_INTERNAL_ENDPOINT: 内网端点（可选，用于降低流量费用）
- LOCAL_STORAGE_ROOT: 本地存储根路径（降级使用）
```

### 3.3 上传模块修改 (`routers/uploads.py`)

| 修改点 | 说明 |
|-------|------|
| 文件保存逻辑 | 从直接写入本地改为调用存储服务 |
| 记录存储位置 | 在数据库中记录 `oss_key` 和 `storage_type` |
| 文件验证 | 增加文件大小限制和类型校验 |

### 3.4 Docking任务模块修改 (`routers/docking.py`)

| 修改点 | 说明 |
|-------|------|
| 受体文件获取 | 从OSS下载到临时目录供计算使用 |
| 输入参数保存 | 将 `input.json` 上传到OSS |
| 任务目录创建 | 改为创建OSS前缀路径记录 |

### 3.5 Peptide任务模块修改 (`routers/peptide.py`)

| 修改点 | 说明 |
|-------|------|
| PDB文件复制 | 从OSS下载并上传到任务目录 |
| FASTA文件创建 | 上传到OSS任务目录 |
| 配置文件保存 | 上传到OSS |

### 3.6 任务处理器修改 (`async_task_processor.py`)

| 修改点 | 说明 |
|-------|------|
| 输入文件读取 | 从OSS下载到本地临时目录 |
| 结果文件保存 | 计算完成后上传到OSS |
| 临时文件清理 | 增加本地临时文件清理逻辑 |

### 3.7 任务结果下载修改 (`routers/tasks.py`)

| 修改点 | 说明 |
|-------|------|
| 文件下载接口 | 支持从OSS直接流式传输或返回预签名URL |
| ZIP打包下载 | 先从OSS下载所有文件，再打包 |
| CSV下载 | 从OSS读取JSON/CSV并处理 |

### 3.8 数据库层修改

**`database/models/upload.py`：**
- 扩展 `UserUpload` 模型，增加OSS相关字段

**`database/repositorys/upload_repository.py`：**
- 修改CREATE语句，支持新字段
- 增加按storage_type查询方法

---

## 四、实施路线图

### 阶段一：基础设施准备（1-2天）

1. [ ] 创建OSS Bucket并配置权限
2. [ ] 配置OSS访问密钥
3. [ ] 创建存储服务抽象层代码结构
4. [ ] 实现本地存储适配器（兼容现有逻辑）
5. [ ] 实现OSS存储适配器
6. [ ] 添加存储配置模块

### 阶段二：数据库扩展（0.5天）

1. [ ] 编写数据库迁移脚本
2. [ ] 扩展 `user_uploads` 表
3. [ ] 扩展 `tasks` 表
4. [ ] 更新ORM模型

### 阶段三：上传模块迁移（1天）

1. [ ] 修改上传接口使用存储服务
2. [ ] 更新上传记录保存逻辑
3. [ ] 编写单元测试
4. [ ] 灰度测试

### 阶段四：任务创建模块迁移（1-2天）

1. [ ] 修改Docking任务创建流程
2. [ ] 修改Peptide任务创建流程
3. [ ] 修改Generate任务创建流程
4. [ ] 编写集成测试

### 阶段五：任务处理器迁移（1-2天）

1. [ ] 修改异步任务处理器的文件读写
2. [ ] 协调peptide_opt服务的存储适配
3. [ ] 实现临时文件管理
4. [ ] 测试任务完整流程

### 阶段六：下载接口迁移（1天）

1. [ ] 修改文件下载接口
2. [ ] 实现预签名URL方案
3. [ ] 优化大文件下载性能
4. [ ] 测试下载功能

### 阶段七：历史数据迁移（1-2天）

1. [ ] 编写数据迁移脚本
2. [ ] 分批迁移历史文件
3. [ ] 更新数据库记录
4. [ ] 验证迁移结果

### 阶段八：收尾与优化（1天）

1. [ ] 清理本地历史文件（确认无误后）
2. [ ] 配置OSS生命周期规则
3. [ ] 设置监控告警
4. [ ] 更新部署文档

---

## 五、关键技术决策

### 5.1 文件访问策略

| 场景 | 策略 | 原因 |
|------|------|------|
| 小文件下载（<10MB） | 服务器流式中转 | 简单可控 |
| 大文件下载（>10MB） | 预签名URL直接下载 | 减少服务器带宽压力 |
| 任务处理时读取 | 下载到本地临时目录 | 兼容现有计算逻辑 |
| 结果文件保存 | 直接上传到OSS | 减少本地存储压力 |

### 5.2 临时文件管理

- 使用 `/tmp/astramolecula/{session_id}/` 作为临时目录
- 任务完成后自动清理
- 配置定时任务清理超时临时文件

### 5.3 降级策略

- 当OSS不可用时，自动降级到本地存储
- 记录降级日志并告警
- 支持配置强制使用本地存储

### 5.4 peptide_opt服务协同

peptide_opt是独立服务，需要考虑两种方案：

**方案A：共享存储服务**
- peptide_opt也接入OSS
- 共用同一存储配置
- 需要修改peptide_opt代码

**方案B：保持本地存储交互（推荐）**
- 主服务从OSS下载文件到约定目录
- peptide_opt从本地目录读取
- peptide_opt结果写入本地目录
- 主服务将结果上传到OSS

---

## 六、风险与应对

| 风险 | 影响 | 应对措施 |
|------|------|---------|
| OSS服务中断 | 文件上传/下载失败 | 实现本地存储降级 |
| 网络延迟增加 | 任务执行变慢 | 使用内网Endpoint |
| 历史数据丢失 | 用户文件不可用 | 迁移前完整备份 |
| 成本超预期 | 运营成本增加 | 设置生命周期规则自动清理 |

---

## 七、成本估算

### 7.1 OSS费用组成

| 费用项 | 估算依据 | 月成本估算 |
|-------|---------|-----------|
| 存储费用 | 100GB * ¥0.12/GB | ¥12 |
| 请求费用 | 100万次 * ¥0.01/万次 | ¥1 |
| 流量费用（外网） | 50GB * ¥0.50/GB | ¥25 |
| 流量费用（内网） | 免费 | ¥0 |

**月度总成本估算：¥40-100**（根据实际使用量浮动）

### 7.2 成本优化建议

1. 使用内网Endpoint减少流量费用
2. 配置生命周期规则，自动删除过期任务文件
3. 对大文件使用预签名URL直接下载，减少服务器带宽
4. 使用低频存储类型存储历史任务结果

---

## 八、测试策略

### 8.1 单元测试

- 存储服务接口测试
- 各存储适配器测试
- 配置加载测试

### 8.2 集成测试

- 完整的文件上传流程
- 完整的任务执行流程
- 文件下载流程
- 降级场景测试

### 8.3 性能测试

- 大文件上传性能
- 并发上传性能
- 下载响应时间

### 8.4 回归测试

- 确保所有现有API行为不变
- 确保前端无需修改

---

## 九、部署检查清单

- [ ] OSS Bucket已创建
- [ ] 访问密钥已配置
- [ ] 环境变量已设置
- [ ] 数据库迁移已执行
- [ ] 历史数据已迁移
- [ ] 监控告警已配置
- [ ] 备份策略已生效
- [ ] 文档已更新

---

## 附录A：环境变量配置示例

```bash
# 存储类型: local, oss, s3
STORAGE_TYPE=oss

# 阿里云OSS配置
OSS_ACCESS_KEY_ID=your-access-key-id
OSS_ACCESS_KEY_SECRET=your-access-key-secret
OSS_ENDPOINT=oss-cn-hangzhou.aliyuncs.com
OSS_INTERNAL_ENDPOINT=oss-cn-hangzhou-internal.aliyuncs.com
OSS_BUCKET=astramolecula-storage

# 本地存储配置（降级使用）
LOCAL_STORAGE_ROOT=/data/astramolecula
```

## 附录B：相关文档链接

- [阿里云OSS Python SDK](https://help.aliyun.com/document_detail/32026.html)
- [AWS S3 Boto3文档](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html)
- [MinIO Python SDK](https://docs.min.io/docs/python-client-api-reference.html)
