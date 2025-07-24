# 任务API优化说明

## 问题描述
前端频繁轮询任务的文件下载接口，导致大量无效请求和日志记录。

## 解决方案

### 1. 优化HTTP状态码
- `425 Too Early`: 任务待处理 (pending)
- `202 Accepted`: 任务处理中 (processing) 
- `410 Gone`: 任务失败 (failed)
- `409 Conflict`: 其他状态冲突
- `200 OK`: 任务完成，文件可下载

### 2. 新增状态检查接口
**GET `/tasks/{task_id}/status`**
```json
{
  "status": "processing|pending|finished|failed",
  "progress": 0-100,
  "updated_at": "2025-07-21T18:26:17",
  "poll_interval": 5,
  "can_download": false
}
```

### 3. 添加缓存机制
- 文件响应添加 `Cache-Control` 和 `ETag` 头
- 缓存时间：1小时（可配置）

### 4. 减少日志噪音
- 只在成功访问时记录日志
- 失败状态不记录详细信息

## 前端最佳实践建议

### 1. 智能轮询策略
```javascript
async function pollTaskStatus(taskId) {
    while (true) {
        const response = await fetch(`/tasks/${taskId}/status`);
        const data = await response.json();
        
        if (data.poll_interval === 0) {
            // 任务完成或失败，停止轮询
            break;
        }
        
        // 根据服务器建议的间隔轮询
        await sleep(data.poll_interval * 1000);
    }
}
```

### 2. 条件文件下载
```javascript
// 只在任务完成时才尝试下载文件
if (taskStatus.can_download) {
    const fileResponse = await fetch(`/tasks/${taskId}/sdf/${filename}`);
    if (fileResponse.ok) {
        // 处理文件下载
    }
}
```

### 3. 错误处理
```javascript
try {
    const response = await fetch(`/tasks/${taskId}/sdf/${filename}`);
    
    switch (response.status) {
        case 425: // 任务待处理
        case 202: // 任务处理中
            // 继续轮询，不要立即重试下载
            break;
        case 410: // 任务失败
            // 显示错误信息，停止轮询
            break;
        case 200: // 成功
            // 处理文件下载
            break;
    }
} catch (error) {
    // 网络错误处理
}
```

### 4. 使用状态检查接口
- 优先使用 `/tasks/{task_id}/status` 进行轮询
- 只在确认任务完成后才调用文件下载接口
- 减少对文件下载接口的直接轮询

## 配置说明

文件: `config/api_config.py`
- `CACHE_SETTINGS`: 缓存配置
- `TASK_STATUS_PRIORITY`: 任务状态优先级
- `POLLING_SETTINGS`: 轮询建议配置

## 监控建议

1. 监控各接口的调用频率
2. 关注 202/425 状态码的响应率
3. 检查缓存命中率
4. 监控轮询模式的改善情况
