import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Alert, Button, Card, Col, Empty, List, Progress, Row, Skeleton, Space, Statistic, Tag, Typography } from 'antd';
import type { EChartsOption } from 'echarts';
import {
  ApiOutlined,
  BarChartOutlined,
  BranchesOutlined,
  CheckCircleOutlined,
  CompassOutlined,
  ExperimentOutlined,
  FundProjectionScreenOutlined,
  LineChartOutlined,
  MessageOutlined,
  ProfileOutlined,
  RiseOutlined,
  ThunderboltOutlined,
  TrophyOutlined
} from '@ant-design/icons';
import { fetchInterviewHistory } from '../api/interview';
import { fetchJobStats, fetchJobs } from '../api/jobs';
import { fetchRoadmapHistory } from '../api/history';
import type { InterviewHistoryItem, JobItem, JobStatsItem, RoadmapHistoryItem } from '../api/types';
import { getErrorMessage } from '../api/client';
import { ChartCanvas } from '../components/ChartCanvas';
import { useProfile } from '../hooks/useProfile';
import { compactNumber } from '../utils/format';
import {
  getCareerRecommendations,
  getPrimaryTargetRole,
  getProfileGaps,
  getProfileStrengths,
  hasCareerProfile
} from '../utils/careerPlan';

export default function Dashboard() {
  const navigate = useNavigate();
  const { profile, loading: profileLoading, error: profileError } = useProfile();
  const [jobStats, setJobStats] = useState<JobStatsItem[]>([]);
  const [jobs, setJobs] = useState<JobItem[]>([]);
  const [interviews, setInterviews] = useState<InterviewHistoryItem[]>([]);
  const [roadmaps, setRoadmaps] = useState<RoadmapHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadDashboard() {
      setLoading(true);
      setError(null);
      const [statsResult, jobsResult, interviewResult, roadmapResult] = await Promise.allSettled([
        fetchJobStats(),
        fetchJobs(6),
        fetchInterviewHistory(),
        fetchRoadmapHistory()
      ]);

      if (statsResult.status === 'fulfilled') setJobStats(statsResult.value.data);
      if (jobsResult.status === 'fulfilled') setJobs(jobsResult.value.data);
      if (interviewResult.status === 'fulfilled') setInterviews(interviewResult.value.data);
      if (roadmapResult.status === 'fulfilled') setRoadmaps(roadmapResult.value.data);

      const rejected = [statsResult, jobsResult, interviewResult, roadmapResult].find(
        (result) => result.status === 'rejected'
      );
      if (rejected?.status === 'rejected') {
        setError(getErrorMessage(rejected.reason, '部分成长中心数据加载失败'));
      }
      setLoading(false);
    }

    void loadDashboard();
  }, []);

  const hasProfile = hasCareerProfile(profile);
  const primaryRole = getPrimaryTargetRole(profile);
  const recommendations = useMemo(() => getCareerRecommendations(profile, jobs), [jobs, profile]);
  const strengths = useMemo(() => getProfileStrengths(profile), [profile]);
  const gaps = useMemo(() => getProfileGaps(profile), [profile]);

  const abilityScores = useMemo(
    () => [
      { name: '专业技能', value: Math.min((profile?.current_skills.length || 0) * 16, 100) },
      { name: '项目实践', value: profile?.internship_experience ? 82 : 32 },
      { name: '职业目标', value: Math.min((profile?.target_roles.length || 0) * 32, 100) },
      {
        name: '软素质',
        value: Math.min(((profile?.soft_skills.length || 0) + (profile?.interests.length || 0)) * 14, 100)
      },
      { name: '证书作品', value: Math.min((profile?.certificates.length || 0) * 22, 100) }
    ],
    [profile]
  );

  const pieOption = useMemo<EChartsOption>(
    () => ({
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'item',
        borderWidth: 0,
        backgroundColor: 'rgba(255,255,255,0.96)',
        textStyle: { color: '#10233f' }
      },
      legend: {
        bottom: 0,
        left: 'center',
        itemGap: 16,
        textStyle: { color: '#60748f', fontSize: 12 }
      },
      series: [
        {
          type: 'pie',
          radius: ['46%', '70%'],
          center: ['50%', '44%'],
          itemStyle: {
            borderRadius: 8,
            borderColor: '#fff',
            borderWidth: 3,
            shadowBlur: 18,
            shadowColor: 'rgba(37,99,235,0.16)'
          },
          label: { formatter: '{b}\n{d}%', color: '#10233f', fontWeight: 600 },
          data: jobStats
        }
      ],
      color: ['#1d4ed8', '#0ea5e9', '#14b8a6', '#6366f1', '#93c5fd', '#0f4bd8']
    }),
    [jobStats]
  );

  const abilityOption = useMemo<EChartsOption>(
    () => ({
      backgroundColor: 'transparent',
      grid: { left: 12, right: 18, top: 24, bottom: 10, containLabel: true },
      tooltip: {
        trigger: 'axis',
        borderWidth: 0,
        backgroundColor: 'rgba(255,255,255,0.96)',
        textStyle: { color: '#10233f' }
      },
      xAxis: {
        type: 'value',
        max: 100,
        splitLine: { lineStyle: { color: 'rgba(120,151,190,0.16)' } },
        axisLabel: { color: '#60748f' }
      },
      yAxis: {
        type: 'category',
        data: abilityScores.map((item) => item.name),
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { color: '#10233f', fontWeight: 600 }
      },
      series: [
        {
          type: 'bar',
          data: abilityScores.map((item) => item.value),
          barWidth: 14,
          showBackground: true,
          backgroundStyle: { color: 'rgba(37,99,235,0.08)', borderRadius: 8 },
          itemStyle: {
            borderRadius: 8,
            color: {
              type: 'linear',
              x: 0,
              y: 0,
              x2: 1,
              y2: 0,
              colorStops: [
                { offset: 0, color: '#5eead4' },
                { offset: 0.55, color: '#2563eb' },
                { offset: 1, color: '#1e40af' }
              ]
            }
          }
        }
      ]
    }),
    [abilityScores]
  );

  const nextTasks = [
    hasProfile ? `围绕 ${primaryRole} 生成未来 12 周学习路径` : '完成 AI 职业测评，建立第一版画像',
    gaps[0] || '补齐岗位关键技能',
    interviews.length ? '复盘最近一次模拟面试反馈' : '完成一次目标岗位模拟面试'
  ];

  if (loading || profileLoading) {
    return <Skeleton active paragraph={{ rows: 14 }} />;
  }

  return (
    <div className="page-stack dashboard-home">
      {(error || profileError) && <Alert type="warning" showIcon message={error || profileError} />}

      <section className="home-hero growth-center-hero">
        <div className="hero-copy">
          <Tag className="hero-kicker" icon={<ThunderboltOutlined />}>
            Career Growth Center
          </Tag>
          <Typography.Title>
            职业成长中心：
            <span>从画像到行动计划</span>
          </Typography.Title>
          <Typography.Paragraph>
            这里把你的职业测评、AI 推荐、学习路径、顾问对话和历史规划串成一条成长线，让你随时知道现在适合什么、缺什么、下一步做什么。
          </Typography.Paragraph>
          <Space className="hero-actions" wrap>
            <Button type="primary" size="large" icon={<ExperimentOutlined />} onClick={() => navigate('/assessment')}>
              开始 AI 职业测评
            </Button>
            <Button size="large" icon={<CompassOutlined />} onClick={() => navigate('/recommendations')}>
              查看推荐职业方向
            </Button>
            <Button size="large" icon={<FundProjectionScreenOutlined />} onClick={() => navigate(`/roadmap?role=${encodeURIComponent(primaryRole)}`)}>
              生成学习提升路径
            </Button>
          </Space>
        </div>

        <div className="growth-stage-panel" aria-label="职业成长路径">
          {['我是谁', '适合什么', '缺什么', '如何提升', '下一步'].map((step, index) => (
            <div className={`growth-stage-node ${index <= (hasProfile ? 2 : 0) ? 'is-active' : ''}`} key={step}>
              <span>{String(index + 1).padStart(2, '0')}</span>
              <strong>{step}</strong>
            </div>
          ))}
        </div>
      </section>

      {!hasProfile && (
        <Card className="guided-empty-card" variant="borderless">
          <Empty description="还没有完整职业画像" />
          <Typography.Paragraph type="secondary">
            当前推荐和路径只能使用默认样本。完成测评后，成长中心会展示你的目标岗位、匹配度、优势短板和近期任务。
          </Typography.Paragraph>
          <Button type="primary" icon={<ExperimentOutlined />} onClick={() => navigate('/assessment')}>
            开始 AI 职业测评
          </Button>
        </Card>
      )}

      <Row gutter={[18, 18]}>
        <Col xs={24} md={12} xl={6}>
          <Card className="metric-card" variant="borderless">
            <Statistic title="当前职业目标" value={primaryRole} prefix={<ProfileOutlined />} />
            <Typography.Text type="secondary">可在测评中重新选择或更新目标</Typography.Text>
          </Card>
        </Col>
        <Col xs={24} md={12} xl={6}>
          <Card className="metric-card" variant="borderless">
            <Statistic
              title="AI 职业匹配度"
              value={recommendations[0]?.match || profile?.competitiveness_score || 0}
              suffix="%"
              prefix={<TrophyOutlined />}
            />
            <Progress
              percent={recommendations[0]?.match || profile?.competitiveness_score || 0}
              showInfo={false}
              strokeColor={{ '0%': '#5eead4', '100%': '#2563eb' }}
            />
          </Card>
        </Col>
        <Col xs={24} md={12} xl={6}>
          <Card className="metric-card" variant="borderless">
            <Statistic title="近期学习任务" value={nextTasks.length} prefix={<BranchesOutlined />} />
            <Typography.Text type="secondary">{nextTasks[0]}</Typography.Text>
          </Card>
        </Col>
        <Col xs={24} md={12} xl={6}>
          <Card className="metric-card" variant="borderless">
            <Statistic title="历史规划记录" value={compactNumber(roadmaps.length)} prefix={<RiseOutlined />} />
            <Typography.Text type="secondary">{roadmaps[0]?.role_name || '暂无历史规划'}</Typography.Text>
          </Card>
        </Col>
      </Row>

      <section className="growth-story-grid">
        <Card title="我是谁：能力画像概览" variant="borderless" className="dashboard-panel profile-summary-card">
          <Space direction="vertical" size={16} className="full-width">
            <div className="profile-score-row">
              <Progress
                type="circle"
                percent={profile?.competitiveness_score || 0}
                strokeColor={{ '0%': '#5eead4', '100%': '#2563eb' }}
              />
              <div>
                <Typography.Title level={4}>{profile?.name || '未设置姓名'}</Typography.Title>
                <Typography.Text type="secondary">
                  {profile?.education_level || '学历待补充'} · {profile?.major || '专业待补充'}
                </Typography.Text>
                <div className="tag-cloud">
                  {strengths.map((item) => (
                    <Tag color="cyan" key={item}>
                      {item}
                    </Tag>
                  ))}
                </div>
              </div>
            </div>
            <Button icon={<ProfileOutlined />} onClick={() => navigate('/profile')}>
              完善个人画像资料
            </Button>
          </Space>
        </Card>

        <Card
          title={
            <Space>
              <CompassOutlined />
              <span>我适合什么：推荐职业方向</span>
            </Space>
          }
          variant="borderless"
          className="dashboard-panel"
        >
          <div className="career-path-grid">
            {recommendations.map((career) => (
              <div className="career-path-card" key={career.title}>
                <div>
                  <Typography.Text strong>{career.title}</Typography.Text>
                  <span>{career.subtitle}</span>
                </div>
                <Progress percent={career.match} showInfo={false} strokeColor={{ '0%': '#5eead4', '100%': '#2563eb' }} />
                <Space wrap>
                  <Tag color="blue">{career.match}% 匹配</Tag>
                  <Button type="link" onClick={() => navigate(`/roadmap?role=${encodeURIComponent(career.title)}`)}>
                    生成路径
                  </Button>
                </Space>
              </div>
            ))}
          </div>
          <div className="section-next-action">
            <Button type="primary" icon={<CompassOutlined />} onClick={() => navigate('/recommendations')}>
              查看完整推荐理由
            </Button>
          </div>
        </Card>

        <Card title="我缺什么：能力差距" variant="borderless" className="dashboard-panel chart-panel">
          <ChartCanvas option={abilityOption} className="dashboard-chart compact-chart" />
          <Space wrap>
            {gaps.slice(0, 4).map((gap) => (
              <Tag color="gold" key={gap}>
                {gap}
              </Tag>
            ))}
          </Space>
        </Card>

        <Card title="我该如何提升：近期行动计划" variant="borderless" className="dashboard-panel">
          <List
            dataSource={nextTasks}
            renderItem={(task, index) => (
              <List.Item
                actions={[
                  index === 0 ? (
                    <Button type="link" onClick={() => navigate(index === 0 && hasProfile ? `/roadmap?role=${encodeURIComponent(primaryRole)}` : '/assessment')}>
                      {hasProfile ? '生成计划' : '开始测评'}
                    </Button>
                  ) : null
                ]}
              >
                <List.Item.Meta
                  avatar={<CheckCircleOutlined className="list-positive-icon" />}
                  title={`行动 ${index + 1}`}
                  description={task}
                />
              </List.Item>
            )}
          />
        </Card>
      </section>

      <Row gutter={[18, 18]}>
        <Col xs={24} xl={10}>
          <Card title="岗位市场分布" variant="borderless" className="dashboard-panel chart-panel">
            {jobStats.length ? <ChartCanvas option={pieOption} className="dashboard-chart" /> : <Empty description="暂无岗位市场数据" />}
          </Card>
        </Col>
        <Col xs={24} xl={14}>
          <Card title="AI 顾问快捷入口" variant="borderless" className="advisor-card">
            <div className="advisor-layout">
              <div className="advisor-avatar">
                <ApiOutlined />
              </div>
              <div>
                <Typography.Title level={4}>带着当前画像继续追问</Typography.Title>
                <Typography.Paragraph>
                  AI 顾问会结合你的目标方向、优势短板和已生成路径，继续细化实习准备、项目选择、学习计划或面试表达。
                </Typography.Paragraph>
                <Space wrap>
                  <Button
                    type="primary"
                    icon={<MessageOutlined />}
                    onClick={() =>
                      navigate(`/chat?role=${encodeURIComponent(primaryRole)}&prompt=${encodeURIComponent('请结合我的职业画像，告诉我下一步最应该做什么。')}`)
                    }
                  >
                    继续咨询 AI 职业顾问
                  </Button>
                  <Button icon={<BarChartOutlined />} onClick={() => navigate('/interview')}>
                    进行目标岗位面试训练
                  </Button>
                </Space>
              </div>
            </div>
          </Card>
        </Col>
      </Row>

      <Card
        title={
          <Space>
            <LineChartOutlined />
            <span>历史测评 / 历史规划入口</span>
          </Space>
        }
        variant="borderless"
        className="dashboard-panel"
      >
        <Row gutter={[18, 18]}>
          <Col xs={24} lg={12}>
            <List
              header="最近规划记录"
              dataSource={roadmaps.slice(0, 4)}
              locale={{ emptyText: '暂无规划记录，先生成一条学习路径' }}
              renderItem={(item) => (
                <List.Item
                  actions={[
                    <Button type="link" onClick={() => navigate(`/roadmap?role=${encodeURIComponent(item.role_name)}`)} key="open">
                      回看并更新
                    </Button>
                  ]}
                >
                  <List.Item.Meta title={item.role_name} description="学习路径规划记录" />
                </List.Item>
              )}
            />
          </Col>
          <Col xs={24} lg={12}>
            <List
              header="最近面试复盘"
              dataSource={interviews.slice(0, 4)}
              locale={{ emptyText: '暂无面试复盘，完成一次模拟面试后会显示在这里' }}
              renderItem={(item) => (
                <List.Item>
                  <List.Item.Meta
                    title={
                      <Space>
                        <Tag color={item.score >= 80 ? 'green' : item.score >= 60 ? 'gold' : 'red'}>{item.score}</Tag>
                        <Typography.Text ellipsis>{item.question}</Typography.Text>
                      </Space>
                    }
                    description={item.improvement_suggestion}
                  />
                </List.Item>
              )}
            />
          </Col>
        </Row>
      </Card>
    </div>
  );
}
