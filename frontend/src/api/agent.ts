import request from '@/utils/request';
import type { ApiResponse } from '@/types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const AGENT_TIMEOUT_MS = 300_000;

export type AgentRunMode = 'react' | 'plan_execute';

export type AgentStreamPhase =
  | 'running'
  | 'answering'
  | 'needs_input'
  | string;

export interface AgentQueryRequest {
  query: string;
  session_id?: string;
  mode?: AgentRunMode;
  resume_token?: string;
  answers?: string | Record<string, string>;
}

export interface AgentLogEntry {
  level: string;
  source: string;
  message: string;
  ts?: string;
  step?: number;
  logger?: string;
}

export interface AgentStreamCallbacks {
  onMeta?: (data: { session_id: string; mode?: string; trace_id?: string }) => void;
  onStatus?: (data: { phase: AgentStreamPhase; mode?: string }) => void;
  onLog?: (data: AgentLogEntry) => void;
  onDelta?: (data: { content: string }) => void;
  onNeedsInput?: (data: {
    session_id: string;
    answer: string;
    resume_token: string;
    pending?: Record<string, unknown>;
  }) => void;
  onDone?: (data: {
    session_id: string;
    answer: string;
    status: string;
    steps?: number;
    mode?: string;
    trace_id?: string;
  }) => void;
  onError?: (message: string) => void;
}

const getSessionStorageKey = (): string => {
  try {
    const userStr = localStorage.getItem('user_info');
    if (userStr) {
      const user = JSON.parse(userStr);
      if (user?.id != null) {
        return `agent_session_id_${user.id}`;
      }
    }
  } catch {
    // ignore
  }
  return 'agent_session_id';
};

export const getStoredAgentSessionId = (): string | null =>
  localStorage.getItem(getSessionStorageKey());

export const saveAgentSessionId = (sessionId: string): void => {
  localStorage.setItem(getSessionStorageKey(), sessionId);
};

export const clearStoredAgentSessionId = (): void => {
  localStorage.removeItem(getSessionStorageKey());
};

/** 清空服务端进程内该 session 的 memory / pending */
export const clearAgentSession = (sessionId: string) => {
  return request.delete<any, ApiResponse>(`/api/agent/session/${sessionId}`);
};

const MODE_KEY = 'agent_run_mode';

export const getStoredAgentMode = (): AgentRunMode => {
  const v = localStorage.getItem(MODE_KEY);
  return v === 'plan_execute' ? 'plan_execute' : 'react';
};

export const saveAgentMode = (mode: AgentRunMode): void => {
  localStorage.setItem(MODE_KEY, mode);
};

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
    return { event, data: JSON.parse(dataLines.join('\n')) };
  } catch {
    return null;
  }
};

const dispatchSSE = (payload: SSEPayload, callbacks: AgentStreamCallbacks) => {
  const { event, data } = payload;
  switch (event) {
    case 'meta':
      callbacks.onMeta?.(data as { session_id: string; mode?: string; trace_id?: string });
      break;
    case 'status':
      callbacks.onStatus?.(data as { phase: AgentStreamPhase; mode?: string });
      break;
    case 'log':
      callbacks.onLog?.(data as unknown as AgentLogEntry);
      break;
    case 'delta':
      callbacks.onDelta?.(data as { content: string });
      break;
    case 'needs_input':
      callbacks.onNeedsInput?.(
        data as {
          session_id: string;
          answer: string;
          resume_token: string;
          pending?: Record<string, unknown>;
        },
      );
      break;
    case 'done':
      callbacks.onDone?.(
        data as {
          session_id: string;
          answer: string;
          status: string;
          steps?: number;
          mode?: string;
          trace_id?: string;
        },
      );
      break;
    case 'error':
      callbacks.onError?.(String(data.message || 'Agent 请求失败'));
      break;
    default:
      break;
  }
};

/** Agent SSE（单路多 event：左聊天 / 右日志） */
export const sendAgentQueryStream = async (
  data: AgentQueryRequest,
  callbacks: AgentStreamCallbacks,
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
  const timeoutId = window.setTimeout(() => controller.abort(), AGENT_TIMEOUT_MS);

  if (signal) {
    signal.addEventListener('abort', () => controller.abort(), { once: true });
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/agent/query/stream`, {
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
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const blocks = buffer.split('\n\n');
      buffer = blocks.pop() || '';

      for (const block of blocks) {
        const payload = parseSSEBlock(block.trim());
        if (payload) dispatchSSE(payload, callbacks);
      }
    }

    if (buffer.trim()) {
      const payload = parseSSEBlock(buffer.trim());
      if (payload) dispatchSSE(payload, callbacks);
    }
  } finally {
    window.clearTimeout(timeoutId);
    reader.releaseLock();
  }
};
