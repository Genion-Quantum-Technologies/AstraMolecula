# 公开访问 Peptide 3D Viewer API 文档

## 📋 概述

此 API 允许第三方用户（未登录用户）通过分享链接直接访问肽优化结果的 3D 结构文件，无需进行身份认证。

## 🔑 特性

- ✅ **无需认证**: 公开访问，不需要 JWT token 或 API key
- ✅ **安全防护**: 内置路径遍历攻击防护、文件类型限制
- ✅ **CORS 支持**: 允许跨域访问，便于前端集成
- ✅ **缓存优化**: 返回适当的缓存头，提升访问速度
- ⚠️ **仅限 PDB**: 只允许访问 PDB 格式文件

## 📍 API Endpoints

### 1. 获取 PDB 文件内容

**GET** `/public/peptide/{task_id}/complex/{filename}`

获取肽优化任务的 PDB 结构文件内容，用于 3D 可视化。

#### 参数

| 参数名 | 类型 | 位置 | 必需 | 说明 |
|--------|------|------|------|------|
| `task_id` | string | path | ✅ | 肽优化任务的 ID |
| `filename` | string | path | ✅ | PDB 文件名（如 `complex1.pdb`） |

#### 请求示例

```bash
# 使用 curl
curl -X GET "http://localhost:8000/public/peptide/abc123def456/complex/complex1.pdb"

# 使用 JavaScript (fetch)
fetch('http://localhost:8000/public/peptide/abc123def456/complex/complex1.pdb')
  .then(response => response.text())
  .then(pdbContent => {
    console.log('PDB content:', pdbContent);
  });
```

#### 成功响应 (200 OK)

```
Content-Type: text/plain
Access-Control-Allow-Origin: *
Cache-Control: public, max-age=3600

ATOM      1  N   ALA A   1      10.123  12.456  15.789  1.00 20.00           N
ATOM      2  CA  ALA A   1      11.234  13.567  16.890  1.00 20.00           C
...
```

#### 错误响应

**400 Bad Request** - 无效的文件名格式
```json
{
  "detail": "Invalid filename format"
}
```

**400 Bad Request** - 文件类型不允许
```json
{
  "detail": "Only PDB files are allowed"
}
```

**404 Not Found** - 任务不存在
```json
{
  "detail": "Task not found"
}
```

**404 Not Found** - 文件不存在
```json
{
  "detail": "File 'complex1.pdb' not found"
}
```

### 2. 获取任务公开信息

**GET** `/public/peptide/{task_id}/info`

获取肽优化任务的基本信息（不包含敏感数据）。

#### 参数

| 参数名 | 类型 | 位置 | 必需 | 说明 |
|--------|------|------|------|------|
| `task_id` | string | path | ✅ | 肽优化任务的 ID |

#### 请求示例

```bash
curl -X GET "http://localhost:8000/public/peptide/abc123def456/info"
```

#### 成功响应 (200 OK)

```json
{
  "task_id": "abc123def456",
  "task_type": "peptide_optimization",
  "status": "finished",
  "created_at": "2025-11-19T10:30:00",
  "finished_at": "2025-11-19T11:45:00"
}
```

**注意**: 此 API 不返回敏感信息（如 `user_id`, `job_dir` 等）

## 🔒 安全措施

### 1. 文件名验证

- ✅ 只允许字母、数字、下划线、连字符和点号
- ❌ 阻止路径遍历字符（`../`, `..\\` 等）
- ❌ 阻止特殊字符和空格

**允许的文件名示例**:
- ✅ `complex1.pdb`
- ✅ `complex_10.pdb`
- ✅ `peptide-result.pdb`

**被阻止的文件名示例**:
- ❌ `../../../etc/passwd`
- ❌ `complex 1.pdb` (包含空格)
- ❌ `complex1.txt` (非 PDB 文件)

### 2. 文件类型限制

- ✅ 只允许访问 `.pdb` 文件
- ❌ 拒绝其他所有文件类型（`.txt`, `.py`, `.json` 等）

### 3. 路径安全检查

- ✅ 使用 `os.path.realpath()` 验证实际路径
- ✅ 确保文件在任务目录内
- ❌ 防止符号链接攻击

### 4. 访问范围限制

**仅搜索以下安全目录**:
- `{job_dir}/output/`
- `{job_dir}/output/complexes/`
- `{job_dir}/output/complex/`
- `{job_dir}/output/pdb/`
- `{job_dir}/output/pdbs/`

**不允许访问**:
- 用户上传目录
- 配置文件
- 系统文件
- 其他用户的任务

## 🌐 CORS 配置

所有公开 API 响应都包含以下 CORS 头部：

```
Access-Control-Allow-Origin: *
Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS
Access-Control-Allow-Headers: Authorization, X-API-Key, Content-Type
```

