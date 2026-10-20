import React, { useEffect, useState } from 'react';
import { Card, Progress, Statistic, Row, Col, Empty, Button, Badge } from 'antd';
import { SyncOutlined, CheckCircleOutlined, WifiOutlined } from '@ant-design/icons';
import { SummarizationProgress } from '../../../types';
import { useWebSocket } from '../../../hooks/useWebSocket';
import { getFileProgressWebSocketUrl } from '../../../utils/websocket';
import request from '../../../utils/request';

interface SummarizationTabProps {
  fileId: string;
  data?: SummarizationProgress;
}

const SummarizationTab: React.FC<SummarizationTabProps> = ({ fileId, data: initialData }) => {
  const [data, setData] = useState<SummarizationProgress | undefined>(initialData);
  const [refreshing, setRefreshing] = useState(false);

  const token = localStorage.getItem('access_token') || '';
  const wsUrl = token ? getFileProgressWebSocketUrl(fileId, token) : null;

  const { isConnected } = useWebSocket(wsUrl, {
    onMessage: (message) => {
      if (!message || message.type === 'pong' || message.status == null) {
        return;
      }

      const step = message.current_step;
      if (
        (step === 'embedding' || step === 'summarization') &&
        message.data?.current != null &&
        message.data?.total != null &&
        message.data.total > 0
      ) {
        const { current, total } = message.data;
        setData({
          total_chunks: total,
          processed_chunks: current,
          progress_percentage: (current / total) * 100,
        });
      } else if (message.status === 'processed' || message.status === 'completed') {
        refreshProgress();
      }
    },
  });

  useEffect(() => {
    setData(initialData);
  }, [initialData]);

  const refreshProgress = async () => {
    setRefreshing(true);
    try {
      const response = (await request.get(
        `/api/files/${fileId}/summarization-progress`
      )) as SummarizationProgress;
      setData(response);
    } catch (err) {
      console.error('Failed to refresh progress:', err);
    } finally {
      setRefreshing(false);
    }
  };

  if (!data) {
    return (
      <Empty description="Summarization not started yet" style={{ padding: '50px' }} />
    );
  }

  const isComplete = data.progress_percentage >= 100;

  return (
    <div style={{ padding: '20px' }}>
      <Card
        title="Vector Storage Progress"
        extra={
          <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
            {isConnected && (
              <Badge
                status="success"
                text={
                  <span style={{ fontSize: '12px' }}>
                    <WifiOutlined /> 实时更新
                  </span>
                }
              />
            )}
            <Button
              icon={<SyncOutlined spin={refreshing} />}
              onClick={refreshProgress}
              loading={refreshing}
              size="small"
            >
              刷新
            </Button>
          </div>
        }
      >
        <div style={{ textAlign: 'center', padding: '40px 0' }}>
          <Progress
            type="circle"
            percent={Math.round(data.progress_percentage)}
            size={200}
            status={isComplete ? 'success' : 'active'}
            format={(percent) =>
              isComplete ? (
                <CheckCircleOutlined style={{ fontSize: '48px', color: '#52c41a' }} />
              ) : (
                `${percent}%`
              )
            }
          />
          <div style={{ marginTop: '30px', fontSize: '18px' }}>
            {isComplete ? (
              <span style={{ color: '#52c41a', fontWeight: 'bold' }}>✓ Storage Complete</span>
            ) : (
              <span>Processing chunks and generating embeddings...</span>
            )}
          </div>
        </div>

        <Row gutter={[24, 24]} style={{ marginTop: '30px' }}>
          <Col xs={24} md={12}>
            <Card hoverable>
              <Statistic
                title="Processed Chunks"
                value={data.processed_chunks}
                suffix={`/ ${data.total_chunks}`}
                valueStyle={{ color: '#1890ff' }}
              />
            </Card>
          </Col>
          <Col xs={24} md={12}>
            <Card hoverable>
              <Statistic
                title="Remaining Chunks"
                value={Math.max(0, data.total_chunks - data.processed_chunks)}
                valueStyle={{ color: '#faad14' }}
              />
            </Card>
          </Col>
        </Row>
      </Card>
    </div>
  );
};

export default SummarizationTab;
