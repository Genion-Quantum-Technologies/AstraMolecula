# AstraMolecula 数据库初始化指南 (PostgreSQL)

本文档提供了 AstraMolecula 项目所需数据库的完整创建命令。

## 📋 数据库信息

| 配置项 | 值 |
|--------|-----|
| 数据库类型 | PostgreSQL |
| 数据库名 | `mydatabase` |
| 用户名 | `admin` |
| 密码 | `secret` |
| 端口 | `5432` |

## 🗃️ 数据库表结构

项目包含以下 6 张表：

| 表名 | 说明 |
|------|------|
| `users` | 用户表 - 存储系统用户信息 |
| `user_uploads` | 上传文件表 - 记录用户上传的文件 |
| `tasks` | 任务表 - 存储各种任务状态信息 |
| `docking_task_params` | Docking任务参数表 |
| `peptide_task_params` | Peptide任务参数表 |
| `service_user_mappings` | 第三方服务用户映射表 |

---

## 🚀 快速初始化（推荐）

### 方法一：使用 Docker 运行 PostgreSQL

```bash
# 启动 PostgreSQL Docker 容器
sudo docker run -d \
  --name postgres-container \
  -e POSTGRES_USER=admin \
  -e POSTGRES_PASSWORD=secret \
  -e POSTGRES_DB=mydatabase \
  -p 5432:5432 \
  postgres

# 执行初始化 SQL 脚本
sudo docker exec -i postgres-container psql -U admin -d mydatabase < /home/songyou/projects/AstraMolecula/database/init_database_postgres.sql
```

### 方法二：使用本地 PostgreSQL

```bash
# 以 postgres 用户执行 SQL 脚本
psql -U admin -d mydatabase < database/init_database_postgres.sql
```

---

## 🔧 手动初始化（分步执行）

### 第一步：连接 PostgreSQL

```bash
# Docker 方式
sudo docker exec -it postgres-container psql -U admin -d mydatabase

# 本地方式
psql -U admin -d mydatabase
```

### 第二步：创建用户表

```sql
CREATE TABLE IF NOT EXISTS users (
  id CHAR(36) NOT NULL,
  username VARCHAR(255) NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  phone VARCHAR(20) DEFAULT NULL,
  email VARCHAR(255) DEFAULT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  external_user_id VARCHAR(255) DEFAULT NULL,
  source_system VARCHAR(50) DEFAULT 'internal',
  created_by_service VARCHAR(255) DEFAULT NULL,
  is_shadow_user BOOLEAN DEFAULT FALSE,
  migrated_to CHAR(36) DEFAULT NULL,
  user_role VARCHAR(20) DEFAULT 'user',
  is_admin BOOLEAN DEFAULT FALSE,
  PRIMARY KEY (id),
  UNIQUE (username)
);

CREATE INDEX IF NOT EXISTS idx_users_external_user ON users(external_user_id, source_system);
CREATE INDEX IF NOT EXISTS idx_users_is_shadow_user ON users(is_shadow_user);
```

### 第三步：创建用户上传文件表

```sql
CREATE TABLE IF NOT EXISTS user_uploads (
  id CHAR(32) NOT NULL,
  user_id CHAR(36) NOT NULL,
  filename VARCHAR(255) NOT NULL,
  file_path VARCHAR(1024) NOT NULL,
  uploaded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_user_uploads_user_id ON user_uploads(user_id);
```

### 第四步：创建任务表

```sql
CREATE TABLE IF NOT EXISTS tasks (
  id CHAR(36) NOT NULL,
  user_id CHAR(36) NOT NULL,
  task_type VARCHAR(50) NOT NULL,
  job_dir VARCHAR(1024) NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'pending',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  started_at TIMESTAMP DEFAULT NULL,
  finished_at TIMESTAMP DEFAULT NULL,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_tasks_user_id ON tasks(user_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_task_type ON tasks(task_type);
CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at);
```

### 第五步：创建 Docking 任务参数表

```sql
CREATE TABLE IF NOT EXISTS docking_task_params (
  id CHAR(32) NOT NULL,
  task_id CHAR(32) NOT NULL,
  n_ligands INT NOT NULL,
  min_ph DECIMAL(3,1) NOT NULL,
  max_ph DECIMAL(3,1) NOT NULL,
  ph_factor DECIMAL(3,1) NOT NULL DEFAULT 1.5,
  center_x DECIMAL(10,3) NOT NULL,
  center_y DECIMAL(10,3) NOT NULL,
  center_z DECIMAL(10,3) NOT NULL,
  box_size_x DECIMAL(10,3) NOT NULL,
  box_size_y DECIMAL(10,3) NOT NULL,
  box_size_z DECIMAL(10,3) NOT NULL,
  box_volume DECIMAL(15,3) NOT NULL,
  exhaustiveness INT NOT NULL,
  n_poses INT NOT NULL,
  n_jobs INT NOT NULL,
  total_molecules DECIMAL(10,3) NOT NULL,
  core_docking_factor DECIMAL(15,6) NOT NULL,
  pose_generation_factor DECIMAL(10,6) NOT NULL,
  total_compute_units DECIMAL(20,6) NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_docking_task_params_task_id ON docking_task_params(task_id);
```

### 第六步：创建 Peptide 任务参数表

