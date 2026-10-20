/**
 * React Hook - 文件处理进度监听
 * 自动管理 WebSocket 连接生命周期
 */
import { useEffect, useState, useCallback, useRef } from 'react';
import { createFileProgressWebSocket, ProgressMessage, WebSocketClient } from '@/utils/websocket';
import { message } from 'antd';

interface UseFileProgressOptions {
  fileId: number;
  enabled?: boolean; // 是否启用监听
  onComplete?: (data: ProgressMessage) => void; // 完成回调
  onError?: (error: Event) => void; // 错误回调
}

interface UseFileProgressReturn {
  progress: number; // 进度 0-100
  status: string; // 状态
  currentStep: string; // 当前步骤
  message: string; // 提示信息
  isConnected: boolean; // 是否已连接
  data?: Record<string, any>; // 额外数据
  disconnect: () => void; // 手动断开连接
  requestProgress: () => void; // 手动请求进度
}

export function useFileProgress(
  options: UseFileProgressOptions
): UseFileProgressReturn {
  const { fileId, enabled = true, onComplete, onError } = options;

  const [progress, setProgress] = useState<number>(0);
  const [status, setStatus] = useState<string>('pending');
  const [currentStep, setCurrentStep] = useState<string>('');
  const [messageText, setMessageText] = useState<string>('');
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [data, setData] = useState<Record<string, any> | undefined>();

  const wsRef = useRef<WebSocketClient | null>(null);

  // 处理进度消息
  const handleMessage = useCallback(
    (msg: ProgressMessage) => {
      setProgress(msg.progress);
      setStatus(msg.status);
      setCurrentStep(msg.current_step);
      setMessageText(msg.message);
      setData(msg.data);

      // 完成时触发回调
      if (msg.status === 'completed' && msg.progress === 100) {
        message.success('文件处理完成！');
        onComplete?.(msg);
      }

      // 失败时显示错误
      if (msg.status === 'failed') {
        message.error(msg.message || '文件处理失败');
      }
    },
    [onComplete]
  );

  // 手动断开连接
  const disconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.disconnect();
      wsRef.current = null;
      setIsConnected(false);
    }
  }, []);

  // 手动请求进度
  const requestProgress = useCallback(() => {
    wsRef.current?.requestProgress();
  }, []);

  // 建立连接
  useEffect(() => {
    if (!enabled || !fileId) {
      return;
    }

    const token = localStorage.getItem('access_token');
    if (!token) {
      console.error('❌ 未找到 access_token，无法建立 WebSocket 连接');
      return;
    }

    // WebSocket URL 根据环境变量配置
    const apiUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
    const wsUrl = apiUrl.replace(/^http/, 'ws'); // http -> ws, https -> wss

    console.log(`🔌 连接 WebSocket: file_id=${fileId}`);

    const ws = createFileProgressWebSocket(fileId, token, wsUrl);

    ws.connect(
      handleMessage,
      (error) => {
        console.error('WebSocket 错误:', error);
        setIsConnected(false);
        onError?.(error);
      },
      () => {
        console.log('WebSocket 连接关闭');
        setIsConnected(false);
      },
      () => {
        console.log('WebSocket 连接成功');
        setIsConnected(true);
      }
    );

    wsRef.current = ws;

    // 清理函数
    return () => {
      disconnect();
    };
  }, [fileId, enabled, handleMessage, onError, disconnect]);

  return {
    progress,
    status,
    currentStep,
    message: messageText,
    isConnected,
    data,
    disconnect,
    requestProgress,
  };
}
