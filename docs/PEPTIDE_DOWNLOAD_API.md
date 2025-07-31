# 肽段优化结果文件下载接口文档

## 新增接口

### 1. 获取result数据（JSON格式）

**接口路径**: `GET /tasks/{task_id}/peptide/result`

**功能**: 获取肽段优化任务的结果数据，以JSON格式返回供前端页面展示

**参数**:
- `task_id`: 任务ID (路径参数)

**返回**: 
- **成功 (200)**: JSON格式的结果数据
- **任务未完成 (425/202)**: 任务仍在处理中
- **任务失败 (410)**: 任务执行失败
- **文件不存在 (404)**: result.csv文件未找到
- **权限错误 (404)**: 任务不存在或无权限访问

**响应格式**:
```json
{
  "task_id": "abc123",
  "task_status": "finished",
  "created_at": "2025-07-29T10:00:00Z",
  "finished_at": "2025-07-29T12:00:00Z",
  "data": {
    "columns": ["Original sequence affinity score", "Optimal sequence", "Global score", ...],
    "index": ["Input peptide property", "Docking result rank 1", "Docking result rank 2", ...],
    "rows": [
      {
        "index": "Input peptide property",
        "values": {
          "Original sequence affinity score": "-",
          "Optimal sequence": "MKFLVNVAL",
          "Global score": "-",
          ...
        }
      },
      ...
    ]
  }
}
```

**使用示例**:
```javascript
fetch('/tasks/abc123/peptide/result', {
    headers: {
        'Authorization': `Bearer ${token}`
    }
})
.then(response => response.json())
.then(data => {
    console.log('任务状态:', data.task_status);
    console.log('数据列:', data.data.columns);
    console.log('数据行:', data.data.rows);
});
```

### 2. 下载result.csv文件（原始文件）

**接口路径**: `GET /tasks/{task_id}/peptide/result/download`

**功能**: 下载肽段优化任务的原始CSV文件

**参数**:
- `task_id`: 任务ID (路径参数)

**返回**: 
- **成功 (200)**: CSV文件直接下载
- **任务未完成 (425/202)**: 任务仍在处理中
- **任务失败 (410)**: 任务执行失败
- **文件不存在 (404)**: result.csv文件未找到
- **权限错误 (404)**: 任务不存在或无权限访问

**响应头**:
- `Content-Type`: `text/csv`
- `Content-Disposition`: `attachment; filename=result.csv`
- `Cache-Control`: 缓存控制
- `ETag`: 文件版本标识

**使用示例**:
```bash
curl -H "Authorization: Bearer <token>" \
     -o result.csv \
     "http://localhost:8000/tasks/abc123/peptide/result/download"
```

### 3. 下载output文件夹压缩包

**接口路径**: `GET /tasks/{task_id}/peptide/output`

**功能**: 下载肽段优化任务的整个output文件夹，打包为ZIP压缩包

**参数**:
- `task_id`: 任务ID (路径参数)

**返回**:
- **成功 (200)**: ZIP压缩包直接下载
- **任务未完成 (425/202)**: 任务仍在处理中
- **任务失败 (410)**: 任务执行失败
- **文件夹不存在 (404)**: output文件夹未找到
- **权限错误 (404)**: 任务不存在或无权限访问

**响应头**:
- `Content-Type`: `application/zip`
- `Content-Disposition`: `attachment; filename=peptide_optimization_{task_id}_output.zip`
- `Cache-Control`: 缓存控制
- `ETag`: 压缩包版本标识

**压缩包内容**:
- `result.csv`: 详细分析报告
- `complex*.pdb`: 复合物结构文件
- 其他优化过程生成的文件

**使用示例**:
```bash
curl -H "Authorization: Bearer <token>" \
     -o peptide_results.zip \
     "http://localhost:8000/tasks/abc123/peptide/output"
```

### 4. 获取肽段优化任务状态 (补充接口)

**接口路径**: `GET /peptide/optimize/{task_id}`

**功能**: 获取肽段优化任务的状态和详细信息