```sql
CREATE TABLE IF NOT EXISTS peptide_task_params (
  id CHAR(32) NOT NULL,
  task_id CHAR(32) NOT NULL,
  peptide_sequence TEXT NOT NULL,
  peptide_length INT NOT NULL,
  receptor_pdb_filename VARCHAR(255) NOT NULL,
  n_iterations INT NOT NULL,
  n_rosetta_runs INT NOT NULL,
  num_seq_per_target INT NOT NULL,
  proteinmpnn_seed INT NOT NULL,
  total_calculations INT NOT NULL,
  complexity_factor DECIMAL(15,6) NOT NULL,
  total_compute_units DECIMAL(20,6) NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_peptide_task_params_task_id ON peptide_task_params(task_id);
```

### 第七步：创建服务用户映射表

```sql
CREATE TABLE IF NOT EXISTS service_user_mappings (
  id VARCHAR(36) NOT NULL DEFAULT gen_random_uuid()::text,
  service_api_key VARCHAR(255) NOT NULL,
  external_user_id VARCHAR(255) NOT NULL,
  internal_user_id VARCHAR(36) NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE (service_api_key, external_user_id)
);

CREATE INDEX IF NOT EXISTS idx_service_user_mappings_service_api_key ON service_user_mappings(service_api_key);
CREATE INDEX IF NOT EXISTS idx_service_user_mappings_external_user_id ON service_user_mappings(external_user_id);
CREATE INDEX IF NOT EXISTS idx_service_user_mappings_internal_user_id ON service_user_mappings(internal_user_id);
CREATE INDEX IF NOT EXISTS idx_service_user_mappings_created_at ON service_user_mappings(created_at);
```

---

## ✅ 验证数据库

### 测试连接

```bash
# Docker 方式
sudo docker exec -it postgres-container psql -U admin -d mydatabase

# 本地方式
psql -U admin -h 127.0.0.1 -d mydatabase
```

### 查看所有表

```sql
\dt
```

### 验证表结构

```sql
\d users
\d user_uploads
\d tasks
\d docking_task_params
\d peptide_task_params
\d service_user_mappings
```

---

## 🗑️ 重置数据库（危险操作！）

> ⚠️ **警告**: 以下操作将删除所有数据，请谨慎执行！

```sql
-- 删除所有表（按外键依赖顺序）
DROP TABLE IF EXISTS docking_task_params;
DROP TABLE IF EXISTS peptide_task_params;
DROP TABLE IF EXISTS service_user_mappings;
DROP TABLE IF EXISTS tasks;
DROP TABLE IF EXISTS user_uploads;
DROP TABLE IF EXISTS users;
```

---

## 🐳 Docker 容器管理

```bash
# 启动容器
sudo docker start postgres-container

# 停止容器
sudo docker stop postgres-container

# 查看容器日志
sudo docker logs postgres-container

# 删除容器（数据会丢失）
sudo docker rm -f postgres-container
```

---

## 📊 ER 图

```
┌─────────────────────┐
│       users         │
├─────────────────────┤
│ id (PK)             │
│ username (UK)       │
│ password_hash       │
│ phone               │
│ email               │
│ user_role           │
│ is_admin            │
│ is_shadow_user      │
│ ...                 │
└─────────────────────┘
         │
         │ 1:N
         ▼
┌─────────────────────┐         ┌─────────────────────────┐
│    user_uploads     │         │   service_user_mappings │
├─────────────────────┤         ├─────────────────────────┤
│ id (PK)             │         │ id (PK)                 │
│ user_id (FK)        │         │ service_api_key         │
│ filename            │         │ external_user_id        │
│ file_path           │         │ internal_user_id        │
│ uploaded_at         │         │ created_at              │
└─────────────────────┘         └─────────────────────────┘
         │
         │ 1:N
         ▼
┌─────────────────────┐
│       tasks         │
├─────────────────────┤
│ id (PK)             │
│ user_id (FK)        │
│ task_type           │
│ job_dir             │
│ status              │
│ created_at          │
│ started_at          │
│ finished_at         │
└─────────────────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌───────────────────┐  ┌───────────────────┐
│docking_task_params│  │peptide_task_params│
├───────────────────┤  ├───────────────────┤
│ id (PK)           │  │ id (PK)           │
│ task_id (FK)      │  │ task_id (FK)      │
│ n_ligands         │  │ peptide_sequence  │
│ exhaustiveness    │  │ peptide_length    │
│ box_volume        │  │ n_iterations      │
│ total_compute_... │  │ total_compute_... │
└───────────────────┘  └───────────────────┘
```

---

## 📝 任务状态说明

`tasks` 表中的 `status` 字段可能的值：

| 状态 | 说明 |
|------|------|
| `pending` | 等待处理 |
| `queued` | 已排队 |
| `running` | 正在运行 |
| `processing` | 处理中（可包含进度） |
| `finished` | 已完成 |
| `failed` | 失败 |
| `cancelled` | 已取消 |
| `paused` | 暂停 |

---

## 🔗 相关文件

- SQL 初始化脚本: [database/init_database.sql](database/init_database.sql)
- Shell 初始化脚本: [database/init_database.sh](database/init_database.sh)
- 数据库配置: [database/config.py](database/config.py)
- 数据模型定义: [database/models/](database/models/)
