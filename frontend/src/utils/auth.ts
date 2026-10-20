import { User } from '@/types';

// Token管理
export const setToken = (token: string) => {
  localStorage.setItem('access_token', token);
};

export const getToken = (): string | null => {
  return localStorage.getItem('access_token');
};

export const removeToken = () => {
  localStorage.removeItem('access_token');
};

// 用户信息管理
export const setUserInfo = (user: User) => {
  localStorage.setItem('user_info', JSON.stringify(user));
};

export const getUserInfo = (): User | null => {
  const userStr = localStorage.getItem('user_info');
  return userStr ? JSON.parse(userStr) : null;
};

export const removeUserInfo = () => {
  localStorage.removeItem('user_info');
};

// 检查是否已登录
export const isAuthenticated = (): boolean => {
  return !!getToken();
};

// 登出
export const logout = () => {
  removeToken();
  removeUserInfo();
};
