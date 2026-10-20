import { useEffect, useState } from 'react';
import { Layout, Tabs, Avatar, Dropdown, message } from 'antd';
import { UserOutlined, LogoutOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { getUserInfo, logout as authLogout } from '@/utils/auth';
import TabOne from './TabOne';
import AgentTab from './AgentTab';

const { Header, Content } = Layout;

const Main = () => {
  const navigate = useNavigate();
  const userInfo = getUserInfo();
  const [activeKey, setActiveKey] = useState('1');
  // Agent Tab 挂载后保持不卸载，避免切走丢掉内存态对话
  const [agentMounted, setAgentMounted] = useState(false);

  useEffect(() => {
    if (activeKey === '2') {
      setAgentMounted(true);
    }
  }, [activeKey]);

  const handleLogout = () => {
    authLogout();
    message.success('已登出');
    navigate('/login');
  };

  const userMenuItems = [
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: '退出登录',
      onClick: handleLogout,
    },
  ];

  return (
    <Layout style={{ height: '100vh' }}>
      <Header style={{ 
        background: '#fff', 
        padding: '0 24px', 
        boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
      }}>
        <div style={{ fontSize: 20, fontWeight: 'bold', color: '#1890ff' }}>
          RAG智能助手
        </div>
        <Dropdown menu={{ items: userMenuItems }} placement="bottomRight">
          <div style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8 }}>
            <Avatar icon={<UserOutlined />} />
            <span>{userInfo?.username}</span>
          </div>
        </Dropdown>
      </Header>
      <Content
        style={{
          background: '#f0f2f5',
          height: 'calc(100vh - 64px)',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <Tabs
          activeKey={activeKey}
          onChange={setActiveKey}
          items={[
            { key: '1', label: '智能问答' },
            { key: '2', label: 'Agent' },
          ]}
          style={{ padding: '0 24px', flexShrink: 0 }}
          // 只使用 Tabs 做导航条，内容在下方独立渲染，避免子组件被卸载
          className="main-nav-tabs"
        />
        <div
          style={{
            flex: 1,
            minHeight: 0,
            overflow: 'hidden',
            display: activeKey === '1' ? 'block' : 'none',
            padding: '0 24px',
          }}
        >
          <TabOne />
        </div>
        {agentMounted && (
          <div
            style={{
              flex: 1,
              minHeight: 0,
              overflow: 'hidden',
              display: activeKey === '2' ? 'block' : 'none',
              padding: '0 24px',
            }}
          >
            <AgentTab />
          </div>
        )}
      </Content>
    </Layout>
  );
};

export default Main;
