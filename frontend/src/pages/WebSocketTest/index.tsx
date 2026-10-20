/**
 * WebSocket 测试页面
 * 用于测试 WebSocket 连接和进度监听
 */
import React, { useState } from 'react';
import {
  Card,
  Button,
  Input,
  Space,
  Typography,
  Tag,
  List,
  Divider,
  message,
} from 'antd';
import {
  PlayCircleOutlined,
  StopOutlined,
  ClearOutlined,
  SendOutlined,
} from '@ant-design/icons';
import { useFileProgress } from '@/hooks/useFileProgress';

const { Title, Text } = Typography;

const WebSocketTestPage: React.FC = () => {
  const [fileId, setFileId] = useState<number>(1);
  const [enabled, setEnabled] = useState(false);
  const [logs, setLogs] = useState<string[]>([]);

  const addLog = (msg: string) => {
    const timestamp = new Date().toLocaleTimeString();
    setLogs((prev) => [`[${timestamp}] ${msg}`, ...prev].slice(0, 50));
  };

  const {
    progress,
    status,
    currentStep,
    message: progressMessage,
    isConnected,
    data,
    disconnect,
    requestProgress,
  } = useFileProgress({
    fileId,
    enabled,
    onComplete: (data) => {
      addLog(`✅ 文件处理完成！数据: ${JSON.stringify(data)}`);
      message.success('文件处理完成！');
    },
    onError: (error) => {
      addLog(`❌ 错误: ${error}`);
      message.error('WebSocket 错误');
    },
  });

  const handleConnect = () => {
    if (!fileId) {
      message.error('请输入文件ID');
      return;
    }
    addLog(`🔌 开始连接 WebSocket, file_id=${fileId}`);
    setEnabled(true);
  };

  const handleDisconnect = () => {
    addLog('🔌 断开 WebSocket 连接');
    setEnabled(false);
    disconnect();
  };

  const handleRequestProgress = () => {
    addLog('📡 手动请求进度');
    requestProgress();
  };

  const handleClearLogs = () => {
    setLogs([]);
  };

  return (
    <div style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }}>
      <Title level={2}>WebSocket 测试页面</Title>

      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        {/* 控制面板 */}
        <Card title="控制面板">
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            {/* 连接状态 */}
            <div>
              <Text strong>连接状态: </Text>
              <Tag color={isConnected ? 'green' : 'red'}>
                {isConnected ? '🟢 已连接' : '🔴 未连接'}
              </Tag>
            </div>

            {/* 文件ID输入 */}
            <Space>
              <Text>文件ID:</Text>
              <Input
                type="number"
                value={fileId}
                onChange={(e) => setFileId(Number(e.target.value))}
                style={{ width: 120 }}
                disabled={enabled}
                placeholder="请输入文件ID"
              />
            </Space>

            {/* 操作按钮 */}
            <Space>
              <Button
                type="primary"
                icon={<PlayCircleOutlined />}
                onClick={handleConnect}
                disabled={enabled}
              >
                连接
              </Button>

              <Button
                danger
                icon={<StopOutlined />}
                onClick={handleDisconnect}
                disabled={!enabled}
              >
                断开
              </Button>

              <Button
                icon={<SendOutlined />}
                onClick={handleRequestProgress}
                disabled={!isConnected}
              >
                请求进度
              </Button>
            </Space>
          </Space>
        </Card>

        {/* 进度信息 */}
        <Card title="进度信息">
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            <div>
              <Text strong>进度: </Text>
              <Tag color="blue">{progress}%</Tag>
            </div>

            <div>
              <Text strong>状态: </Text>
              <Tag
                color={
                  status === 'completed'
                    ? 'green'
                    : status === 'failed'
                    ? 'red'
                    : 'processing'
                }
              >
                {status}
              </Tag>
            </div>

            <div>
              <Text strong>当前步骤: </Text>
              <Tag>{currentStep || '-'}</Tag>
            </div>

            <div>
              <Text strong>消息: </Text>
              <Text>{progressMessage || '-'}</Text>
            </div>

            {data && (
              <div>
                <Text strong>额外数据: </Text>
                <pre
                  style={{
                    background: '#f5f5f5',
                    padding: '12px',
                    borderRadius: '4px',
                    marginTop: '8px',
                  }}
                >
                  {JSON.stringify(data, null, 2)}
                </pre>
              </div>
            )}
          </Space>
        </Card>

        {/* 日志 */}
        <Card
          title="实时日志"
          extra={
            <Button
              size="small"
              icon={<ClearOutlined />}
              onClick={handleClearLogs}
            >
              清空
            </Button>
          }
        >
          <List
            size="small"
            dataSource={logs}
            renderItem={(log) => (
              <List.Item>
                <Text code style={{ fontSize: '12px' }}>
                  {log}
                </Text>
              </List.Item>
            )}
            style={{
              maxHeight: '400px',
              overflow: 'auto',
              background: '#fafafa',
              padding: '12px',
              borderRadius: '4px',
            }}
            locale={{ emptyText: '暂无日志' }}
          />
        </Card>

        {/* 使用说明 */}
        <Card title="使用说明">
          <Space direction="vertical" size="small">
            <Text>1. 输入要监听的文件ID</Text>
            <Text>2. 点击"连接"按钮建立 WebSocket 连接</Text>
            <Text>3. 观察进度信息和实时日志</Text>
            <Text>4. 可以点击"请求进度"手动查询当前进度</Text>
            <Text>5. 处理完成后会收到完成通知</Text>
            <Divider />
            <Text type="secondary">
              提示: 需要先上传并处理文件，才能看到进度更新
            </Text>
            <Text type="secondary">
              WebSocket URL: ws://localhost:8000/ws/file/{'{file_id}'}/progress
            </Text>
          </Space>
        </Card>
      </Space>
    </div>
  );
};

export default WebSocketTestPage;
