import request from '@/utils/request';
import {
  ChatQueryRequest,
  ChatQueryResponse,
  ChatMessage,
  ChatSource,
  ApiResponse,
} from '@/types';

const CHAT_TIMEOUT_MS = 120_000;
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

const getSessionStorageKey = (): string => {
  try {
    const userStr = localStorage.getItem('user_info');
    if (userStr) {
      const user = JSON.parse(userStr);
      if (user?.id != null) {
        return `chat_session_id_${user.id}`;
      }
    }
  } catch {
    // ignore parse errors
  }
  return 'chat_session_id';
};

export const getStoredSessionId = (): string | null => {
  return localStorage.getItem(getSessionStorageKey());
};

export const saveSessionId = (sessionId: string): void => {
  localStorage.setItem(getSessionStorageKey(), sessionId);
};

export const clearStoredSessionId = (): void => {
  localStorage.removeItem(getSessionStorageKey());
};

export type ChatStreamPhase = 'retrieving' | 'generating';

export interface ChatStreamCallbacks {
  onMeta?: (data: { session_id: string }) => void;
  onStatus?: (data: { phase: ChatStreamPhase }) => void;
  onDelta?: (data: { content: string }) => void;
  onDone?: (data: {
    session_id: string;
    answer: string;
    sources: ChatSource[];
  }) => void;
  onError?: (message: string) => void;
}

interface SSEPayload {
  event: string;
  data: Record<string, unknown>;
}

const parseSSEBlock = (block: string): SSEPayload | null => {
  const lines = block.split('\n');
  let event = 'message';
  const dataLines: string[] = [];

  for (const line of lines) {
    if (line.startsWith('event:')) {
      event = line.slice(6).trim();
    } else if (line.startsWith('data:')) {
      dataLines.push(line.slice(5).trim());
    }
  }

  if (dataLines.length === 0) {
    return null;
  }

  try {
    return {
      event,
      data: JSON.parse(dataLines.join('\n')),
    };
  } catch {
    return null;
  }
};

const dispatchSSE = (payload: SSEPayload, callbacks: ChatStreamCallbacks) => {
  const { event, data } = payload;

  switch (event) {
    case 'meta':
      callbacks.onMeta?.(data as { session_id: string });
      break;
    case 'status':
      callbacks.onStatus?.(data as { phase: ChatStreamPhase });
      break;
    case 'delta':
      callbacks.onDelta?.(data as { content: string });
      break;
    case 'done':
      callbacks.onDone?.(data as {
        session_id: string;
        answer: string;
        sources: ChatSource[];
      });
      break;
    case 'error':
      callbacks.onError?.(String(data.message || '流式请求失败'));
      break;
    default:
      break;
  }
};

/** SSE 流式问答（fetch + ReadableStream，支持 Authorization 头） */
export const sendQueryStream = async (
  data: ChatQueryRequest,
  callbacks: ChatStreamCallbacks,
  signal?: AbortSignal,
): Promise<void> => {
  const token = localStorage.getItem('access_token');
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), CHAT_TIMEOUT_MS);

  if (signal) {
    signal.addEventListener('abort', () => controller.abort(), { once: true });
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/chat/query/stream`, {
      method: 'POST',
      headers,
      body: JSON.stringify(data),
      signal: controller.signal,
    });
  } catch (error) {
    window.clearTimeout(timeoutId);
    if (error instanceof DOMException && error.name === 'AbortError') {
      callbacks.onError?.('请求超时，请稍后重试');
      return;
    }
    callbacks.onError?.('网络错误，请检查连接');
    return;
  }

  if (!response.ok) {
    window.clearTimeout(timeoutId);
    let detail = '请求失败';
    try {
      const errBody = await response.json();
      detail = errBody.detail || errBody.message || detail;
    } catch {
      // ignore
    }
    callbacks.onError?.(detail);
    return;
  }

  const reader = response.body?.getReader();
  if (!reader) {
    window.clearTimeout(timeoutId);
    callbacks.onError?.('浏览器不支持流式响应');
    return;
  }

  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }

      buffer += decoder.decode(value, { stream: true });
      const blocks = buffer.split('\n\n');
      buffer = blocks.pop() || '';

      for (const block of blocks) {
        const payload = parseSSEBlock(block.trim());
        if (payload) {
          dispatchSSE(payload, callbacks);
        }
      }
    }

    if (buffer.trim()) {
      const payload = parseSSEBlock(buffer.trim());
      if (payload) {
        dispatchSSE(payload, callbacks);
      }
    }
  } finally {
    window.clearTimeout(timeoutId);
    reader.releaseLock();
  }
};

// 非流式（兼容）
export const sendQuery = (data: ChatQueryRequest) => {
  return request.post<any, ChatQueryResponse>('/api/chat/query', data, {
    timeout: CHAT_TIMEOUT_MS,
  });
};

export const getSessions = () => {
  return request.get<any, any>('/api/chat/sessions');
};

export const getHistory = (sessionId: string) => {
  return request.get<any, { session_id: string; messages: ChatMessage[] }>(
    `/api/chat/history/${sessionId}`
  );
};

export const deleteSession = (sessionId: string) => {
  return request.delete<any, ApiResponse>(`/api/chat/session/${sessionId}`);
};

export const clearAllSessions = () => {
  return request.delete<any, ApiResponse>('/api/chat/clear');
};
