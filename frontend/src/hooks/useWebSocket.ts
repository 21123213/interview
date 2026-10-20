import { useEffect, useRef, useState, useCallback } from 'react';
import { message } from 'antd';

interface WebSocketMessage {
  status: string;
  progress: number;
  current_step: string;
  message: string;
  [key: string]: any;
}

interface UseWebSocketOptions {
  onMessage?: (data: WebSocketMessage) => void;
  onError?: (error: Event) => void;
  onClose?: () => void;
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
}

export const useWebSocket = (
  url: string | null,
  options: UseWebSocketOptions = {}
) => {
  const {
    onMessage,
    onError,
    onClose,
    reconnectInterval = 3000,
    maxReconnectAttempts = 5,
  } = options;

  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const intentionalCloseRef = useRef(false);

  const connect = useCallback(() => {
    if (!url || wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    try {
      const ws = new WebSocket(url);

      ws.onopen = () => {
        console.log('✅ WebSocket connected:', url);
        setIsConnected(true);
        reconnectAttemptsRef.current = 0;

        // 启动心跳
        const heartbeat = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send('ping');
          }
        }, 30000); // 每30秒发送心跳

        ws.onclose = () => {
          clearInterval(heartbeat);
        };
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          // 心跳响应不进入业务回调，避免覆盖进度状态
          if (data?.type === 'pong') {
            return;
          }
          setLastMessage(data);
          onMessage?.(data);
        } catch (error) {
          console.error('❌ Failed to parse WebSocket message:', error);
        }
      };

      ws.onerror = (error) => {
        console.error('❌ WebSocket error:', error);
        onError?.(error);
      };

      ws.onclose = () => {
        console.log('🔌 WebSocket disconnected');
        setIsConnected(false);
        wsRef.current = null;
        onClose?.();

        // 自动重连（如果不是主动关闭）
        if (!intentionalCloseRef.current) {
          if (reconnectAttemptsRef.current < maxReconnectAttempts) {
            reconnectAttemptsRef.current++;
            console.log(
              `🔄 Reconnecting... (${reconnectAttemptsRef.current}/${maxReconnectAttempts})`
            );

            reconnectTimeoutRef.current = setTimeout(() => {
              connect();
            }, reconnectInterval);
          } else {
            console.error('❌ Max reconnect attempts reached');
            message.error('WebSocket连接失败，请刷新页面重试');
          }
        }
      };

      wsRef.current = ws;
    } catch (error) {
      console.error('❌ Failed to create WebSocket:', error);
    }
  }, [url, onMessage, onError, onClose, reconnectInterval, maxReconnectAttempts]);

  const disconnect = useCallback(() => {
    intentionalCloseRef.current = true;
    
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    setIsConnected(false);
  }, []);

  const sendMessage = useCallback((data: string | object) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      const message = typeof data === 'string' ? data : JSON.stringify(data);
      wsRef.current.send(message);
    } else {
      console.warn('⚠️  WebSocket is not connected');
    }
  }, []);

  useEffect(() => {
    if (url) {
      intentionalCloseRef.current = false;
      connect();
    }

    return () => {
      disconnect();
    };
  }, [url]); // ✅ 只依赖 url 变化

  return {
    isConnected,
    lastMessage,
    sendMessage,
    disconnect,
  };
};
