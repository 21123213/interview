import React, { useState, useEffect, type ReactNode } from 'react';
import {
  Card,
  Input,
  Select,
  List,
  Tag,
  Drawer,
  Space,
  Typography,
  Spin,
  Empty,
  Row,
  Col,
} from 'antd';
import { SearchOutlined, FileTextOutlined } from '@ant-design/icons';
import { Chunk } from '../../../types';
import request from '../../../utils/request';

const { Search } = Input;
const { Option } = Select;
const { Text, Paragraph } = Typography;

/** 在文本中高亮 search（大小写不敏感），用于 chunk 列表与详情 */
function highlightText(text: string, query: string): ReactNode {
  const q = query.trim();
  if (!q || !text) return text;

  const lower = text.toLowerCase();
  const needle = q.toLowerCase();
  const parts: ReactNode[] = [];
  let start = 0;
  let idx = lower.indexOf(needle, start);
  let key = 0;

  while (idx !== -1) {
    if (idx > start) {
      parts.push(text.slice(start, idx));
    }
    parts.push(
      <mark
        key={`h-${key++}`}
        style={{
          background: '#ffe58f',
          color: 'inherit',
          padding: '0 1px',
          borderRadius: 2,
        }}
      >
        {text.slice(idx, idx + needle.length)}
      </mark>,
    );
    start = idx + needle.length;
    idx = lower.indexOf(needle, start);
  }

  if (start < text.length) {
    parts.push(text.slice(start));
  }
  return parts.length ? <>{parts}</> : text;
}

interface ViewChunksTabProps {
  fileId: string;
  refreshKey?: number;
}

const getChunkTypes = (chunk: Chunk): string[] => {
  const fromMeta = chunk.metadata?.element_types || [];
  const fromContent = chunk.content_types || chunk.metadata?.content_types || [];
  const merged = [...fromMeta, ...fromContent];
  if (merged.length === 0 && chunk.chunk_type) {
    merged.push(chunk.chunk_type);
  }
  return Array.from(new Set(merged.filter(Boolean)));
};

