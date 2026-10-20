# WebSocket 前端使用文档

## 📦 已创建的文件

```
frontend/src/
├── utils/
│   └── websocket.ts              # WebSocket 客户端工具类
├── hooks/
│   ├── useFileProgress.ts        # React Hook - 文件进度监听
│   └── index.ts                  # Hooks 导出
└── components/
    ├── FileProgressModal.tsx     # 进度弹窗组件
    └── FileUploadWithProgress.tsx # 文件上传示例组件
```

---

## 🚀 快速开始

### 1. 基础使用 - React Hook（推荐）

```tsx
import React from 'react';
import { useFileProgress } from '@/hooks/useFileProgress';

function FileProgress({ fileId }: { fileId: number }) {
  const {
    progress,
    status,
    message,
    isConnected,
  } = useFileProgress({
    fileId,
    enabled: true, // 是否启用
    onComplete: (data) => {
      console.log('处理完成！', data);
    },
  });

  return (
    <div>
      <p>进度: {progress}%</p>
      <p>状态: {status}</p>
      <p>提示: {message}</p>
      <p>连接状态: {isConnected ? '已连接' : '未连接'}</p>
    </div>
  );
}
```

### 2. 使用进度弹窗组件

```tsx
import React, { useState } from 'react';
import { Button } from 'antd';
import FileProgressModal from '@/components/FileProgressModal';

function MyComponent() {
  const [visible, setVisible] = useState(false);
  const [fileId, setFileId] = useState<number>(0);

  const handleUploadSuccess = (file: any) => {
    setFileId(file.file_id);
    setVisible(true);
  };

  return (
    <>
      <Button onClick={() => setVisible(true)}>
        查看进度
      </Button>

      <FileProgressModal
        visible={visible}
        fileId={fileId}
        fileName="测试文件.pdf"
        onClose={() => setVisible(false)}
        onComplete={() => {
          console.log('处理完成！');
          // 刷新文件列表等操作
        }}
      />
    </>
  );
}
```

### 3. 直接使用 WebSocket 客户端

如果不使用 React，可以直接使用底层工具类：

```typescript
import { createFileProgressWebSocket } from '@/utils/websocket';

const token = localStorage.getItem('access_token')!;
const ws = createFileProgressWebSocket(fileId, token);

ws.connect(
  (data) => {
    console.log('进度更新:', data);
    // { progress: 50, status: 'processing', message: '正在切片...' }
  },
  (error) => {
    console.error('错误:', error);
  },
  () => {
    console.log('连接关闭');
  }
);

// 手动请求当前进度
ws.requestProgress();

// 关闭连接
ws.disconnect();
```

---

## 📡 API 说明

### WebSocket 端点

#### 1. 文件进度监听

```
ws://localhost:8000/ws/file/{file_id}/progress?token=YOUR_JWT_TOKEN
```

**消息格式**:
```json
{
  "status": "processing",
  "progress": 60,
  "current_step": "chunking",
  "message": "切片生成完成，共125个切片",
  "data": {
    "chunks_count": 125
  }
}
```

**状态值**:
- `pending`: 等待处理
- `processing`: 处理中
- `completed`: 已完成
- `failed`: 失败

**步骤值**:
- `parsing`: 文档解析
- `chunking`: 文本切片
- `embedding`: 向量化
- `completed`: 完成

#### 2. 用户通知

```
ws://localhost:8000/ws/notifications?token=YOUR_JWT_TOKEN
```

用于接收用户相关的系统通知。

---

## 🎯 进度流程

```
上传文件 (0%)
    ↓
开始解析 (10%)
    ↓
解析完成 (35%)
    ↓
开始切片 (40%)
    ↓
切片完成 (60%)
    ↓
向量化中 (65-95%)
    ↓
处理完成 (100%)
```

---

## 🔧 配置

### 环境变量

在 `.env.development` 中配置：

```bash
# API 基础地址
VITE_API_BASE_URL=http://localhost:8000

# WebSocket 会自动从 HTTP URL 转换为 WS URL
# http://localhost:8000 → ws://localhost:8000
# https://example.com → wss://example.com
```

### 修改 WebSocket 配置

在 `src/utils/websocket.ts` 中：

```typescript
export class WebSocketClient {
  private maxReconnectAttempts: number = 5;  // 最大重连次数
  private reconnectDelay: number = 3000;     // 重连延迟(毫秒)
  private heartbeatDelay: number = 30000;    // 心跳间隔(毫秒)
  // ...
}
```

---

## 🎨 自定义进度组件

如果需要自定义进度显示：

```tsx
import { useFileProgress } from '@/hooks/useFileProgress';

function CustomProgress({ fileId }: { fileId: number }) {
  const progress = useFileProgress({ fileId });

  // 根据步骤显示不同的图标
  const stepIcons = {
    parsing: '📄',
    chunking: '✂️',
    embedding: '🧬',
    completed: '✅',
  };

  return (
    <div>
      {/* 自定义进度条 */}
      <div style={{ width: `${progress.progress}%`, height: '4px', background: 'blue' }} />
      
      {/* 步骤图标 */}
      <span>{stepIcons[progress.currentStep]}</span>
      
      {/* 详细信息 */}
      {progress.data && (
        <div>
          元素: {progress.data.elements_count}
          切片: {progress.data.chunks_count}
        </div>
      )}
    </div>
  );
}
```

---

## 🐛 故障排查

### 1. WebSocket 连接失败

**检查**:
- JWT Token 是否有效
- 后端 WebSocket 服务是否启动
- CORS 配置是否正确
- 浏览器控制台是否有错误

**调试**:
```javascript
// 打开浏览器控制台，查看 WebSocket 连接日志
// ✅ WebSocket 连接成功: ws://localhost:8000/ws/file/1/progress?token=...
// 或
// ❌ WebSocket 错误: ...
```

### 2. 进度不更新

**可能原因**:
- Celery worker 未启动
- Redis 未启动
- 后端任务执行失败

**检查**:
```bash
# 查看 Celery 日志
celery -A app.celery_app worker --loglevel=info

# 查看 FastAPI 日志
python backend/app/main.py
```

### 3. Token 认证失败

**解决方案**:
```typescript
// 确保 Token 格式正确
const token = localStorage.getItem('access_token');
if (!token) {
  console.error('未找到 Token');
  return;
}

// Token 应该是纯字符串，不带 "Bearer " 前缀
// ✅ 正确: "eyJhbGciOiJIUzI1NiIs..."
// ❌ 错误: "Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

## 📚 完整示例

查看 `src/components/FileUploadWithProgress.tsx` 获取完整的上传+进度监听示例。

---

## 🔗 相关文档

- 后端 WebSocket 实现: `backend/app/api/websocket.py`
- Celery 任务: `backend/app/tasks/file_processing.py`
- WebSocket 工具类: `frontend/src/utils/websocket.ts`
