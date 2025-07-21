# 日志系统升级说明

## 📋 概述

本次升级对整个应用的日志系统进行了全面优化，新增了以下功能：

- ✅ **时间戳支持**：所有日志都包含详细的时间戳（年-月-日 时:分:秒）
- ✅ **代码位置信息**：显示文件名、行号和函数名
- ✅ **彩色输出**：控制台日志支持颜色高亮
- ✅ **日志分类**：不同模块的日志写入不同文件
- ✅ **日志轮转**：自动压缩和清理旧日志文件
- ✅ **统一配置**：集中管理所有日志配置

## 🗂️ 日志文件结构

```
logs/
├── application.log     # 所有日志（主日志文件）
├── api.log            # API相关日志
├── tasks.log          # 任务管理日志
├── worker.log         # 后台工作线程日志
└── errors.log         # 仅错误级别日志
```

## 📊 日志格式

### 控制台输出格式
```
2025-07-21 14:30:25 | INFO     | tasks.py:67 | User alice requesting generated molecules for task abc123
```

### 文件输出格式
```
2025-07-21 14:30:25 | tasks_router | INFO     | tasks.py:67:get_generated_molecules() | User alice requesting generated molecules for task abc123
```

## 🎨 日志级别和颜色

| 级别     | 颜色   | 用途                    |
|----------|--------|-------------------------|
| DEBUG    | 青色   | 详细的调试信息          |
| INFO     | 绿色   | 一般信息日志            |
| WARNING  | 黄色   | 警告信息                |
| ERROR    | 红色   | 错误信息                |
| CRITICAL | 洋红色 | 严重错误                |

## 🚀 使用方法

### 1. 在代码中使用日志

```python
import logging

# 获取模块专用的logger
logger = logging.getLogger("your_module_name")

# 记录不同级别的日志
logger.debug("详细的调试信息")
logger.info("用户 %s 执行了操作 %s", username, action)
logger.warning("检测到潜在问题: %s", issue)
logger.error("操作失败: %s", error_message)
logger.exception("发生异常", exc_info=True)  # 自动记录异常堆栈
```

### 2. 启动应用

使用新的启动脚本：
```bash
python start_app.py
```

或设置日志级别：
```bash
LOG_LEVEL=DEBUG python start_app.py
```

### 3. 测试日志功能

运行日志测试脚本：
```bash
python test_logging.py
```

## ⚙️ 配置说明

### 环境变量

- `LOG_LEVEL`: 设置日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)

### 日志轮转配置

- **最大文件大小**: 10MB
- **备份文件数量**: 5个
- **编码格式**: UTF-8

## 📝 各模块Logger命名

| 模块                | Logger名称          | 日志文件        |
|--------------------|---------------------|-----------------|
| 任务路由           | `tasks_router`      | tasks.log       |
| 对接路由           | `docking_router`    | api.log         |
| SMILES路由         | `smiles_router`     | api.log         |
| 上传路由           | `uploads_router`    | api.log         |
| 认证路由           | `auth_router`       | api.log         |
| 任务工作线程       | `task_worker`       | worker.log      |
| 数据库服务         | `database.*`        | application.log |
| 中间件             | `middleware`        | application.log |
| 工具模块           | `utils.*`           | application.log |

## 🔍 日志监控和分析

### 实时查看日志

```bash
# 查看所有日志
tail -f logs/application.log

# 查看API日志
tail -f logs/api.log

# 查看错误日志
tail -f logs/errors.log

# 查看特定用户的操作
grep "User alice" logs/*.log
```

### 日志分析示例

```bash
# 统计API调用次数
grep "requesting" logs/api.log | wc -l

# 查找错误信息
grep "ERROR\|CRITICAL" logs/*.log

# 按时间范围过滤
grep "2025-07-21 14:" logs/application.log
```

## 🛠️ 自定义配置

可以修改 `config/logging_config.py` 文件来调整：

- 日志格式
- 文件路径
- 轮转策略
- Logger配置

## 📚 最佳实践

1. **使用合适的日志级别**
   - DEBUG: 开发调试信息
   - INFO: 用户操作记录
   - WARNING: 可恢复的问题
   - ERROR: 需要关注的错误
   - CRITICAL: 严重的系统错误

2. **记录重要信息**
   - 用户操作（登录、任务创建等）
   - 系统状态变更
   - 错误和异常
   - 性能关键点

3. **避免敏感信息**
   - 不要记录密码
   - 脱敏用户数据
   - 限制API密钥长度

4. **使用参数化日志**
   ```python
   # ✅ 推荐
   logger.info("用户 %s 创建了任务 %s", username, task_id)
   
   # ❌ 不推荐
   logger.info(f"用户 {username} 创建了任务 {task_id}")
   ```

## 🔧 故障排除

### 常见问题

1. **日志文件未创建**
   - 检查 `logs/` 目录权限
   - 确认应用有写入权限

2. **控制台无颜色显示**
   - 在支持颜色的终端中运行
   - 检查环境变量设置

3. **日志级别不生效**
   - 检查环境变量 `LOG_LEVEL`
   - 确认配置文件正确加载

## 📈 性能影响

新的日志系统经过优化，对性能影响最小：

- 使用异步日志写入
- 合理的缓冲策略
- 自动压缩和清理
- 分级存储减少I/O

---

**更新时间**: 2025-07-21  
**版本**: v2.0  
**维护人员**: Development Team
