# DockingVina 免认证日志查看功能使用指南

## 功能概述

我们为DockingVina API添加了免认证的实时日志查看功能，用户可以直接通过浏览器查看系统运行状态和日志信息，无需任何认证或登录。

## 🚀 快速开始

### 方式一：Web界面（推荐）

访问以下地址即可打开实时日志查看器：

```
http://localhost:8000/
```

或者直接访问：

```
http://localhost:8000/static/log-viewer.html
```

### 方式二：API接口

#### 1. 获取可用日志文件列表

```bash
curl "http://localhost:8000/logs/"
```

返回示例：
```json
{
  "available_logs": [
    {
      "name": "docking_service.log",
      "size": 1383,
      "modified": 1756890432.12,
      "path": "/logs/docking_service.log"
    },
    {
      "name": "tasks.log", 
      "size": 10199,
      "modified": 1756652645.21,
      "path": "/logs/tasks.log"
    }
  ],
  "count": 2
}
```

#### 2. 查看对接服务日志（文本格式）

```bash
# 查看最后50行
curl "http://localhost:8000/logs/docking_service.log?lines=50"

# 查看最后10行
curl "http://localhost:8000/logs/docking_service.log?lines=10"
```

#### 3. 查看对接服务日志（JSON格式）

```bash
curl "http://localhost:8000/logs/docking_service.log?lines=20&format=json"
```

返回示例：
```json
{
  "log_file": "docking_service.log",
  "total_lines": 16,
  "returned_lines": 3,
  "entries": [
    {
      "line_number": 14,
      "content": "2025-09-03 17:07:12 | INFO | main.py:39 | Application startup complete"
    },
    {
      "line_number": 15,
      "content": "INFO:     Application startup complete."
    },
    {
      "line_number": 16,
      "content": "INFO:     Uvicorn running on http://0.0.0.0:8000"
    }
  ]
}
```

#### 4. 实时日志查看（推荐用于监控）

```bash
# 获取结构化的实时日志数据，包含日志级别和时间戳解析
curl "http://localhost:8000/logs/live/docking_service?lines=30"
```

返回示例：
```json
{
  "status": "success",
  "log_file": "docking_service.log",
  "total_lines": 16,
  "returned_lines": 3,
  "last_update": 1756890432.12,
  "entries": [
    {
      "line_number": 14,
      "level": "INFO",
      "content": "2025-09-03 17:07:12 | INFO | main.py:39 | Application startup complete",
      "timestamp": "2025-09-03 17:07:12"
    },
    {
      "line_number": 15,
      "level": "INFO",
      "content": "INFO:     Application startup complete.",
      "timestamp": null
    }
  ]
}
```

## 📊 Web界面功能特点

### 🎨 友好的用户界面
- 现代化的暗色主题，适合长时间查看
- 清晰的日志级别颜色区分（ERROR: 红色, WARNING: 黄色, INFO: 蓝色）
- 自动滚动到最新日志

### ⚡ 实时监控
- 自动每5秒刷新日志
- 可手动暂停/启动自动刷新
- 页面失焦时自动暂停，重新获得焦点时恢复

### 🔧 灵活配置
- 选择不同的日志文件（对接服务日志、任务日志）
- 自定义显示行数（10-500行）
- 支持文本和JSON两种输出格式

### 📱 响应式设计
- 适配桌面和移动端
- 可在任何现代浏览器中使用

## 🔒 安全特性

### 免认证访问
- 无需登录或API Key即可访问
- 适合快速故障排查和系统监控

### 安全限制
- 仅允许访问预定义的安全日志文件
- 自动过滤敏感信息
- 限制最大返回行数，防止资源消耗

### 支持的日志文件
- `docking_service.log`: 对接服务主日志
- `tasks.log`: 任务处理日志

## 🛠️ 使用场景

### 1. 开发调试
```bash
# 监控服务启动过程
curl "http://localhost:8000/logs/live/docking_service?lines=20"

# 查看最近的错误信息
curl "http://localhost:8000/logs/docking_service.log?lines=100" | grep ERROR
```

### 2. 系统监控
- 通过Web界面实时监控服务状态
- 设置自动刷新，观察系统运行情况
- 快速发现异常和错误

### 3. 故障排查
- 快速查看最近的日志信息
- 无需服务器登录权限
- 支持移动端访问，便于随时查看

### 4. 第三方集成
```python
import requests

# 定期检查日志中的错误
response = requests.get("http://localhost:8000/logs/live/docking_service?lines=50")
data = response.json()

error_count = sum(1 for entry in data['entries'] if entry['level'] == 'ERROR')
if error_count > 0:
    print(f"发现 {error_count} 个错误，需要关注!")
```

## 📋 API接口列表

| 接口 | 方法 | 描述 | 认证需求 |
|------|------|------|----------|
| `/logs/` | GET | 获取可查看的日志文件列表 | ❌ 无需认证 |
| `/logs/docking_service.log` | GET | 查看对接服务日志 | ❌ 无需认证 |
| `/logs/tasks.log` | GET | 查看任务处理日志 | ❌ 无需认证 |
| `/logs/live/docking_service` | GET | 实时查看对接服务日志 | ❌ 无需认证 |
| `/logs/{log_name}` | GET | 查看指定日志文件 | ❌ 无需认证 |
| `/static/log-viewer.html` | GET | Web日志查看器界面 | ❌ 无需认证 |

## 🔧 技术实现

### 后端特性
- FastAPI路由实现
- 支持路径前缀匹配的中间件
- 文件系统安全访问控制
- 结构化日志数据解析

### 前端特性
- 纯HTML/CSS/JavaScript实现
- 响应式设计
- 实时数据更新
- 优雅的错误处理

## 🎯 最佳实践

### 1. 监控建议
- 定期查看ERROR和WARNING级别的日志
- 使用实时接口进行系统健康检查
- 设置合适的查看行数，避免信息过载

### 2. 性能优化
- 避免频繁请求大量日志数据
- 使用`lines`参数限制返回数据量
- 在页面不可见时自动暂停刷新

### 3. 故障排查
- 优先查看最新的日志信息
- 结合不同日志文件进行问题定位
- 利用浏览器开发者工具查看网络请求

---

**功能特点总结：**
✅ 免认证访问，开箱即用  
✅ 实时监控，自动刷新  
✅ 多种输出格式，灵活选择  
✅ 安全限制，保护系统  
✅ 响应式设计，多端支持  
✅ API和Web界面双重选择  

**立即体验：** 访问 `http://localhost:8000/` 开始使用！
