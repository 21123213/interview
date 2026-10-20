import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Tabs, Card, Alert, Progress, Badge, Space } from 'antd';
import {
  FileTextOutlined,
  ScissorOutlined,
  FileSearchOutlined,
  EyeOutlined,
  WifiOutlined,
  DisconnectOutlined,
} from '@ant-design/icons';
import { ProcessingStatus } from '../../types';
import PartitioningTab from './ProcessingTabs/PartitioningTab';
import ChunkingTab from './ProcessingTabs/ChunkingTab';
import SummarizationTab from './ProcessingTabs/SummarizationTab';
import ViewChunksTab from './ProcessingTabs/ViewChunksTab';
import { useWebSocket } from '../../hooks/useWebSocket';
import { getFileProgressWebSocketUrl } from '../../utils/websocket';
import request from '../../utils/request';

interface FileProcessingViewProps {
  fileId: string;
  filename: string;
  onBack: () => void;
}

const DETAIL_REFRESH_STEPS = new Set([
  'parsing',
  'chunking',
  'summarization',
  'embedding',
  'completed',
]);

const FileProcessingView: React.FC<FileProcessingViewProps> = ({ fileId, filename, onBack }) => {
  const [status, setStatus] = useState<ProcessingStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [chunksVersion, setChunksVersion] = useState(0);
  const lastStageRef = useRef<string | undefined>(undefined);
  const fetchStatusRef = useRef<() => Promise<void>>(async () => {});
  // 处理到 100% 后不再刷新 View Chunks，避免搜索输入被冲掉
  const processingDoneRef = useRef(false);

  const token = localStorage.getItem('access_token') || '';
  const wsUrl = token ? getFileProgressWebSocketUrl(fileId, token) : null;

  const fetchStatus = useCallback(async () => {
    try {
      const response = (await request.get(`/api/files/${fileId}/status`)) as ProcessingStatus;
      setStatus(response);
      setError(null);
      if (response.current_stage) {
        lastStageRef.current = response.current_stage;
      }
      if (response.status === 'processed' || response.status === 'completed') {
        processingDoneRef.current = true;
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || '获取处理状态失败');
    }
  }, [fileId]);

  useEffect(() => {
    fetchStatusRef.current = fetchStatus;
  }, [fetchStatus]);

  useEffect(() => {
    lastStageRef.current = undefined;
    processingDoneRef.current = false;
    setStatus(null);
    setError(null);
    setChunksVersion(0);
    fetchStatus();
  }, [fileId, fetchStatus]);

  const { isConnected } = useWebSocket(wsUrl, {
    onMessage: (data) => {
      // 忽略心跳 pong，避免把 status 覆盖成 undefined →「等待处理」
      if (!data || data.type === 'pong' || data.status == null) {
        return;
      }

      const stage = data.current_step as string | undefined;
      const isDone =
        data.status === 'processed' ||
        data.status === 'completed' ||
        data.progress === 100 ||
        stage === 'completed';

      // 已完成后只更新右上角状态，不再重拉 Tab / 刷新切片列表
      if (processingDoneRef.current && !isDone) {
        return;
      }

      const stageChanged = Boolean(stage && stage !== lastStageRef.current);
      const detailReady =
        data.data?.elements_count != null || data.data?.chunks_count != null;

      setStatus((prevStatus) => {
        const next: ProcessingStatus = {
          ...(prevStatus || {
            file_id: fileId,
            filename,
            status: 'pending',
          }),
          file_id: fileId,
          filename,
          status: data.status,
          current_stage: stage,
          progress: data.progress,
          error: data.error,
          partitioning: prevStatus?.partitioning,
          chunking: prevStatus?.chunking,
          summarization: prevStatus?.summarization,
        };

        if (
          (stage === 'summarization' || stage === 'embedding') &&
          data.data &&
          data.data.current != null &&
          data.data.total != null &&
          data.data.total > 0
        ) {
          next.summarization = {
            total_chunks: data.data.total,
            processed_chunks: data.data.current,
            progress_percentage: (data.data.current / data.data.total) * 100,
          };
        }

        if (isDone) {
          if (next.summarization) {
            next.summarization = {
              ...next.summarization,
              processed_chunks: next.summarization.total_chunks,
              progress_percentage: 100,
            };
          }
        }

        return next;
      });

      if (isDone) {
        // 只做最后一次回填，之后停刷
        if (!processingDoneRef.current) {
          processingDoneRef.current = true;
          if (stage) lastStageRef.current = stage;
          fetchStatusRef.current();
          setChunksVersion((v) => v + 1);
        }
        return;
      }

      if (stageChanged || detailReady || data.status === 'failed') {
        if (stage) {
          lastStageRef.current = stage;
        }
        fetchStatusRef.current();

        if (detailReady || stage === 'chunking' || stage === 'embedding') {
          setChunksVersion((v) => v + 1);
        }
      } else if (stage && DETAIL_REFRESH_STEPS.has(stage) && !lastStageRef.current) {
        lastStageRef.current = stage;
      }
    },
    onError: () => {
      if (!processingDoneRef.current) {
        fetchStatusRef.current();
      }
    },
  });

  const getStatusDisplay = () => {
    if (!status) return null;

    const statusConfig: Record<string, { text: string; color: string; status: any }> = {
      pending: { text: '等待处理', color: 'default', status: 'default' },
      processing: { text: '处理中', color: 'processing', status: 'processing' },
      processed: { text: '已完成', color: 'success', status: 'success' },
      completed: { text: '已完成', color: 'success', status: 'success' },
      failed: { text: '失败', color: 'error', status: 'error' },
    };

    const config = statusConfig[status.status] || statusConfig.pending;

    return (
      <Space>
        <Badge status={config.status} text={config.text} />
        {status.status === 'processing' && status.current_stage && (
          <span style={{ fontSize: '12px', color: '#666' }}>({status.current_stage})</span>
        )}
        {status.progress !== undefined && status.status === 'processing' && (
          <Progress type="circle" percent={Math.round(status.progress)} width={40} />
        )}
      </Space>
    );
  };

  const tabItems = [
    {
      key: 'partitioning',
      label: (
        <span>
          <FileTextOutlined /> Partitioning
        </span>
      ),
      children: <PartitioningTab fileId={fileId} data={status?.partitioning} />,
    },
    {
      key: 'chunking',
      label: (
        <span>
          <ScissorOutlined /> Chunking
        </span>
      ),
      children: <ChunkingTab fileId={fileId} data={status?.chunking} />,
    },
    {
      key: 'summarization',
      label: (
        <span>
          <FileSearchOutlined /> Summarisation
        </span>
      ),
      children: <SummarizationTab fileId={fileId} data={status?.summarization} />,
    },
    {
      key: 'view-chunks',
      label: (
        <span>
          <EyeOutlined /> View Chunks
        </span>
      ),
      children: <ViewChunksTab fileId={fileId} refreshKey={chunksVersion} />,
    },
  ];

  return (
    <div style={{ padding: '20px' }}>
      <Card
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <a onClick={onBack} style={{ cursor: 'pointer', color: '#1890ff' }}>
              ← 返回
            </a>
            <span style={{ fontWeight: 'bold' }}>{filename}</span>
          </div>
        }
        extra={
          <Space>
            <Badge
              status={isConnected ? 'success' : 'default'}
              text={
                <span style={{ fontSize: '12px', color: '#666' }}>
                  {isConnected ? (
                    <>
                      <WifiOutlined /> 实时连接
                    </>
                  ) : (
                    <>
                      <DisconnectOutlined /> 离线
                    </>
                  )}
                </span>
              }
            />
            {getStatusDisplay()}
          </Space>
        }
      >
        {error && (
          <Alert
            message="加载失败"
            description={typeof error === 'string' ? error : '获取处理状态失败'}
            type="error"
            showIcon
            style={{ marginBottom: '16px' }}
          />
        )}
        {status?.status === 'failed' && status.error && (
          <Alert
            message="Processing Failed"
            description={status.error}
            type="error"
            showIcon
            style={{ marginBottom: '16px' }}
          />
        )}
        <Tabs items={tabItems} destroyInactiveTabPane={false} />
      </Card>
    </div>
  );
};

export default FileProcessingView;
