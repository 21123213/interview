/**
 * 文件上传组件示例（集成实时进度监听）
 * 展示如何使用 WebSocket 监听文件处理进度
 */
import React, { useState } from 'react';
import { Upload, Button, message, Space } from 'antd';
import { UploadOutlined, EyeOutlined } from '@ant-design/icons';
import type { UploadProps } from 'antd';
import { uploadFile, processFile } from '@/api/file';
import FileProgressModal from './FileProgressModal';

const FileUploadWithProgress: React.FC = () => {
  const [uploading, setUploading] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [progressVisible, setProgressVisible] = useState(false);
  const [currentFile, setCurrentFile] = useState<{
    id: number;
    name: string;
  } | null>(null);

  // 文件上传
  const handleUpload: UploadProps['customRequest'] = async (options) => {
    const { file, onSuccess, onError } = options;

    setUploading(true);

    try {
      const response = await uploadFile(file as File);

      if (response.success) {
        message.success('文件上传成功！');
        onSuccess?.(response);

        // 保存文件信息
        setCurrentFile({
          id: response.data.file_id,
          name: response.data.filename,
        });

        // 自动开始处理
        handleProcess(response.data.file_id, response.data.filename);
      } else {
        throw new Error(response.message || '上传失败');
      }
    } catch (error: any) {
      console.error('上传错误:', error);
      message.error(error.message || '文件上传失败');
      onError?.(error);
    } finally {
      setUploading(false);
    }
  };

  // 开始处理文件
  const handleProcess = async (fileId: number, fileName: string) => {
    setProcessing(true);

    try {
      const response = await processFile(fileId);

      if (response.success) {
        message.success('开始处理文件...');

        // 显示进度弹窗
        setCurrentFile({ id: fileId, name: fileName });
        setProgressVisible(true);
      } else {
        throw new Error(response.message || '处理失败');
      }
    } catch (error: any) {
      console.error('处理错误:', error);
      message.error(error.message || '文件处理失败');
    } finally {
      setProcessing(false);
    }
  };

  // 处理完成回调
  const handleComplete = () => {
    message.success('文件处理完成！');
    // 这里可以刷新文件列表等操作
  };

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      {/* 上传按钮 */}
      <Upload
        customRequest={handleUpload}
        maxCount={1}
        showUploadList={false}
        accept=".pdf,.txt,.doc,.docx"
      >
        <Button
          type="primary"
          icon={<UploadOutlined />}
          loading={uploading}
          disabled={processing}
        >
          {uploading ? '上传中...' : '选择文件上传'}
        </Button>
      </Upload>

      {/* 查看进度按钮（如果有正在处理的文件） */}
      {currentFile && (
        <Button
          icon={<EyeOutlined />}
          onClick={() => setProgressVisible(true)}
        >
          查看处理进度
        </Button>
      )}

      {/* 进度弹窗 */}
      {currentFile && (
        <FileProgressModal
          visible={progressVisible}
          fileId={currentFile.id}
          fileName={currentFile.name}
          onClose={() => setProgressVisible(false)}
          onComplete={handleComplete}
        />
      )}
    </Space>
  );
};

export default FileUploadWithProgress;
