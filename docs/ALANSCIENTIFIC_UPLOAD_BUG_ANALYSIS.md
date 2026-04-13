# alanscientific.com 文件上传故障分析报告

> 分析时间：2026-03-27  
> 问题页面：`https://www.alanscientific.com/aiService/docking`  
> 报告人：AI Analysis via Playwright

---

## 1. 问题描述

第三方用户在 Molecular Docking 页面尝试上传 PDBqt 文件时，浏览器控制台报错：

```
Failed to load resource: net::ERR_BLOCKED_BY_CLIENT
docking:77 Object
docking:86 Uncaught TypeError: Cannot read properties of null (reading 'msg')
    at docking:86:40
    at Object.complete (main.js?31526:198:25)
    at c (jquery.min.js:3:7857)
    at Object.fireWith (jquery.min.js:3:8658)
    at k (jquery.min.js:5:14138)
    at XMLHttpRequest.r (jquery.min.js:5:18226)
```

---

## 2. 分析过程

通过 Playwright 自动化浏览器执行了以下步骤：

1. 登录 `www.alanscientific.com`，进入 docking 页面
2. 提取页面内联 JavaScript 和 `main.js` 源码
3. 分析 `upload()` 函数逻辑和错误处理链路
4. 直接调用 `/api/aiTask/upload` 接口验证后端响应
5. 对比 AstraMolecula（FastAPI）后端端点，确认后端服务归属

---

## 3. 根因分析

### 3.1 架构发现：alanscientific.com 使用独立后端

| 特征 | alanscientific.com 后端 | AstraMolecula 后端 |
|------|------------------------|-------------------|
| 框架 | Java/Spring Boot（推测） | Python/FastAPI |
| 响应格式 | `{success, code, msg, data}` | `{message, error, error_code, ...}` |
| 上传端点 | `/api/aiTask/upload` | `/upload_pdbqt` |
| `/api/health` | 404 (HTML页面) | JSON 健康检查 |
| `/api/upload_pdbqt` | 404 | 正常工作 |

**结论：`www.alanscientific.com` 的后端不是 AstraMolecula FastAPI 服务，而是一个独立的 Java/Spring Boot 后端。当前工作区中不包含该后端代码。**

### 3.2 错误 #1（主要）：后端上传接口返回异常

向 `/api/aiTask/upload` 发送 POST 请求（携带有效 pdbqt 文件内容），后端始终返回：

```json
{
  "success": false,
  "code": "100",
  "msg": "POST Unknown error",
  "data": null
}
```

- 无文件时返回：`{"success":false,"code":"001","msg":"File is null","data":null}`
- 有文件时返回：`{"success":false,"code":"100","msg":"POST Unknown error","data":null}`

`"POST Unknown error"` 表明后端上传处理器内部发生了**未捕获的异常**，被全局异常处理器 catch 后返回了通用错误。可能的原因包括：

- 文件存储路径未配置或不可写
- 数据库连接问题
- 文件处理逻辑异常（如解析、转码失败）
- MultipartFile 解析参数不匹配（field name 预期不一致）

### 3.3 错误 #2（次要）：前端空值安全 Bug

**错误传播链：**

```
后端返回 {"data": null}
       ↓
main.js upload() 函数: error(res.data)  →  传入 null
       ↓
docking 页面: vant.showToast(err.msg)  →  null.msg
       ↓
Uncaught TypeError: Cannot read properties of null (reading 'msg')
```

**具体代码分析：**

`main.js` 中的 `upload` 函数（错误分支）：

```javascript
// main.js - upload 函数
function upload(file, api, success, error) {
    var formData = new FormData();
    formData.append('file', file);
    $.ajax({
        // ...
        complete: function (res) {
            res = JSON.parse(res.responseText);
            if (res.success) {
                if (success) { success(res.data); }
            } else {
                if (res.code === "003") {
                    // 重定向到登录
                } else {
                    if (error) {
                        error(res.data);   // ← BUG: res.data 为 null
                    }
                }
            }
        }
    });
}
```

docking 页面内联脚本（第 72-87 行）：