const ViewChunksTab: React.FC<ViewChunksTabProps> = ({ fileId, refreshKey = 0 }) => {
  const [chunks, setChunks] = useState<Chunk[]>([]);
  const [filteredChunks, setFilteredChunks] = useState<Chunk[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchText, setSearchText] = useState('');
  const [typeFilter, setTypeFilter] = useState<string>('all');
  const [selectedChunk, setSelectedChunk] = useState<Chunk | null>(null);
  const [drawerVisible, setDrawerVisible] = useState(false);
  const [chunkTypes, setChunkTypes] = useState<string[]>([]);
  const hasLoadedRef = React.useRef(false);

  useEffect(() => {
    hasLoadedRef.current = false;
    setSearchText('');
    setTypeFilter('all');
  }, [fileId]);

  useEffect(() => {
    // 首次加载全屏 loading；之后 refreshKey 变化只静默更新列表，不清搜索框
    const isFirst = !hasLoadedRef.current;
    fetchChunks(isFirst);
  }, [fileId, refreshKey]);

  useEffect(() => {
    filterChunks();
  }, [chunks, searchText, typeFilter]);

  const fetchChunks = async (showFullLoading = true) => {
    if (showFullLoading) {
      setLoading(true);
    }
    try {
      const response = (await request.get(`/api/files/${fileId}/chunks`)) as {
        chunks?: Chunk[];
      };
      const data = response.chunks || [];
      setChunks(data);
      hasLoadedRef.current = true;

      const types = Array.from(
        new Set(data.flatMap((c: Chunk) => getChunkTypes(c)))
      ).sort();
      setChunkTypes(types);
    } catch (err) {
      console.error('Failed to fetch chunks:', err);
    } finally {
      setLoading(false);
    }
  };

  const filterChunks = () => {
    let filtered = chunks;

    if (typeFilter !== 'all') {
      filtered = filtered.filter((chunk) => getChunkTypes(chunk).includes(typeFilter));
    }

    if (searchText) {
      filtered = filtered.filter((chunk) =>
        chunk.content.toLowerCase().includes(searchText.toLowerCase())
      );
    }

    setFilteredChunks(filtered);
  };

  const handleChunkClick = (chunk: Chunk) => {
    setSelectedChunk(chunk);
    setDrawerVisible(true);
  };

  const getElementCount = (chunk: Chunk) =>
    chunk.element_count ?? chunk.element_ids?.length ?? 0;

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '50px' }}>
        <Spin size="large" tip="Loading chunks..." />
      </div>
    );
  }

  if (chunks.length === 0) {
    return (
      <Empty description="No chunks available yet" style={{ padding: '50px' }} />
    );
  }

  return (
    <div style={{ padding: '20px' }}>
      <Card title="Chunk Browser" style={{ marginBottom: '20px' }}>
        <Row gutter={[16, 16]} style={{ marginBottom: '20px' }}>
          <Col xs={24} md={16}>
            <Search
              placeholder="Search in chunk content..."
              prefix={<SearchOutlined />}
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              allowClear
              size="large"
            />
          </Col>
          <Col xs={24} md={8}>
            <Select
              style={{ width: '100%' }}
              size="large"
              value={typeFilter}
              onChange={setTypeFilter}
              placeholder="Filter by type"
            >
              <Option value="all">All Types</Option>
              {chunkTypes.map((type) => (
                <Option key={type} value={type}>
                  {type}
                </Option>
              ))}
            </Select>
          </Col>
        </Row>

        <div style={{ marginBottom: '10px' }}>
          <Text type="secondary">
            Showing {filteredChunks.length} of {chunks.length} chunks
          </Text>
        </div>
      </Card>

      <List
        grid={{ gutter: 16, xs: 1, sm: 1, md: 2, lg: 2, xl: 3 }}
        dataSource={filteredChunks}
        renderItem={(chunk, index) => {
          const types = getChunkTypes(chunk);
          return (
            <List.Item>
              <Card
                hoverable
                onClick={() => handleChunkClick(chunk)}
                title={
                  <Space>
                    <FileTextOutlined />
                    <span>Chunk #{index + 1}</span>
                  </Space>
                }
                extra={
                  <Space size={[0, 4]} wrap>
                    {types.slice(0, 3).map((type) => (
                      <Tag key={type} color="blue">
                        {type}
                      </Tag>
                    ))}
                    {types.length > 3 && <Tag>+{types.length - 3}</Tag>}
                  </Space>
                }
              >
                <Space direction="vertical" style={{ width: '100%' }}>
                  <Text strong>Character Count: {chunk.character_count}</Text>
                  {chunk.page_number && (
                    <Text type="secondary">Page: {chunk.page_number}</Text>
                  )}
                  <Text type="secondary">Elements: {getElementCount(chunk)}</Text>
                  <Paragraph
                    ellipsis={{ rows: 3 }}
                    style={{ marginBottom: 0, color: '#666' }}
                  >
                    {highlightText(chunk.content, searchText)}
                  </Paragraph>
                </Space>
              </Card>
            </List.Item>
          );
        }}
      />

      <Drawer
        title="Chunk Details"
        width={720}
        onClose={() => setDrawerVisible(false)}
        open={drawerVisible}
      >
        {selectedChunk && (
          <Space direction="vertical" size="large" style={{ width: '100%' }}>
            <Card title="Metadata">
              <Space direction="vertical" style={{ width: '100%' }}>
                <Text>
                  <strong>Filename:</strong>{' '}
                  {selectedChunk.metadata?.filename || 'N/A'}
                </Text>
                <div>
                  <strong>Type:</strong>
                  <div style={{ marginTop: '8px' }}>
                    {getChunkTypes(selectedChunk).map((type) => (
                      <Tag key={type} color="blue">
                        {type}
                      </Tag>
                    ))}
                  </div>
                </div>
                <Text>
                  <strong>Character Count:</strong> {selectedChunk.character_count}
                </Text>
                {selectedChunk.page_number && (
                  <Text>
                    <strong>Page Number:</strong> {selectedChunk.page_number}
                  </Text>
                )}
                <Text>
                  <strong>Total Elements:</strong> {getElementCount(selectedChunk)}
                </Text>
                {selectedChunk.metadata?.element_types &&
                  selectedChunk.metadata.element_types.length > 0 && (
                    <div>
                      <strong>Element Types:</strong>
                      <div style={{ marginTop: '8px' }}>
                        {selectedChunk.metadata.element_types.map((type, idx) => (
                          <Tag key={idx} color="geekblue">
                            {type}
                          </Tag>
                        ))}
                      </div>
                    </div>
                  )}
              </Space>
            </Card>

            <Card title="Full Content">
              <Paragraph style={{ whiteSpace: 'pre-wrap', fontSize: '14px' }}>
                {highlightText(selectedChunk.content, searchText)}
              </Paragraph>
            </Card>

            {selectedChunk.element_ids && selectedChunk.element_ids.length > 0 && (
              <Card title="Element IDs">
                <div style={{ maxHeight: '200px', overflow: 'auto' }}>
                  {selectedChunk.element_ids.map((id, idx) => (
                    <Tag key={idx} style={{ marginBottom: '8px' }}>
                      {id}
                    </Tag>
                  ))}
                </div>
              </Card>
            )}
          </Space>
        )}
      </Drawer>
    </div>
  );
};

export default ViewChunksTab;
