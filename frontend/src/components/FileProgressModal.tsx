/**
 * 文件处理进度弹窗组件
 * 实时显示文件处理进度（WebSocket）
 */
import React from 'react';
import { Modal, Progress, Space, Typography, Tag } from 'antd';
import {
  LoadingOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  SyncOutlined,
} from '@ant-design/icons';
import { useFileProgress } from '@/hooks/useFileProgress';

const { Text, Title } = Typography;

interface FileProgressModalProps {
  visible: boolean;
  fileId: number;
  fileName: string;
  onClose: () => void;
  onComplete?: () => void;
}

const FileProgressModal: React.FC<FileProgressModalProps> = ({
  visible,
  fileId,
  fileName,
  onClose,
  onComplete,
}) => {
  const {
    progress,
    status,
    currentStep,
    message: progressMessage,
    isConnected,
    data,
  } = useFileProgress({
    fileId,
    enabled: visible,
    onComplete: () => {
      onComplete?.();
    },
  });

  // 状态映射
  const statusConfig: Record<string, { text: string; color: string; icon: React.ReactNode }> = {
    pending: {
      text: '等待处理',
      color: 'default',
      icon: <SyncOutlined spin />,
    },
    processing: {
      text: '处理中',
      color: 'processing',
      icon: <LoadingOutlined />,
    },
    completed: {
      text: '已完成',
      color: 'success',
      icon: <CheckCircleOutlined />,
    },
    failed: {
      text: '处理失败',
      color: 'error',
      icon: <CloseCircleOutlined />,
    },
  };

  const currentConfig = statusConfig[status] || statusConfig.pending;

  // 步骤映射
  const stepNames: Record<string, string> = {
    parsing: '📄 文档解析',
    chunking: '✂️ 文本切片',
    embedding: '🧬 向量化',
    completed: '✅ 完成',
  };

  return (
    <Modal
      title={
        <Space>
          <span>文件处理进度</span>
          <Tag color={isConnected ? 'green' : 'red'}>
            {isConnected ? '已连接' : '未连接'}
          </Tag>
        </Space>
      }
      open={visible}
      onCancel={onClose}
      footer={null}
      width={600}
      maskClosable={false}
    >
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        {/* 文件名 */}
        <div>
          <Text type="secondary">文件名：</Text>
          <Text strong>{fileName}</Text>
        </div>

        {/* 进度条 */}
        <Progress
          percent={progress}
          status={
            status === 'completed'
              ? 'success'
              : status === 'failed'
              ? 'exception'
              : 'active'
          }
          strokeColor={{
            '0%': '#108ee9',
            '100%': '#87d068',
          }}
        />

        {/* 状态信息 */}
        <Space size="large">
          <div>
            <Text type="secondary">状态：</Text>
            <Tag color={currentConfig.color} icon={currentConfig.icon}>
              {currentConfig.text}
            </Tag>
          </div>

          {currentStep && (
            <div>
              <Text type="secondary">当前步骤：</Text>
              <Text strong>{stepNames[currentStep] || currentStep}</Text>
            </div>
          )}
        </Space>

        {/* 消息 */}
        {progressMessage && (
          <div
            style={{
              padding: '12px',
              background: '#f5f5f5',
              borderRadius: '4px',
            }}
          >
            <Text>{progressMessage}</Text>
          </div>
        )}

        {/* 统计信息 */}
        {data && (
          <div
            style={{
              padding: '12px',
              background: '#fafafa',
              borderRadius: '4px',
              border: '1px solid #d9d9d9',
            }}
          >
            <Title level={5}>处理详情</Title>
            <Space direction="vertical" size="small">
              {data.elements_count !== undefined && (
                <Text>📄 元素数量: {data.elements_count}</Text>
              )}
              {data.chunks_count !== undefined && (
                <Text>✂️ 切片数量: {data.chunks_count}</Text>
              )}
              {data.embedded_count !== undefined && (
                <Text>🧬 已向量化: {data.embedded_count}</Text>
              )}
              {data.current !== undefined && data.total !== undefined && (
                <Text>
                  📊 进度: {data.current} / {data.total}
                </Text>
              )}
            </Space>
          </div>
        )}
      </Space>
    </Modal>
  );
};

export default FileProgressModal;