这允许从任何前端应用直接调用 API，无需配置代理。

## 📊 使用示例

### 前端集成示例

#### React + 3DMol.js

```javascript
import React, { useEffect, useState } from 'react';

function PublicPeptideViewer({ taskId, filename }) {
  const [pdbContent, setPdbContent] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const loadPDB = async () => {
      try {
        const url = `http://your-api.com/public/peptide/${taskId}/complex/${filename}`;
        const response = await fetch(url);
        
        if (!response.ok) {
          throw new Error(`Failed to load PDB: ${response.status}`);
        }
        
        const content = await response.text();
        setPdbContent(content);
        setLoading(false);
        
        // 初始化 3DMol.js 查看器
        initViewer(content);
      } catch (err) {
        setError(err.message);
        setLoading(false);
      }
    };
    
    loadPDB();
  }, [taskId, filename]);

  const initViewer = (pdbContent) => {
    // 使用 3DMol.js 显示 PDB 结构
    const viewer = $3Dmol.createViewer('viewer', {
      backgroundColor: 'white'
    });
    viewer.addModel(pdbContent, 'pdb');
    viewer.setStyle({}, {cartoon: {color: 'spectrum'}});
    viewer.zoomTo();
    viewer.render();
  };

  if (loading) return <div>Loading 3D structure...</div>;
  if (error) return <div>Error: {error}</div>;
  
  return <div id="viewer" style={{ width: '800px', height: '600px' }} />;
}
```

#### 简单的 HTML 示例

```html
<!DOCTYPE html>
<html>
<head>
  <title>Peptide 3D Viewer</title>
  <script src="https://3dmol.csb.pitt.edu/build/3Dmol-min.js"></script>
</head>
<body>
  <h1>Peptide Optimization Result</h1>
  <div id="viewer" style="width: 800px; height: 600px; border: 1px solid #ccc;"></div>
  
  <script>
    // 从 URL 参数获取 taskId 和 filename
    const urlParams = new URLSearchParams(window.location.search);
    const taskId = urlParams.get('taskId');
    const filename = urlParams.get('filename') || 'complex1.pdb';
    
    // 加载 PDB 文件
    const apiUrl = `http://localhost:8000/public/peptide/${taskId}/complex/${filename}`;
    
    fetch(apiUrl)
      .then(response => response.text())
      .then(pdbContent => {
        // 创建 3DMol.js 查看器
        const viewer = $3Dmol.createViewer('viewer', {
          backgroundColor: 'white'
        });
        
        // 添加 PDB 模型
        viewer.addModel(pdbContent, 'pdb');
        
        // 设置样式
        viewer.setStyle({}, {
          cartoon: { color: 'spectrum' },
          stick: {}
        });
        
        // 居中和渲染
        viewer.zoomTo();
        viewer.render();
      })
      .catch(error => {
        console.error('Error loading PDB:', error);
        document.getElementById('viewer').innerHTML = 
          '<p style="color: red;">Failed to load 3D structure: ' + error.message + '</p>';
      });
  </script>
</body>
</html>
```

## 🧪 测试

运行提供的测试脚本：

```bash
cd /home/davis/projects/AstraMolecula
python test/test_public_peptide_api.py
```

**注意**: 测试前需要：
1. 确保后端服务正在运行 (`./service restart`)
2. 替换脚本中的 `YOUR_TASK_ID_HERE` 为实际存在的任务 ID

## 📝 注意事项

### 性能优化

1. **缓存**: 响应包含 `Cache-Control: public, max-age=3600`，浏览器会缓存 1 小时
2. **CDN**: 可以配置 CDN 缓存公开 API 响应
3. **压缩**: 建议在 Nginx 中启用 gzip 压缩

### 安全建议

1. **频率限制**: 建议添加 rate limiting 防止滥用
   ```python
   # 示例：使用 slowapi
   from slowapi import Limiter
   limiter = Limiter(key_func=get_remote_address)
   
   @router.get("/peptide/{task_id}/complex/{filename}")
   @limiter.limit("60/minute")  # 每分钟最多 60 次请求
   async def get_public_peptide_complex(...):
       ...
   ```

2. **监控**: 记录公开访问日志，监控异常访问模式

3. **隐私**: 确保只分享已完成且用户愿意公开的任务

## 🔗 相关链接

- **前端实现文档**: `/home/davis/projects/llm-front-docker-frontend-uni/docs/PUBLIC_PEPTIDE_VIEWER_IMPLEMENTATION.md`
- **API 主文档**: `API_Documentation.md`
- **测试脚本**: `test/test_public_peptide_api.py`

## 📞 问题反馈

如发现安全问题或 bug，请联系系统管理员。

---

**版本**: 1.0  
**更新时间**: 2025-11-19  
**维护者**: AstraMolecula Team