```javascript
// docking 页面
App.methods.upload = (file) => {
    return new Promise((resolve) => {
        console.log(file)                           // → docking:74
        App._this.loading = true;
        upload(file.raw, "/api/aiTask/upload", (res) => {
            console.log(res);                       // → docking:77, 成功回调
            App._this.loading = false;
            App._this.form.receptor_filename = res.name;
            resolve({status: 'success', response: {url: ""}});
        }, (err) => {                               // err = res.data = null
            App._this.loading = false;
            vant.showToast(err.msg);                // ← CRASH: null.msg → TypeError
            resolve({status: 'error', response: {url: ""}});
        })
    })
}
```

### 3.4 非问题：`ERR_BLOCKED_BY_CLIENT`

```
js?id=AW-17911337377:293  Failed to load resource: net::ERR_BLOCKED_BY_CLIENT
```

- 来源：Google Ads/Analytics 跟踪脚本 (`googletagmanager.com/gtag/js?id=AW-17911337377`)
- 原因：第三方用户浏览器安装了**广告拦截插件**（如 uBlock Origin、AdBlock Plus 等）
- 影响：**无**。仅阻止了 Google 广告追踪，不影响任何业务功能
- 处理：**无需修复**，这是广告拦截器的正常行为

---

## 4. 修复建议

### 4.1 [P0] 修复后端上传处理器

**位置：** alanscientific.com Java/Spring Boot 后端（不在当前工作区）

**步骤：**
1. 查看后端服务日志，搜索 `/api/aiTask/upload` 请求对应的完整异常堆栈
2. 根据异常类型修复上传处理逻辑
3. 检查常见问题：
   - 文件存储目录是否存在且可写
   - 数据库表/连接是否正常
   - MultipartFile 参数名是否为 `file`
   - 文件大小限制配置（`spring.servlet.multipart.max-file-size`）

### 4.2 [P1] 修复前端 `main.js` 空值安全

**位置：** `main.js` 中的 `upload` 函数

**修改前：**
```javascript
if (error) {
    error(res.data);    // res.data 可能为 null
}
```

**修改后（方案 A — 推荐）：传递完整响应对象**
```javascript
if (error) {
    error(res);         // 传完整对象，包含 msg 字段
}
```

**修改后（方案 B — 最小改动）：空值保护**
```javascript
if (error) {
    error(res.data || {msg: res.msg || "Upload failed"});
}
```

### 4.3 [P1] 修复 docking 页面错误处理

**位置：** docking 页面内联脚本

**修改前：**
```javascript
(err) => {
    App._this.loading = false;
    vant.showToast(err.msg);
}
```

**修改后：**
```javascript
(err) => {
    App._this.loading = false;
    vant.showToast((err && err.msg) || "Upload failed, please try again");
}
```

---

## 5. 验证步骤

1. **修复后端后**：手动上传 `.pdbqt` 文件，检查 `/api/aiTask/upload` 返回 `{"success": true, ...}`
2. **修复前端后**：在后端仍返回错误时，页面应显示 toast 提示而非抛出 JavaScript 异常
3. **广告拦截**：`ERR_BLOCKED_BY_CLIENT` 不需要处理，告知第三方用户此错误可忽略

---

## 6. 总结

| 优先级 | 问题 | 归属 | 状态 |
|--------|------|------|------|
| **P0** | 后端 `/api/aiTask/upload` 返回 "POST Unknown error" | alanscientific.com Java 后端 | 需检查后端日志 |
| **P1** | `main.js` upload 错误回调传入 `null` | 前端 main.js | 需修复 |
| **P1** | docking 页面 `err.msg` 无空值保护 | 前端 docking 页面 | 需修复 |
| 无需处理 | Google Analytics 被广告拦截器阻止 | 用户浏览器 | 正常现象 |

> **核心结论**：上传失败的根本原因在 alanscientific.com 的 Java/Spring Boot 后端，该代码不在当前工作区中。前端的 TypeError 是由于后端返回 `data: null` 时缺少空值保护导致的次生问题。
