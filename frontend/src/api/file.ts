import request from '@/utils/request';
import { FileMetadata, FileListResponse, ApiResponse } from '@/types';

// 上传文件
export const uploadFile = (file: File) => {
  const formData = new FormData();
  formData.append('file', file);
  
  return request.post<any, any>('/api/files/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
};

// 获取文件列表
export const getFileList = (page: number = 1, size: number = 10) => {
  return request.get<any, FileListResponse>('/api/files/list', {
    params: { page, size },
  });
};

// 获取文件详情
export const getFileDetail = (fileId: number) => {
  return request.get<any, FileMetadata>(`/api/files/${fileId}`);
};

// 删除文件
export const deleteFile = (fileId: number) => {
  return request.delete<any, ApiResponse>(`/api/files/${fileId}`);
};

export type BatchDeleteResult = {
  success: boolean;
  deleted: number;
  failed: number;
  message: string;
  errors?: string[];
};

// 批量删除选中文件
export const batchDeleteFiles = (fileIds: number[]) => {
  return request.post<any, BatchDeleteResult>('/api/files/batch-delete', {
    file_ids: fileIds,
  });
};

// 删除当前用户全部文件
export const deleteAllFiles = () => {
  return request.post<any, BatchDeleteResult>('/api/files/delete-all');
};

// 处理文件
export const processFile = (fileId: number) => {
  return request.post<any, ApiResponse>(`/api/files/${fileId}/process`);
};

// 获取文件处理进度
export const getFileProgress = (fileId: number) => {
  return request.get<any, any>(`/api/files/${fileId}/progress`);
};
