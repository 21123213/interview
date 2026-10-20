import request from '@/utils/request';
import { LoginRequest, RegisterRequest, LoginResponse, User, ApiResponse } from '@/types';

// 发送验证码
export const sendCode = (phone: string) => {
  return request.post<any, ApiResponse>('/api/auth/send-code', { phone });
};

// 验证验证码
export const verifyCode = (phone: string, code: string) => {
  return request.post<any, ApiResponse>('/api/auth/verify-code', { phone, code });
};

// 用户注册
export const register = (data: RegisterRequest) => {
  return request.post<any, ApiResponse>('/api/auth/register', data);
};

// 用户登录
export const login = (data: LoginRequest) => {
  return request.post<any, LoginResponse>('/api/auth/login', data);
};

// 获取当前用户信息
export const getCurrentUser = () => {
  return request.get<any, User>('/api/auth/me');
};

// 登出
export const logout = () => {
  return request.post<any, ApiResponse>('/api/auth/logout');
};
