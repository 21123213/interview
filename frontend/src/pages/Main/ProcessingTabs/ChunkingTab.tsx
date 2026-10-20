import React from 'react';
import { Card, Statistic, Row, Col, Empty, Descriptions } from 'antd';
import { ScissorOutlined, BlockOutlined, BarChartOutlined } from '@ant-design/icons';
import { ChunkingResult } from '../../../types';

interface ChunkingTabProps {
  fileId: string;
  data?: ChunkingResult;
}

const ChunkingTab: React.FC<ChunkingTabProps> = ({ fileId, data }) => {
  if (!data) {
    return (
      <Empty
        description="Chunking data not available yet"
        style={{ padding: '50px' }}
      />
    );
  }

  return (
    <div style={{ padding: '20px' }}>
      <Card title="Chunking Summary" style={{ marginBottom: '20px' }}>
        <Row gutter={[24, 24]}>
          <Col xs={24} md={8}>
            <Card hoverable>
              <Statistic
                title="Total Elements"
                value={data.total_elements}
                prefix={<BlockOutlined style={{ color: '#1890ff' }} />}
                valueStyle={{ fontSize: '28px', color: '#1890ff' }}
              />
            </Card>
          </Col>
          <Col xs={24} md={8}>
            <Card hoverable>
              <Statistic
                title="Total Chunks Created"
                value={data.total_chunks}
                prefix={<ScissorOutlined style={{ color: '#52c41a' }} />}
                valueStyle={{ fontSize: '28px', color: '#52c41a' }}
              />
            </Card>
          </Col>
          <Col xs={24} md={8}>
            <Card hoverable>
              <Statistic
                title="Avg Characters per Chunk"
                value={data.avg_chunk_size}
                prefix={<BarChartOutlined style={{ color: '#faad14' }} />}
                valueStyle={{ fontSize: '28px', color: '#faad14' }}
              />
            </Card>
          </Col>
        </Row>
      </Card>

      <Card title="Chunking Strategy">
        <Descriptions bordered column={1}>
          <Descriptions.Item label="Strategy">
            create_chunks_by_title
          </Descriptions.Item>
          <Descriptions.Item label="Description">
            Elements are grouped into chunks based on title boundaries, combining related
            content sections together while maintaining semantic coherence.
          </Descriptions.Item>
          <Descriptions.Item label="Elements per Chunk">
            {data.total_elements > 0
              ? (data.total_elements / data.total_chunks).toFixed(2)
              : 0}
          </Descriptions.Item>
        </Descriptions>
      </Card>
    </div>
  );
};

export default ChunkingTab;