**参数**:
- `task_id`: 任务ID (路径参数)

**返回**: 
- **成功 (200)**: 任务详细信息 (JSON格式)
- **权限错误 (404)**: 任务不存在或无权限访问
- **任务类型错误 (400)**: 不是肽段优化任务

**响应示例**:
```json
{
  "id": "abc123",
  "user_id": "user456",
  "task_type": "peptide_optimization",
  "status": "finished",
  "job_dir": "/path/to/job",
  "created_at": "2025-07-29T10:00:00Z",
  "finished_at": "2025-07-29T12:00:00Z"
}
```

## 接口设计特点

### 安全特性
1. **用户权限验证**: 只有任务所有者可以下载
2. **任务类型检查**: 仅支持肽段优化任务
3. **状态验证**: 只有完成的任务才能下载结果

### 性能优化
1. **缓存机制**: 支持HTTP缓存，减少重复传输
2. **流式传输**: 大文件使用StreamingResponse
3. **压缩传输**: ZIP压缩减少传输大小

### 错误处理
1. **状态码规范**: 不同错误情况返回相应的HTTP状态码
2. **详细错误信息**: 提供清晰的错误描述
3. **日志记录**: 记录下载操作以便审计

### 文件结构
```
{job_dir}/
├── input/
│   ├── peptide.fasta
│   └── 5ffg.pdb
├── output/
│   ├── result.csv          # 可通过 /peptide/result 下载
│   ├── complex1.pdb
│   ├── complex2.pdb
│   └── ...
└── optimization_config.txt
```

## 测试方法

使用提供的测试脚本：

### JSON格式接口测试
```bash
cd /path/to/dockingVina/test
python3 test_peptide_json_result.py
```

### 完整功能测试
```bash
cd /path/to/dockingVina/test
python3 test_peptide_download.py
```

或者使用curl命令进行测试：
```bash
# 获取token
TOKEN=$(curl -X POST "http://localhost:8000/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"Admin#2024"}' | jq -r '.access_token')

# 获取JSON格式结果数据
curl -H "Authorization: Bearer $TOKEN" \
     "http://localhost:8000/tasks/{task_id}/peptide/result"

# 下载原始CSV文件
curl -H "Authorization: Bearer $TOKEN" \
     -o result.csv \
     "http://localhost:8000/tasks/{task_id}/peptide/result/download"

# 下载output文件夹
curl -H "Authorization: Bearer $TOKEN" \
     -o output.zip \
     "http://localhost:8000/tasks/{task_id}/peptide/output"
```

## 前端集成示例

### 获取并展示结果数据
```javascript
async function loadPeptideResults(taskId) {
    try {
        const response = await fetch(`/tasks/${taskId}/peptide/result`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (response.ok) {
            const data = await response.json();
            
            // 创建表格展示数据
            const table = document.createElement('table');
            const thead = document.createElement('thead');
            const tbody = document.createElement('tbody');
            
            // 添加表头
            const headerRow = document.createElement('tr');
            headerRow.innerHTML = '<th>序列类型</th>' + 
                data.data.columns.map(col => `<th>${col}</th>`).join('');
            thead.appendChild(headerRow);
            
            // 添加数据行
            data.data.rows.forEach(row => {
                const tr = document.createElement('tr');
                tr.innerHTML = `<td>${row.index}</td>` +
                    data.data.columns.map(col => 
                        `<td>${row.values[col] || ''}</td>`
                    ).join('');
                tbody.appendChild(tr);
            });
            
            table.appendChild(thead);
            table.appendChild(tbody);
            document.getElementById('results-container').appendChild(table);
        }
    } catch (error) {
        console.error('加载结果失败:', error);
    }
}
```

### 提供下载功能
```javascript
function downloadResults(taskId, format) {
    const baseUrl = `/tasks/${taskId}/peptide`;
    let url;
    
    switch(format) {
        case 'csv':
            url = `${baseUrl}/result/download`;
            break;
        case 'zip':
            url = `${baseUrl}/output`;
            break;
        default:
            return;
    }
    
    window.open(url);
}
```
