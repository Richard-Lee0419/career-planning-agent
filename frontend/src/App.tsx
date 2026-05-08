import { useEffect, useMemo, useState } from 'react';
import { Navigate, Outlet, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import { BrowserRouter } from 'react-router-dom';
import { Avatar, Button, Drawer, Grid, Layout, Menu, Space, Typography } from 'antd';
import {
  AuditOutlined,
  DashboardOutlined,
  LogoutOutlined,
  MenuOutlined,
  MessageOutlined,
  NodeIndexOutlined,
  ReadOutlined,
  RadarChartOutlined,
  UserOutlined
} from '@ant-design/icons';
import { fetchCurrentUser } from './api/auth';
import { useAuthStore } from './store/authStore';
import Login from './views/Login';
import Dashboard from './views/Dashboard';
import ChatRoom from './views/ChatRoom';
import Interview from './views/Interview';
import Profile from './views/Profile';
import CareerAssessment from './views/CareerAssessment';
import Recommendations from './views/Recommendations';
import Roadmap from './views/Roadmap';

const { Header, Content } = Layout;
const PROJECT_NAME = '智引未来';

function ProtectedRoute() {
  const token = useAuthStore((state) => state.token);
  const location = useLocation();
  if (!token) return <Navigate to="/login" replace state={{ from: location, reason: 'auth_required' }} />;
  return <Outlet />;
}

function AppShell() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const account = useAuthStore((state) => state.account);
  const summary = useAuthStore((state) => state.userProfileSummary);
  const logout = useAuthStore((state) => state.logout);
  const setCurrentUser = useAuthStore((state) => state.setCurrentUser);
  const screens = Grid.useBreakpoint();
  const isMobile = !screens.lg;

  useEffect(() => {
    void fetchCurrentUser().then((response) => setCurrentUser(response.data));
  }, [setCurrentUser]);

  const selectedKey = useMemo(() => {
    if (location.pathname.startsWith('/chat')) return '/chat';
    if (location.pathname.startsWith('/assessment')) return '/assessment';
    if (location.pathname.startsWith('/recommendations')) return '/recommendations';
    if (location.pathname.startsWith('/roadmap')) return '/roadmap';
    if (location.pathname.startsWith('/interview')) return '/interview';
    if (location.pathname.startsWith('/profile')) return '/profile';
    return '/dashboard';
  }, [location.pathname]);

  const navItems = [
    { key: '/dashboard', icon: <DashboardOutlined />, label: '成长中心' },
    { key: '/assessment', icon: <RadarChartOutlined />, label: '职业测评' },
    { key: '/recommendations', icon: <AuditOutlined />, label: '职业推荐' },
    { key: '/roadmap', icon: <NodeIndexOutlined />, label: '学习路径' },
    { key: '/chat', icon: <MessageOutlined />, label: 'AI 顾问' },
    { key: '/interview', icon: <ReadOutlined />, label: '面试训练' }
  ];

  const goRoute = (key: string) => {
    navigate(key);
    setMobileMenuOpen(false);
  };

  const runLogout = () => {
    logout();
    navigate('/login', { replace: true });
  };

  return (
    <Layout className="app-shell">
      <Header className="app-header">
        <button className="brand-mark" type="button" onClick={() => goRoute('/dashboard')}>
          <span className="brand-symbol">智</span>
          <span className="brand-copy">
            <Typography.Text strong className="brand-title">
              {PROJECT_NAME}
            </Typography.Text>
            <span>AI 职业成长平台</span>
          </span>
        </button>

        {!isMobile && (
          <Menu
            className="top-nav-menu"
            mode="horizontal"
            selectedKeys={[selectedKey]}
            onClick={({ key }) => goRoute(key)}
            items={navItems}
          />
        )}

        <Space className="nav-actions" size={12}>
          <Avatar icon={<UserOutlined />} className="user-avatar" />
          <div className="header-user">
            <Typography.Text strong>{summary?.name || account?.username || '用户'}</Typography.Text>
            <span>{summary?.major || '职业探索中'}</span>
          </div>
          <Button className="logout-button" icon={<LogoutOutlined />} onClick={runLogout}>
            退出
          </Button>
          {isMobile && (
            <Button
              className="nav-menu-button"
              type="text"
              icon={<MenuOutlined />}
              onClick={() => setMobileMenuOpen(true)}
            />
          )}
        </Space>
      </Header>

      <Drawer
        className="mobile-nav-drawer"
        title={<span className="drawer-brand-title">{PROJECT_NAME}</span>}
        open={mobileMenuOpen}
        onClose={() => setMobileMenuOpen(false)}
        placement="right"
        width={300}
      >
        <Menu mode="inline" selectedKeys={[selectedKey]} onClick={({ key }) => goRoute(key)} items={navItems} />
      </Drawer>

      <Content className="app-content">
        <Outlet />
      </Content>
    </Layout>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route element={<ProtectedRoute />}>
          <Route element={<AppShell />}>
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/assessment" element={<CareerAssessment />} />
            <Route path="/recommendations" element={<Recommendations />} />
            <Route path="/roadmap" element={<Roadmap />} />
            <Route path="/chat" element={<ChatRoom />} />
            <Route path="/interview" element={<Interview />} />
            <Route path="/profile" element={<Profile />} />
          </Route>
        </Route>
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
