import { useState, useRef, useEffect, useMemo, type CSSProperties } from 'react';
import { 
  Row, Col, Card, Upload, Button, Input, List, message, 
  Spin, Tag, Space, Typography, Checkbox, Modal, Slider
} from 'antd';
import { 
  UploadOutlined, FolderOpenOutlined, SendOutlined, FileTextOutlined, 
  DeleteOutlined, CheckCircleOutlined, ClockCircleOutlined,
  CloseCircleOutlined, EyeOutlined, SearchOutlined
} from '@ant-design/icons';
import type { UploadProps } from 'antd';
import { uploadFile, getFileList, deleteFile, batchDeleteFiles, deleteAllFiles } from '@/api/file';
import {
  sendQueryStream,
  getHistory,
  getSessions,
  getStoredSessionId,
  saveSessionId,
  clearStoredSessionId,
} from '@/api/chat';
import type { ChatStreamPhase } from '@/api/chat';
import type { FileMetadata, ChatMessage, ChatSession } from '@/types';
import FileProcessingView from './FileProcessingView';

const { TextArea } = Input;
const { Text, Paragraph } = Typography;

const ALLOWED_EXTENSIONS = ['.txt', '.pdf', '.docx', '.md'];
const MAX_FILE_SIZE_MB = 20;

type BrowserFile = File & { webkitRelativePath?: string };

function getFileExt(name: string): string {
  const i = name.lastIndexOf('.');
  return i >= 0 ? name.slice(i).toLowerCase() : '';
}

