import { useEffect, useRef, useState, type CSSProperties } from 'react';
import {
  Row,
  Col,
  Card,
  Input,
  Button,
  Space,
  Segmented,
  Tag,
  Typography,
  message,
  Empty,
} from 'antd';
import { SendOutlined, ClearOutlined } from '@ant-design/icons';
import {
  sendAgentQueryStream,
  getStoredAgentSessionId,
  saveAgentSessionId,
  clearStoredAgentSessionId,
  clearAgentSession,
  getStoredAgentMode,
  saveAgentMode,
  type AgentRunMode,
  type AgentLogEntry,
  type AgentStreamPhase,
} from '@/api/agent';

const { TextArea } = Input;
const { Text, Paragraph } = Typography;

interface ChatBubble {
  role: 'user' | 'assistant' | 'system';
  content: string;
}

const levelColor = (level: string): string => {
  switch ((level || '').toUpperCase()) {
    case 'ERROR':
      return '#cf1322';
    case 'WARN':
    case 'WARNING':
      return '#d48806';
    case 'DEBUG':
      return '#8c8c8c';
    default:
      return '#1677ff';
  }
};

const AgentTab = () => {
  const [mode, setMode] = useState<AgentRunMode>(() => getStoredAgentMode());
  const [sessionId, setSessionId] = useState(
    () => getStoredAgentSessionId() || '',
  );
  const [messages, setMessages] = useState<ChatBubble[]>([]);
  const [logs, setLogs] = useState<AgentLogEntry[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [sending, setSending] = useState(false);
  const [phase, setPhase] = useState<AgentStreamPhase | null>(null);
  const [resumeToken, setResumeToken] = useState<string | null>(null);

  const chatEndRef = useRef<HTMLDivElement>(null);
  const logEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  const handleModeChange = (value: string | number) => {
    const next = value === 'plan_execute' ? 'plan_execute' : 'react';
    if (sending) {
      message.warning('运行中请勿切换模式');
      return;
    }
    if (resumeToken) {
      message.info('已清除待补参状态，下一句按新模式开始');
      setResumeToken(null);
    }
    setMode(next);
    saveAgentMode(next);
  };

  const handleClearSession = async () => {
    const sid = sessionId;
    try {
      if (sid) {
        await clearAgentSession(sid);
      }
    } catch {
      // 拦截器已提示；仍继续清前端态
    }
    clearStoredAgentSessionId();
    setSessionId('');
    setMessages([]);
    setLogs([]);
    setResumeToken(null);
    setPhase(null);
    message.success('已清空 Agent 会话');
  };

  const appendLog = (entry: AgentLogEntry) => {
    setLogs((prev) => [
      ...prev,
      {
        level: entry.level || 'INFO',
        source: entry.source || 'runtime',
        message: entry.message || '',
        ts: entry.ts,
        step: entry.step,
        logger: entry.logger,
      },
    ]);
  };

  const handleSend = async () => {
    if (!inputValue.trim()) {
      message.warning('请输入内容');
      return;
    }
    if (sending) return;

    const text = inputValue.trim();
    const isResume = Boolean(resumeToken);

    setMessages((prev) => [...prev, { role: 'user', content: text }]);
    setInputValue('');
    setSending(true);
    setPhase('running');

    // 预留助手气泡（非 needs_input 时由 delta 填充）
    setMessages((prev) => [...prev, { role: 'assistant', content: '' }]);

    const usedResumeToken = resumeToken;
    if (isResume) {
      setResumeToken(null);
    }

    try {
      await sendAgentQueryStream(
        {
          query: text,
          session_id: sessionId || undefined,
          mode,
          ...(isResume && usedResumeToken
            ? { resume_token: usedResumeToken, answers: text }
            : {}),
        },
        {
          onMeta: ({ session_id }) => {
            if (session_id) {
              setSessionId(session_id);
              saveAgentSessionId(session_id);
            }
          },
          onStatus: ({ phase: p }) => setPhase(p),
          onLog: (entry) => appendLog(entry),
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
          onNeedsInput: ({ answer, resume_token, session_id }) => {
            if (session_id) {
              setSessionId(session_id);
              saveAgentSessionId(session_id);
            }
            if (resume_token) {
              setResumeToken(resume_token);
            }
            setMessages((prev) => {
              const next = [...prev];
              const last = next[next.length - 1];
              if (last?.role === 'assistant') {
                next[next.length - 1] = {
                  ...last,
                  content: answer || last.content || '还需要一些信息才能继续。',
                };
              }
              return next;
            });
            appendLog({
              level: 'INFO',
              source: 'runtime',
              message: '等待用户补参 (needs_input)',
            });
          },
          onDone: ({ answer, status, session_id }) => {
            if (session_id) {
              setSessionId(session_id);
              saveAgentSessionId(session_id);
            }
            setMessages((prev) => {
              const next = [...prev];
              const last = next[next.length - 1];
              if (last?.role === 'assistant') {
                const content =
                  last.content ||
                  answer ||
                  (status === 'needs_input' ? last.content : '（无回复）');
                next[next.length - 1] = { ...last, content };
                // 空助手气泡且无内容则去掉
                if (!next[next.length - 1].content) {
                  next.pop();
                }
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
            appendLog({
              level: 'ERROR',
              source: 'runtime',
              message: errMsg || '发送失败',
            });
            message.error(errMsg || '发送失败，请重试');
          },
        },
      );
    } catch {
      message.error('发送失败，请重试');
    } finally {
      setSending(false);
      setPhase(null);
    }
  };

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
    overflow: 'hidden',
    display: 'flex',
    flexDirection: 'column',
  };

  return (
    <div
      style={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        padding: '16px 0',
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          flexShrink: 0,
          marginBottom: 12,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 12,
          flexWrap: 'wrap',
        }}
      >
        <Space wrap>
          <Text strong>运行模式</Text>
          <Segmented
            value={mode}
            onChange={handleModeChange}
            options={[
              { label: 'ReAct', value: 'react' },
              { label: 'Plan-Execute', value: 'plan_execute' },
            ]}
            disabled={sending}
          />
          {phase && <Tag color="processing">{phase}</Tag>}
          {resumeToken && <Tag color="orange">待补参</Tag>}
          {sessionId && (
            <Text type="secondary" style={{ fontSize: 12 }}>
              session: {sessionId.slice(0, 12)}…
            </Text>
          )}
        </Space>
        <Button
          icon={<ClearOutlined />}
          onClick={() => void handleClearSession()}
          disabled={sending}
        >
          清空会话
        </Button>
      </div>

      <Row
        gutter={16}
        style={{
          flex: 1,
          minHeight: 0,
          overflow: 'hidden',
          flexWrap: 'nowrap',
          margin: 0,
        }}
      >
        <Col span={14} style={colStyle}>
          <Card
            title="对话"
            style={cardStyle}
            bodyStyle={cardBodyStyle}
          >
            <div style={{ flex: 1, minHeight: 0, overflow: 'auto', paddingRight: 4 }}>
              {messages.length === 0 ? (
                <Empty
                  description="Agent 与文档库隔离；左侧看回答，右侧看运行日志"
                  style={{ marginTop: 48 }}
                />
              ) : (
                messages.map((m, i) => (
                  <div
                    key={i}
                    style={{
                      marginBottom: 12,
                      display: 'flex',
                      justifyContent:
                        m.role === 'user' ? 'flex-end' : 'flex-start',
                    }}
                  >
                    <div
                      style={{
                        maxWidth: '85%',
                        padding: '10px 14px',
                        borderRadius: 8,
                        background:
                          m.role === 'user' ? '#1677ff' : '#f5f5f5',
                        color: m.role === 'user' ? '#fff' : '#262626',
                        whiteSpace: 'pre-wrap',
                        wordBreak: 'break-word',
                      }}
                    >
                      {m.content || (sending && i === messages.length - 1 ? '…' : '')}
                    </div>
                  </div>
                ))
              )}
              <div ref={chatEndRef} />
            </div>
            <div style={{ flexShrink: 0, marginTop: 12 }}>
              <Space.Compact style={{ width: '100%' }}>
                <TextArea
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  placeholder={
                    resumeToken
                      ? '请补充 Agent 所需信息后发送…'
                      : '输入问题，调用工具型 Agent…'
                  }
                  autoSize={{ minRows: 2, maxRows: 4 }}
                  onPressEnter={(e) => {
                    if (!e.shiftKey) {
                      e.preventDefault();
                      void handleSend();
                    }
                  }}
                  disabled={sending}
                />
                <Button
                  type="primary"
                  icon={<SendOutlined />}
                  loading={sending}
                  onClick={() => void handleSend()}
                  style={{ height: 'auto' }}
                >
                  发送
                </Button>
              </Space.Compact>
            </div>
          </Card>
        </Col>

        <Col span={10} style={colStyle}>
          <Card
            title="运行日志"
            extra={
              <Button
                type="link"
                size="small"
                onClick={() => setLogs([])}
                disabled={logs.length === 0}
              >
                清屏
              </Button>
            }
            style={cardStyle}
            bodyStyle={{ ...cardBodyStyle, background: '#1e1e1e', padding: 12 }}
          >
            <div
              style={{
                flex: 1,
                minHeight: 0,
                overflow: 'auto',
                fontFamily:
                  'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace',
                fontSize: 12,
                lineHeight: 1.55,
              }}
            >
              {logs.length === 0 ? (
                <Text style={{ color: '#8c8c8c' }}>等待运行日志…</Text>
              ) : (
                logs.map((log, i) => (
                  <div key={i} style={{ marginBottom: 6 }}>
                    <span style={{ color: levelColor(log.level) }}>
                      [{log.level}]
                    </span>{' '}
                    <span style={{ color: '#722ed1' }}>{log.source}</span>{' '}
                    <span style={{ color: '#d9d9d9' }}>{log.message}</span>
                  </div>
                ))
              )}
              <div ref={logEndRef} />
            </div>
            <Paragraph
              type="secondary"
              style={{ margin: '8px 0 0', fontSize: 11, color: '#8c8c8c' }}
            >
              工具 / 工具内 LLM 只出现在此栏，不会写入左侧气泡。
            </Paragraph>
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default AgentTab;
