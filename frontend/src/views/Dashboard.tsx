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
  LineChartOutlined,
  MessageOutlined,
  ProfileOutlined,
  RiseOutlined,
  ThunderboltOutlined,
  TrophyOutlined
} from '@ant-design/icons';
import { fetchInterviewHistory } from '../api/interview';
import { fetchJobStats } from '../api/jobs';
import { fetchRecommendations } from '../api/recommendations';
import { fetchRoadmapHistory } from '../api/history';
import type { InterviewHistoryItem, JobStatsItem, RoadmapHistoryItem, RoleMatch } from '../api/types';
import { getErrorMessage } from '../api/client';
import { ChartCanvas } from '../components/ChartCanvas';
import { GrowthJourney } from '../components/GrowthJourney';
import { StandardSourceNote } from '../components/StandardSourceNote';
import { useProfile } from '../hooks/useProfile';
import { compactNumber } from '../utils/format';
import {
  getCareerRecommendations,
  getPrimaryTargetRole,
  getProfileGaps,
  getProfileStrengths,
  getTargetDomain,
  hasCareerProfile,
  roleNamesMatch
} from '../utils/careerPlan';

export default function Dashboard() {
  const navigate = useNavigate();
  const { profile, loading: profileLoading, error: profileError, reload: reloadProfile } = useProfile();
  const [jobStats, setJobStats] = useState<JobStatsItem[]>([]);
  const [roleMatches, setRoleMatches] = useState<RoleMatch[]>([]);
  const [interviews, setInterviews] = useState<InterviewHistoryItem[]>([]);
  const [roadmaps, setRoadmaps] = useState<RoadmapHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    async function loadDashboard() {
      setLoading(true);
      setError(null);
      const [statsResult, matchesResult, interviewResult, roadmapResult] = await Promise.allSettled([
        fetchJobStats(),
        fetchRecommendations(),
        fetchInterviewHistory(),
        fetchRoadmapHistory()
      ]);

      if (statsResult.status === 'fulfilled') setJobStats(statsResult.value.data);
      if (matchesResult.status === 'fulfilled') setRoleMatches(matchesResult.value.data);
      if (interviewResult.status === 'fulfilled') setInterviews(interviewResult.value.data);
      if (roadmapResult.status === 'fulfilled') setRoadmaps(roadmapResult.value.data);

      const rejected = [statsResult, matchesResult, interviewResult, roadmapResult].find(
        (result) => result.status === 'rejected'
      );
      if (rejected?.status === 'rejected') {
        setError(getErrorMessage(rejected.reason, '部分成长中心数据加载失败'));
      }
      setLoading(false);
    }

    void loadDashboard();
  }, [reloadKey]);

  const hasProfile = hasCareerProfile(profile);
  const primaryRole = getPrimaryTargetRole(profile);
  const recommendations = useMemo(() => getCareerRecommendations(profile, roleMatches), [roleMatches, profile]);
  const primaryMatch = roleMatches.find((item) => primaryRole && roleNamesMatch(item.role_name, primaryRole));
  const primaryDomain = getTargetDomain(profile, roleMatches.map((item) => ({ role_name: item.role_name, domain: item.domain || 'technology' })));
  const displayMatch = primaryRole ? primaryMatch?.score : recommendations[0]?.match;
  const strengths = useMemo(() => getProfileStrengths(profile), [profile]);
  const gaps = useMemo(() => getProfileGaps(profile), [profile]);

  const abilityScores = useMemo(
    () => [
      { name: '专业技能', value: profile?.current_skills.length || 0 },
      { name: '项目/实习经历', value: profile?.internship_experience ? 1 : 0 },
      { name: '职业目标', value: profile?.target_roles.length || 0 },
      { name: '软素质', value: profile?.soft_skills.length || 0 },
      { name: '证书奖项', value: profile?.certificates.length || 0 }
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
        minInterval: 1,
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
    hasProfile ? (primaryRole ? `围绕 ${primaryRole} 生成学习路径` : '先明确一个目标岗位') : '完成 AI 职业测评，建立第一版画像',
    gaps[0] || '补齐岗位关键技能',
    interviews.length ? '复盘最近一次模拟面试反馈' : '完成一次目标岗位模拟面试'
  ];
  const latestRoadmap = roadmaps[0];
  const currentRoadmap = primaryRole
    ? roadmaps.find((item) => roleNamesMatch(item.role_name, primaryRole))
    : null;
  const primaryAction = !hasProfile
    ? { label: '开始职业测评', path: '/assessment' }
    : currentRoadmap
      ? { label: '继续已保存的学习路径', path: `/roadmap?history_id=${currentRoadmap.id}` }
      : recommendations.length
        ? { label: '查看推荐方向', path: '/recommendations' }
        : { label: '完善职业画像', path: '/profile' };

  if (loading || profileLoading) {
    return <Skeleton active paragraph={{ rows: 14 }} />;
  }

  return (
    <div className="page-stack dashboard-home story-page">
      {(error || profileError) && <Alert type="warning" showIcon message={error || profileError}
        action={<Button onClick={() => { setReloadKey((current) => current + 1); void reloadProfile(); }}>重新加载</Button>} />}

      <section className="home-hero growth-center-hero">
        <div className="hero-copy">
          <Tag className="hero-kicker" icon={<ThunderboltOutlined />}>
            Career Growth Center
          </Tag>
          <Typography.Title>从现在，走向你的<span>目标岗位</span></Typography.Title>
          <Typography.Paragraph>
            先看清自己的能力与岗位差距，再把推荐方向变成可执行的学习任务。你的测评、路径和面试复盘会持续留在这条成长线上。
          </Typography.Paragraph>
          <Space className="hero-actions" wrap>
            <Button type="primary" size="large" icon={<ThunderboltOutlined />} onClick={() => navigate(primaryAction.path)}>
              {primaryAction.label}
            </Button>
            <Button size="large" icon={<CompassOutlined />} onClick={() => navigate('/recommendations')}>
              查看职业推荐依据
            </Button>
          </Space>
        </div>

        <div className="story-hero-facts" aria-label="当前成长概况">
          <div><span>{primaryRole ? '当前目标' : '推荐探索方向'}</span><strong>{primaryRole || recommendations[0]?.title || '待选择'}</strong></div>
          <div><span>岗位标准覆盖参考</span><strong>{displayMatch == null ? '证据待补充' : `${displayMatch}%`}</strong></div>
          <div><span>下一步</span><strong>{currentRoadmap ? '继续已保存路径' : hasProfile ? '选择推荐方向' : '完成职业测评'}</strong></div>
        </div>
      </section>

      <GrowthJourney />

      {!hasProfile && (
        <Card className="guided-empty-card" variant="borderless">
          <Empty description="还没有完整职业画像" />
          <Typography.Paragraph type="secondary">
            完成测评后，成长中心会根据真实画像与岗位标准展示匹配依据、能力差距和近期任务。
          </Typography.Paragraph>
          <Button type="primary" icon={<ExperimentOutlined />} onClick={() => navigate('/assessment')}>
            开始 AI 职业测评
          </Button>
        </Card>
      )}

      <Row gutter={[18, 18]}>
        <Col xs={24} md={12} xl={6}>
          <Card className="metric-card" variant="borderless">
            <Statistic title="当前职业目标" value={primaryRole || '尚未选择'} prefix={<ProfileOutlined />} />
            <Typography.Text type="secondary">可在测评中重新选择或更新目标</Typography.Text>
          </Card>
        </Col>
        <Col xs={24} md={12} xl={6}>
          <Card className="metric-card" variant="borderless">
            <Statistic
              title="目标岗位标准覆盖参考"
              value={displayMatch ?? '待补充'}
              suffix={displayMatch === null || displayMatch === undefined ? undefined : '%'}
              prefix={<TrophyOutlined />}
            />
            {displayMatch !== null && displayMatch !== undefined && <Progress
              percent={displayMatch}
              showInfo={false}
              strokeColor={{ '0%': '#5eead4', '100%': '#2563eb' }}
            />}
            <Typography.Text type="secondary">依据已填写能力，不代表录用概率或跨领域适合度。</Typography.Text>
          </Card>
        </Col>
        <Col xs={24} md={12} xl={6}>
          <Card className="metric-card" variant="borderless">
            <Statistic title="学习路径版本" value={compactNumber(roadmaps.length)} prefix={<BranchesOutlined />} />
            <Typography.Text type="secondary">{latestRoadmap?.role_name || '还没有生成学习路径'}</Typography.Text>
          </Card>
        </Col>
        <Col xs={24} md={12} xl={6}>
          <Card className="metric-card" variant="borderless">
            <Statistic title="面试复盘记录" value={compactNumber(interviews.length)} prefix={<RiseOutlined />} />
            <Typography.Text type="secondary">{interviews[0]?.question || '完成一次面试训练后会显示'}</Typography.Text>
          </Card>
        </Col>
      </Row>

      <section className="growth-story-grid">
        <Card title="我是谁：能力画像概览" variant="borderless" className="dashboard-panel profile-summary-card">
          <Space direction="vertical" size={16} className="full-width">
            <div className="profile-score-row">
              {displayMatch !== null && displayMatch !== undefined ? <Progress
                type="circle"
                percent={displayMatch}
                strokeColor={{ '0%': '#5eead4', '100%': '#2563eb' }}
              /> : <Typography.Text type="secondary">暂无匹配依据</Typography.Text>}
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
            {primaryMatch && <StandardSourceNote source={primaryMatch.standard_source} />}
          </Space>
        </Card>

        <Card
          title={
            <Space>
              <CompassOutlined />
              <span>同领域岗位与准备方向</span>
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
                {career.match !== null && <Progress percent={career.match} showInfo={false} strokeColor={{ '0%': '#5eead4', '100%': '#2563eb' }} />}
                <Space wrap>
                  <Tag color={career.match === null ? 'gold' : 'blue'}>{career.match === null ? '信息不足，暂不评分' : `${career.match}% 标准覆盖参考`}</Tag>
                  <Button type="link" onClick={() => navigate(`/roadmap?role=${encodeURIComponent(career.title)}`)}>
                    生成路径
                  </Button>
                </Space>
              </div>
            ))}
            {!recommendations.length && <Empty description="先明确目录内目标，或到探索页选择一个就业领域；暂不展示全领域排序。" />}
          </div>
          <div className="section-next-action">
            <Button type="primary" icon={<CompassOutlined />} onClick={() => navigate('/recommendations')}>
              查看完整推荐理由
            </Button>
          </div>
        </Card>

        <Card title="已记录的画像证据数量" variant="borderless" className="dashboard-panel chart-panel">
          <ChartCanvas option={abilityOption} className="dashboard-chart compact-chart" />
          <Space wrap>
            {gaps.slice(0, 4).map((gap) => (
              <Tag color="gold" key={gap}>
                {gap}
              </Tag>
            ))}
          </Space>
        </Card>

        <Card title="我该如何提升：建议行动" variant="borderless" className="dashboard-panel">
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
          <Card title={primaryDomain === 'technology' ? '历史岗位样本分布' : '岗位资料范围'} variant="borderless" className="dashboard-panel chart-panel">
            {primaryDomain === 'technology' ? <>
              <Typography.Paragraph type="secondary">原有企业材料中的历史样本，日期缺少完整年份；此分布不代表当前市场，也不适用于新增试点领域。</Typography.Paragraph>
              {jobStats.length ? <ChartCanvas option={pieOption} className="dashboard-chart" /> : <Empty description="暂无历史岗位样本" />}
            </> : <Typography.Paragraph type="secondary">市场与内容、人力资源目前仅提供少量能力标准试点，尚未接入可追溯招聘样本，不提供招聘热度或薪资统计。可到职业探索页选择领域、查看标准依据。</Typography.Paragraph>}
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
                    <Button type="link" onClick={() => navigate(`/roadmap?history_id=${item.id}`)} key="open">
                      回看版本
                    </Button>
                  ]}
                >
                  <List.Item.Meta title={item.role_name} description={item.created_at ? `保存于 ${new Date(item.created_at).toLocaleString()}` : '历史路径版本'} />
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