function toUploadFile(file: BrowserFile): File {
  const relative = (file.webkitRelativePath || '').replace(/\\/g, '/');
  // 文件夹上传时保留相对路径，避免同名文件混淆；路径分隔符改为 __
  if (relative && relative.includes('/')) {
    const safeName = relative.replace(/\//g, '__');
    return new File([file], safeName, { type: file.type || 'text/plain' });
  }
  return file;
}

const TabOne = () => {
  const [files, setFiles] = useState<FileMetadata[]>([]);
  const [filesLoading, setFilesLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [selectedFileIds, setSelectedFileIds] = useState<number[]>([]);
  const [batchDeleting, setBatchDeleting] = useState(false);
  const [fileSearch, setFileSearch] = useState('');
  // 语义权重 0~100；关键词权重 = 100 - 该值（发给后端前转成 0~1）
  const [vectorWeightPct, setVectorWeightPct] = useState(50);
  
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [sending, setSending] = useState(false);
  const [streamPhase, setStreamPhase] = useState<ChatStreamPhase | null>(null);
  const [sessionId, setSessionId] = useState<string>(() => getStoredSessionId() || '');
  const [historyLoading, setHistoryLoading] = useState(false);
  
  // File processing view state
  const [selectedFileId, setSelectedFileId] = useState<number | null>(null);
  const [selectedFilename, setSelectedFilename] = useState<string>('');
  
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // 加载文件列表
  const loadFiles = async () => {
    setFilesLoading(true);
    try {
      const response = await getFileList(1, 10000);
      setFiles(response.items);
      setSelectedFileIds((prev) =>
        prev.filter((id) => response.items.some((f) => f.id === id))
      );
    } catch (error) {
      // 错误已在拦截器处理
    } finally {
      setFilesLoading(false);
    }
  };

  useEffect(() => {
    loadFiles();
  }, []);

  // 登录/刷新后从后端恢复会话：localStorage 指针 → 否则取最近会话列表
  useEffect(() => {
    let cancelled = false;

    const restore = async () => {
      setHistoryLoading(true);
      try {
        const storedSessionId = getStoredSessionId();
        if (storedSessionId) {
          try {
            const response = await getHistory(storedSessionId);
            if (!cancelled) {
              setSessionId(storedSessionId);
              setMessages(response.messages || []);
            }
            return;
          } catch (err: unknown) {
            const status = (err as { response?: { status?: number } })?.response?.status;
            // 仅会话不存在时清指针；网络/401 等保留，避免误伤
            if (status === 404) {
              clearStoredSessionId();
            } else if (!cancelled) {
              setSessionId(storedSessionId);
              return;
            }
          }
        }

        const list = await getSessions();
        const sessions: ChatSession[] = (list as { sessions?: ChatSession[] })?.sessions || [];
        if (sessions.length === 0 || cancelled) {
          return;
        }
        const latestId = sessions[0].session_id;
        const history = await getHistory(latestId);
        if (!cancelled) {
          setSessionId(latestId);
          saveSessionId(latestId);
          setMessages(history.messages || []);
        }
      } catch {
        // 错误已在拦截器处理
      } finally {
        if (!cancelled) {
          setHistoryLoading(false);
        }
      }
    };

    void restore();
    return () => {
      cancelled = true;
    };
  }, []);

  // 滚动到底部
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // 批量上传（多文件 / 文件夹）；仅在 fileList 最后一项时触发一次
  const uploadBatch = async (fileList: BrowserFile[]) => {
    const valid: BrowserFile[] = [];
    let skippedType = 0;
    let skippedSize = 0;

    for (const file of fileList) {
      const ext = getFileExt(file.name);
      if (!ALLOWED_EXTENSIONS.includes(ext)) {
        skippedType += 1;
        continue;
      }
      if (file.size / 1024 / 1024 > MAX_FILE_SIZE_MB) {
        skippedSize += 1;
        continue;
      }
      valid.push(file);
    }

    if (valid.length === 0) {
      message.warning(
        `未找到可上传文件（支持 ${ALLOWED_EXTENSIONS.join('/')}，单文件 ≤${MAX_FILE_SIZE_MB}MB）`
      );
      return;
    }

    setUploading(true);
    let ok = 0;
    let fail = 0;
    let hideLoading = message.loading(`正在上传 0/${valid.length}...`, 0);
    try {
      for (let i = 0; i < valid.length; i += 1) {
        hideLoading();
        hideLoading = message.loading(`正在上传 ${i + 1}/${valid.length}...`, 0);
        try {
          await uploadFile(toUploadFile(valid[i]));
          ok += 1;
        } catch {
          fail += 1;
        }
      }
    } finally {
      hideLoading();
      setUploading(false);
      loadFiles();
    }

    const skipHint =
      skippedType || skippedSize
        ? `，跳过 ${skippedType + skippedSize} 个（类型/大小不符）`
        : '';
    if (fail === 0) {
      message.success(`上传完成：成功 ${ok} 个${skipHint}`);
    } else {
      message.warning(`上传完成：成功 ${ok}，失败 ${fail}${skipHint}`);
    }
  };

  const makeUploadProps = (directory: boolean): UploadProps => ({
    name: 'file',
    multiple: true,
    directory,
    showUploadList: false,
    accept: directory ? undefined : ALLOWED_EXTENSIONS.join(','),
    disabled: uploading,
    beforeUpload: (file, fileList) => {
      // 等本批最后一个文件进入后再统一上传，避免重复触发
      if (file.uid !== fileList[fileList.length - 1]?.uid) {
        return false;
      }
      void uploadBatch(fileList as BrowserFile[]);
      return false;
    },
  });

  // 删除文件
  const handleDeleteFile = async (fileId: number) => {
    try {
      await deleteFile(fileId);
      message.success('文件删除成功');
      setSelectedFileIds((prev) => prev.filter((id) => id !== fileId));
      loadFiles();
    } catch (error) {
      // 错误已在拦截器处理
    }
  };

  const filteredFiles = useMemo(() => {
    const q = fileSearch.trim().toLowerCase();
    if (!q) return files;
    // 简单模糊：连续子串 + 去空格/下划线后再匹配
    const compact = q.replace(/[\s_\-%.]+/g, '');
    return files.filter((f) => {
      const name = (f.original_filename || '').toLowerCase();
      if (name.includes(q)) return true;
      const nameCompact = name.replace(/[\s_\-%.]+/g, '');
      return compact.length > 0 && nameCompact.includes(compact);
    });
  }, [files, fileSearch]);

  const allSelected =
    filteredFiles.length > 0 &&
    filteredFiles.every((f) => selectedFileIds.includes(f.id));
  const someSelected =
    filteredFiles.some((f) => selectedFileIds.includes(f.id)) && !allSelected;

  const toggleSelectAll = (checked: boolean) => {
    if (checked) {
      setSelectedFileIds((prev) =>
        Array.from(new Set([...prev, ...filteredFiles.map((f) => f.id)])),
      );
    } else {
      const drop = new Set(filteredFiles.map((f) => f.id));
      setSelectedFileIds((prev) => prev.filter((id) => !drop.has(id)));
    }
  };

  const toggleSelectOne = (fileId: number, checked: boolean) => {
    setSelectedFileIds((prev) =>
      checked ? Array.from(new Set([...prev, fileId])) : prev.filter((id) => id !== fileId)
    );
  };

  const handleBatchDelete = () => {
    if (selectedFileIds.length === 0) {
      message.warning('请先勾选要删除的文件');
      return;
    }
    Modal.confirm({
      title: `确认删除选中的 ${selectedFileIds.length} 个文件？`,
      content: '将同时清理向量与切片，不可恢复。',
      okText: '删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        setBatchDeleting(true);
        try {
          const res = await batchDeleteFiles(selectedFileIds);
          message.success(res.message || `已删除 ${res.deleted} 个`);
          setSelectedFileIds([]);
          await loadFiles();
        } catch {
          // 错误已在拦截器处理
        } finally {
          setBatchDeleting(false);
        }
      },
    });
  };

  const handleDeleteAll = () => {
    if (files.length === 0) {
      message.warning('没有可删除的文件');
      return;
    }
    Modal.confirm({
      title: `确认清空全部 ${files.length} 个文件？`,
      content: '将删除当前账号下所有上传文件及向量，不可恢复。',
      okText: '全部删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        setBatchDeleting(true);
        try {
          const res = await deleteAllFiles();
          message.success(res.message || `已删除 ${res.deleted} 个`);
          setSelectedFileIds([]);
          await loadFiles();
        } catch {
          // 错误已在拦截器处理
        } finally {
          setBatchDeleting(false);
        }
      },
    });
  };

  // 发送消息（SSE 流式）
  const handleSendMessage = async () => {
    if (!inputValue.trim()) {
      message.warning('请输入内容');
      return;
    }

    const queryText = inputValue.trim();
    const userMessage: ChatMessage = {
      role: 'user',
      content: queryText,
      timestamp: new Date().toISOString(),
    };

    const assistantPlaceholder: ChatMessage = {
      role: 'assistant',
      content: '',
      timestamp: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMessage, assistantPlaceholder]);
    setInputValue('');
    setSending(true);
    setStreamPhase('retrieving');

    try {
      const vectorWeight = vectorWeightPct / 100;
      const bm25Weight = 1 - vectorWeight;
      await sendQueryStream(
        {
          query: queryText,
          session_id: sessionId || undefined,
          vector_weight: vectorWeight,
          bm25_weight: bm25Weight,
        },
        {
          onMeta: ({ session_id }) => {
            if (!sessionId) {
              setSessionId(session_id);
              saveSessionId(session_id);
            }
          },
          onStatus: ({ phase }) => {
            setStreamPhase(phase);
          },
          onDelta: ({ content }) => {
            setMessages((prev) => {
              const next = [...prev];
              const last = next[next.length - 1];
              if (last?.role === 'assistant') {
                next[next.length - 1] = {
                  ...last,
                  content: last.content + content,
                };
              }
              return next;
            });
          },
          onDone: ({ answer, sources }) => {
            setMessages((prev) => {
              const next = [...prev];
              const last = next[next.length - 1];
              if (last?.role === 'assistant') {
                next[next.length - 1] = {
                  ...last,
                  content: answer,
                  sources,
                };
              }
              return next;
            });
          },
          onError: (errMsg) => {
            setMessages((prev) => {
              const next = [...prev];
              const last = next[next.length - 1];
              if (last?.role === 'assistant' && !last.content) {
                next.pop();
              }
              return next;
            });
            message.error(errMsg || '发送失败，请重试');
          },
        },
      );
    } catch {
      message.error('发送失败，请重试');
    } finally {
      setSending(false);
      setStreamPhase(null);
    }
  };

  // 文件状态标签
  const getStatusTag = (status: string) => {
    switch (status) {
      case 'processed':
        return <Tag icon={<CheckCircleOutlined />} color="success">已处理</Tag>;
      case 'processing':
        return <Tag icon={<ClockCircleOutlined />} color="processing">处理中</Tag>;
      case 'failed':
        return <Tag icon={<CloseCircleOutlined />} color="error">失败</Tag>;
      default:
        return <Tag color="default">待处理</Tag>;
    }
  };

  // View file processing details
  const handleViewFileDetails = (file: FileMetadata) => {
    setSelectedFileId(file.id);
    setSelectedFilename(file.original_filename);
  };

  const handleBackToList = () => {
    setSelectedFileId(null);
    setSelectedFilename('');
    loadFiles();
  };

  // If viewing file details, show processing view
  if (selectedFileId) {
    return (
      <FileProcessingView
        fileId={selectedFileId.toString()}
        filename={selectedFilename}
        onBack={handleBackToList}
      />
    );
  }

  const colStyle: CSSProperties = {
    height: '100%',
    maxHeight: '100%',
    overflow: 'hidden',
    display: 'flex',
    flexDirection: 'column',
  };
  const cardStyle: CSSProperties = {
    height: '100%',
    maxHeight: '100%',
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
  };
  const cardBodyStyle: CSSProperties = {
    flex: 1,
    minHeight: 0,
    overflow: 'auto',
    display: 'flex',
    flexDirection: 'column',
  };

  return (
    <Row
      gutter={16}
      style={{
        height: '100%',
        maxHeight: '100%',
        padding: '16px 0',
        overflow: 'hidden',
        flexWrap: 'nowrap',
        margin: 0,
      }}
    >
      {/* 左侧：文件上传（内部滚动，不撑高整页） */}
      <Col span={8} style={colStyle}>
        <Card 
          title="文件上传" 
          style={cardStyle}
          bodyStyle={{ ...cardBodyStyle, paddingBottom: 16 }}
        >
          <Space direction="vertical" style={{ width: '100%' }} size="middle">
            <Upload {...makeUploadProps(false)}>
              <Button
                icon={<UploadOutlined />}
                loading={uploading}
                block
                size="large"
                disabled={uploading}
              >
                {uploading ? '上传中...' : '选择文件（可多选）'}
              </Button>
            </Upload>
            <Upload {...makeUploadProps(true)}>
              <Button
                icon={<FolderOpenOutlined />}
                loading={uploading}
                block
                size="large"
                disabled={uploading}
              >
                {uploading ? '上传中...' : '选择文件夹上传'}
              </Button>
            </Upload>
          </Space>
          
          <div style={{ marginTop: 16, fontSize: 12, color: '#999' }}>
            支持格式：.txt / .pdf / .docx / .md（单文件最大 {MAX_FILE_SIZE_MB}MB）。
            选文件夹时会自动过滤不合规文件；.txt 可正常入库处理。
          </div>

          <div
            style={{
              marginTop: 24,
              marginBottom: 8,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: 8,
              flexWrap: 'wrap',
            }}
          >
            <Space size={12}>
              <span style={{ fontWeight: 'bold' }}>
                已上传文件 (
                {fileSearch.trim()
                  ? `${filteredFiles.length}/${files.length}`
                  : files.length}
                )
              </span>
              <Checkbox
                checked={allSelected}
                indeterminate={someSelected}
                disabled={filteredFiles.length === 0 || batchDeleting}
                onChange={(e) => toggleSelectAll(e.target.checked)}
              >
                全选
              </Checkbox>
            </Space>
            <Space size={8}>
              <Button
                danger
                size="small"
                icon={<DeleteOutlined />}
                disabled={selectedFileIds.length === 0 || batchDeleting}
                loading={batchDeleting}
                onClick={handleBatchDelete}
              >
                删除选中{selectedFileIds.length ? `(${selectedFileIds.length})` : ''}
              </Button>
              <Button
                danger
                type="primary"
                size="small"
                disabled={files.length === 0 || batchDeleting}
                loading={batchDeleting}
                onClick={handleDeleteAll}
              >
                清空全部
              </Button>
            </Space>
          </div>

          <Input
            allowClear
            size="small"
            prefix={<SearchOutlined style={{ color: '#bfbfbf' }} />}
            placeholder="模糊搜索文件名…"
            value={fileSearch}
            onChange={(e) => setFileSearch(e.target.value)}
            style={{ marginBottom: 8 }}
          />

          <Spin spinning={filesLoading}>
            <List
              dataSource={filteredFiles}
              locale={{ emptyText: fileSearch.trim() ? '无匹配文件' : '暂无文件' }}
              renderItem={(file) => (
                <List.Item
                  actions={[
                    <Button 
                      type="link" 
                      size="small"
                      icon={<EyeOutlined />}
                      onClick={() => handleViewFileDetails(file)}
                    >
                      详情
                    </Button>,
                    <Button 
                      type="link" 
                      danger 
                      size="small"
                      icon={<DeleteOutlined />}
                      onClick={() => handleDeleteFile(file.id)}
                    />,
                  ]}
                >
                  <Checkbox
                    checked={selectedFileIds.includes(file.id)}
                    disabled={batchDeleting}
                    onChange={(e) => toggleSelectOne(file.id, e.target.checked)}
                    style={{ marginRight: 12 }}
                  />
                  <List.Item.Meta
                    avatar={<FileTextOutlined style={{ fontSize: 24 }} />}
                    title={<Text ellipsis={{ tooltip: file.original_filename }}>{file.original_filename}</Text>}
                    description={
                      <Space direction="vertical" size={0}>
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          {(file.file_size / 1024).toFixed(2)} KB
                        </Text>
                        {getStatusTag(file.status)}
                      </Space>
                    }
                  />
                </List.Item>
              )}
            />
          </Spin>
        </Card>
      </Col>

      {/* 右侧：对话框（高度锁定视口，输入框始终在底部可见） */}
      <Col span={16} style={colStyle}>
        <Card 
          title="智能问答" 
          style={cardStyle}
          bodyStyle={{
            ...cardBodyStyle,
            padding: 0,
            overflow: 'hidden',
          }}
        >
          {/* 消息列表 */}
          <div style={{ flex: 1, minHeight: 0, overflowY: 'auto', padding: '16px' }}>
            {historyLoading ? (
              <div style={{ textAlign: 'center', padding: '60px 0' }}>
                <Spin tip="加载历史对话..." />
              </div>
            ) : messages.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '60px 0', color: '#999' }}>
                <p>上传文档后，在这里开始提问</p>
                <p style={{ fontSize: 12 }}>例如：这个文档的主要内容是什么？</p>
              </div>
            ) : (
              <>
                {messages.map((msg, index) => (
                  <div
                    key={index}
                    style={{
                      marginBottom: 16,
                      display: 'flex',
                      justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
                    }}
                  >
                    <div
                      style={{
                        maxWidth: '70%',
                        padding: '12px 16px',
                        borderRadius: 8,
                        background: msg.role === 'user' ? '#1890ff' : '#f0f0f0',
                        color: msg.role === 'user' ? 'white' : 'black',
                      }}
                    >
                      <Paragraph 
                        style={{ 
                          margin: 0, 
                          color: msg.role === 'user' ? 'white' : 'inherit',
                          whiteSpace: 'pre-wrap'
                        }}
                      >
                      {msg.content || (sending && index === messages.length - 1 && msg.role === 'assistant' ? (
                        <Text type="secondary" style={{ fontStyle: 'italic' }}>
                          {streamPhase === 'retrieving' ? '正在检索文档...' : '正在生成回答...'}
                        </Text>
                      ) : null)}
                      </Paragraph>
                      {msg.sources && msg.sources.length > 0 && (
                        <div style={{ marginTop: 8, fontSize: 12, opacity: 0.8 }}>
                          来源：{msg.sources.length} 个相关文档片段
                        </div>
                      )}
                    </div>
                  </div>
                ))}
                <div ref={messagesEndRef} />
              </>
            )}
            {sending && messages[messages.length - 1]?.role !== 'assistant' && (
              <div style={{ textAlign: 'center', padding: '20px' }}>
                <Spin tip="AI思考中..." />
              </div>
            )}
          </div>

          {/* 输入框：固定在卡片底部；检索权重条尽量压矮，把高度留给对话区 */}
          <div style={{ borderTop: '1px solid #f0f0f0', padding: '10px 16px 12px', flexShrink: 0 }}>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                marginBottom: 8,
              }}
            >
              <Text type="secondary" style={{ fontSize: 12, whiteSpace: 'nowrap' }}>
                检索权重
              </Text>
              <Text type="secondary" style={{ fontSize: 11, whiteSpace: 'nowrap' }}>
                BM25 {100 - vectorWeightPct}%
              </Text>
              <Slider
                min={0}
                max={100}
                step={5}
                value={vectorWeightPct}
                onChange={(v) => setVectorWeightPct(Number(v))}
                disabled={sending}
                tooltip={{ formatter: (v) => `语义 ${v}% / 关键词 ${100 - Number(v || 0)}%` }}
                style={{ flex: 1, margin: '0 4px' }}
              />
              <Text type="secondary" style={{ fontSize: 11, whiteSpace: 'nowrap' }}>
                语义 {vectorWeightPct}%
              </Text>
            </div>
            <Space.Compact style={{ width: '100%' }}>
              <TextArea
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onPressEnter={(e) => {
                  if (!e.shiftKey) {
                    e.preventDefault();
                    handleSendMessage();
                  }
                }}
                placeholder="输入你的问题... (Shift+Enter 换行)"
                autoSize={{ minRows: 1, maxRows: 4 }}
                disabled={sending}
                style={{ resize: 'none' }}
              />
              <Button
                type="primary"
                icon={<SendOutlined />}
                onClick={handleSendMessage}
                loading={sending}
                disabled={!inputValue.trim()}
              >
                发送
              </Button>
            </Space.Compact>
          </div>
        </Card>
      </Col>
    </Row>
  );
};

export default TabOne;
