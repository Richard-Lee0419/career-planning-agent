import { useState } from 'react';
import { Alert, Button, Card, Form, Input, Space, Tag, Typography, message } from 'antd';
import {
  ArrowRightOutlined,
  CheckCircleOutlined,
  LockOutlined,
  RadarChartOutlined,
  SafetyCertificateOutlined,
  ThunderboltOutlined,
  UserOutlined
} from '@ant-design/icons';
import { useLocation, useNavigate } from 'react-router-dom';
import { fetchCurrentUser, login, register } from '../api/auth';
import { getErrorMessage } from '../api/client';
import { useAuthStore } from '../store/authStore';

const PROJECT_NAME = '智引未来';

interface LoginFormValues {
  username: string;
  password: string;
}

export default function Login() {
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const setToken = useAuthStore((state) => state.setToken);
  const setCurrentUser = useAuthStore((state) => state.setCurrentUser);
  const routeState = location.state as { from?: { pathname?: string; search?: string }; reason?: string } | null;

  const submit = async (values: LoginFormValues) => {
    setLoading(true);
    try {
      if (mode === 'register') {
        await register(values.username, values.password);
        message.success('注册成功，已为你登录');
      }
      const auth = await login(values.username, values.password);
      setToken(auth.access_token);
      const current = await fetchCurrentUser();
      setCurrentUser(current.data);
      const fromPath = routeState?.from?.pathname
        ? `${routeState.from.pathname}${routeState.from.search || ''}`
        : mode === 'register'
          ? '/assessment'
          : '/dashboard';
      navigate(fromPath, { replace: true });
    } catch (error) {
      message.error(getErrorMessage(error, mode === 'login' ? '登录失败' : '注册失败'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <section className="login-art">
        <div className="login-grid-bg" />
        <div className="career-route-visual" aria-hidden="true">
          <div className="route-glow" />
          <div className="route-node route-node-a" />
          <div className="route-node route-node-b" />
          <div className="route-node route-node-c" />
          <div className="route-panel route-panel-a" />
          <div className="route-panel route-panel-b" />
          <div className="route-panel route-panel-c" />
          <i className="route-link route-link-a" />
          <i className="route-link route-link-b" />
          <i className="route-link route-link-c" />
        </div>
        <div className="login-aurora aurora-a" />
        <div className="login-aurora aurora-b" />
        <div className="login-art-content">
          <Tag className="hero-kicker" icon={<ThunderboltOutlined />}>
            AI Career Coach
          </Tag>
          <Typography.Title className="login-brand-title">{PROJECT_NAME}</Typography.Title>
          <Typography.Paragraph>
            AI 职业规划平台：从职业测评开始，生成个人画像、
            <br />
            推荐方向、学习路径和可持续追踪的成长计划。
          </Typography.Paragraph>
          <div className="login-visual-panel">
            <div>
              <span>AI 匹配度</span>
              <strong>92%</strong>
            </div>
            <div className="mini-bars">
              <i />
              <i />
              <i />
              <i />
            </div>
            <div className="mini-route">
              <span />
              <span />
              <span />
              <span />
            </div>
          </div>
          <div className="login-metrics">
            <div>
              <RadarChartOutlined />
              <strong>4D</strong>
              <span>能力画像</span>
            </div>
            <div>
              <SafetyCertificateOutlined />
              <strong>AI</strong>
              <span>职业教练</span>
            </div>
            <div>
              <CheckCircleOutlined />
              <strong>100</strong>
              <span>成长评分</span>
            </div>
          </div>
        </div>
      </section>
      <Card className="login-card" variant="borderless">
        <div className="login-card-heading">
          <Tag className="gradient-tag">{mode === 'login' ? 'Welcome back' : 'Create account'}</Tag>
          <Typography.Title level={3}>{mode === 'login' ? '登录职业成长中心' : '创建账号并开始职业测评'}</Typography.Title>
          <Typography.Text type="secondary">
            {mode === 'login' ? '回到你的职业画像、推荐结果和学习计划' : '注册后自动登录，并进入 AI 职业测评流程'}
          </Typography.Text>
        </div>
        {routeState?.reason === 'auth_required' && (
          <Alert
            className="login-auth-alert"
            type="info"
            showIcon
            message="请先登录"
            description="登录后会继续打开你刚才选择的职业规划功能。"
          />
        )}
        <Form layout="vertical" className="login-form" onFinish={submit} requiredMark={false}>
          <Form.Item name="username" label="用户名" rules={[{ required: true, message: '请输入用户名' }]}>
            <Input size="large" prefix={<UserOutlined />} placeholder="username" autoComplete="username" />
          </Form.Item>
          <Form.Item name="password" label="密码" rules={[{ required: true, message: '请输入密码' }]}>
            <Input.Password
              size="large"
              prefix={<LockOutlined />}
              placeholder="password"
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
            />
          </Form.Item>
          <Button block size="large" type="primary" htmlType="submit" loading={loading}>
            <Space>
              <span>{mode === 'login' ? '进入职业成长中心' : '注册并开始 AI 职业测评'}</span>
              <ArrowRightOutlined />
            </Space>
          </Button>
        </Form>
        <Button
          type="link"
          block
          onClick={() => setMode((current) => (current === 'login' ? 'register' : 'login'))}
        >
          {mode === 'login' ? '第一次使用，创建职业规划账号' : '已有账号，返回登录职业成长中心'}
        </Button>
      </Card>
    </div>
  );
}
