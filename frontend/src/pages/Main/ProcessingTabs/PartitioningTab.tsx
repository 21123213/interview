import React from 'react';
import { Card, Statistic, Row, Col, Empty } from 'antd';
import {
  FileTextOutlined,
  TableOutlined,
  PictureOutlined,
  FontSizeOutlined,
  UnorderedListOutlined,
} from '@ant-design/icons';
import { PartitioningResult } from '../../../types';

interface PartitioningTabProps {
  fileId: string;
  data?: PartitioningResult;
}

const PartitioningTab: React.FC<PartitioningTabProps> = ({ fileId, data }) => {
  if (!data) {
    return (
      <Empty
        description="Partitioning data not available yet"
        style={{ padding: '50px' }}
      />
    );
  }

  const stats = [
    {
      title: 'Text Sections',
      value: data.element_types.text_sections,
      icon: <FileTextOutlined style={{ fontSize: '24px', color: '#1890ff' }} />,
    },
    {
      title: 'Tables',
      value: data.element_types.tables,
      icon: <TableOutlined style={{ fontSize: '24px', color: '#52c41a' }} />,
    },
    {
      title: 'Images',
      value: data.element_types.images,
      icon: <PictureOutlined style={{ fontSize: '24px', color: '#faad14' }} />,
    },
    {
      title: 'Titles',
      value: data.element_types.titles,
      icon: <FontSizeOutlined style={{ fontSize: '24px', color: '#722ed1' }} />,
    },
    {
      title: 'List Items',
      value: data.element_types.list_items,
      icon: <UnorderedListOutlined style={{ fontSize: '24px', color: '#eb2f96' }} />,
    },
  ];

  return (
    <div style={{ padding: '20px' }}>
      <Card title="Document Elements" style={{ marginBottom: '20px' }}>
        <Statistic
          title="Total Elements"
          value={data.total_elements}
          suffix="elements"
          valueStyle={{ color: '#3f8600', fontSize: '32px' }}
        />
      </Card>

      <Card title="Element Types Breakdown">
        <Row gutter={[16, 16]}>
          {stats.map((stat, index) => (
            <Col xs={24} sm={12} md={8} key={index}>
              <Card hoverable>
                <Statistic
                  title={stat.title}
                  value={stat.value}
                  prefix={stat.icon}
                  valueStyle={{ fontSize: '24px' }}
                />
              </Card>
            </Col>
          ))}
        </Row>
      </Card>
    </div>
  );
};

export default PartitioningTab;
