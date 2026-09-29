import { lazy, Suspense, useEffect, useMemo, useState } from 'react';
import { Navigate, Outlet, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import { BrowserRouter } from 'react-router-dom';
import { Avatar, Button, Drawer, Grid, Layout, Menu, Space, Spin, Typography } from 'antd';
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
const Login = lazy(() => import('./views/Login'));
const Dashboard = lazy(() => import('./views/Dashboard'));
const ChatRoom = lazy(() => import('./views/ChatRoom'));
const Interview = lazy(() => import('./views/Interview'));
const Profile = lazy(() => import('./views/Profile'));
const CareerAssessment = lazy(() => import('./views/CareerAssessment'));
const Recommendations = lazy(() => import('./views/Recommendations'));
const Roadmap = lazy(() => import('./views/Roadmap'));

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
  const token = useAuthStore((state) => state.token);
  const setCurrentUser = useAuthStore((state) => state.setCurrentUser);
  const screens = Grid.useBreakpoint();
  const isMobile = !screens.lg;

  useEffect(() => {
    let active = true;
    void fetchCurrentUser()
      .then((response) => {
        if (active && useAuthStore.getState().token === token) setCurrentUser(response.data);
      })
      .catch(() => {
        // The response interceptor handles expired credentials.
      });
    return () => { active = false; };
  }, [setCurrentUser, token]);

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
          <img className="brand-symbol" src="/brand-mark.png" alt="" aria-hidden="true" />
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
        title={<span className="drawer-brand"><img src="/brand-mark.png" alt="" aria-hidden="true" /><span className="drawer-brand-title">{PROJECT_NAME}</span></span>}
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
      <Suspense fallback={<div className="center-spin"><Spin tip="页面加载中" size="large"><div style={{ minHeight: 120 }} /></Spin></div>}>
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
      </Suspense>
    </BrowserRouter>
  );
}
