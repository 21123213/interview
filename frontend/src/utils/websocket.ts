/**
 * WebSocket 工具函数
 */

/**
 * 获取WebSocket基础URL
 */
export const getWebSocketBaseUrl = (): string => {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = import.meta.env.VITE_API_BASE_URL || 'localhost:8000';
  
  // 移除http/https前缀
  const cleanHost = host.replace(/^https?:\/\//, '');
  
  return `${protocol}//${cleanHost}`;
};

/**
 * 获取文件处理进度的WebSocket URL
 * @param fileId 文件ID
 * @param token JWT token
 */
export const getFileProgressWebSocketUrl = (fileId: string | number, token: string): string => {
  const baseUrl = getWebSocketBaseUrl();
  return `${baseUrl}/ws/file/${fileId}/progress?token=${encodeURIComponent(token)}`;
};

/**
 * 获取用户通知的WebSocket URL
 * @param token JWT token
 */
export const getUserNotificationsWebSocketUrl = (token: string): string => {
  const baseUrl = getWebSocketBaseUrl();
  return `${baseUrl}/ws/notifications?token=${encodeURIComponent(token)}`;
};
