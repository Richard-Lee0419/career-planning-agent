import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Alert, Button, Card, Empty, List, Progress, Select, Skeleton, Space, Tag, Typography } from 'antd';
import { ArrowRightOutlined, BranchesOutlined, CheckCircleOutlined, CompassOutlined, ExclamationCircleOutlined, FundProjectionScreenOutlined, RadarChartOutlined, ThunderboltOutlined } from '@ant-design/icons';
import { fetchJobs } from '../api/jobs';
import { fetchRecommendations } from '../api/recommendations';
import type { JobItem, RoleMatch } from '../api/types';
import { getErrorMessage } from '../api/client';
import { GrowthJourney } from '../components/GrowthJourney';
import { StandardSourceNote } from '../components/StandardSourceNote';
import { useProfile } from '../hooks/useProfile';
import { useCareerCatalog } from '../hooks/useCareerCatalog';
import { getCareerRecommendations, getPrimaryTargetRole, getProfileGaps, getProfileStrengths, getTargetDomain, hasCareerProfile, roleNamesMatch } from '../utils/careerPlan';

export default function Recommendations() {
  const navigate = useNavigate();
  const { profile, loading: profileLoading, error: profileError, reload: reloadProfile } = useProfile();
  const { catalog, loading: catalogLoading, error: catalogError, reload: reloadCatalog } = useCareerCatalog();
  const [selectedDomain, setSelectedDomain] = useState('');
  const [jobs, setJobs] = useState<JobItem[]>([]);
  const [loadingJobs, setLoadingJobs] = useState(false);
  const [jobError, setJobError] = useState<string | null>(null);
  const [roleMatches, setRoleMatches] = useState<RoleMatch[]>([]);
  const [matchError, setMatchError] = useState<string | null>(null);
  const [loadingMatches, setLoadingMatches] = useState(false);
  const matchRequest = useRef(0);
  const jobRequest = useRef(0);
  const activeDomain = catalog ? selectedDomain || getTargetDomain(profile, catalog.roles) : '';
  const domainLabel = catalog?.domains.find((domain) => domain.id === activeDomain)?.label || '';
  const targetRole = getPrimaryTargetRole(profile);
  const targetStandard = catalog?.roles.find((role) => roleNamesMatch(role.role_name, targetRole));
  const targetInDomain = Boolean(targetStandard && targetStandard.domain === activeDomain);

  const loadMatches = useCallback(async () => {
    const request = ++matchRequest.current;
    setRoleMatches([]);
    setMatchError(null);
    if (!activeDomain) {
      setLoadingMatches(false);
      return;
    }
    setLoadingMatches(true);
    try {
      const response = await fetchRecommendations(activeDomain);
      if (request === matchRequest.current) setRoleMatches(response.data);
    } catch (error) {
      if (request === matchRequest.current) setMatchError(getErrorMessage(error, '岗位标准覆盖依据加载失败'));
    } finally {
      if (request === matchRequest.current) setLoadingMatches(false);
    }
  }, [activeDomain]);

  const loadJobs = useCallback(async () => {
    const request = ++jobRequest.current;
    setJobs([]);
    setJobError(null);
    if (activeDomain !== 'technology') {
      setLoadingJobs(false);
      return;
    }
    setLoadingJobs(true);
    try {
      const response = await fetchJobs(8, targetInDomain ? targetRole : undefined);
      if (request === jobRequest.current) setJobs(response.data);
    } catch (error) {
      if (request === jobRequest.current) setJobError(getErrorMessage(error, '历史岗位样本加载失败'));
    } finally {
      if (request === jobRequest.current) setLoadingJobs(false);
    }
  }, [activeDomain, targetInDomain, targetRole]);

  useEffect(() => {
    if (!profileLoading && hasCareerProfile(profile)) {
      void loadMatches();
      void loadJobs();
    }
    return () => { matchRequest.current += 1; jobRequest.current += 1; };
  }, [loadJobs, loadMatches, profileLoading, profile]);

  const recommendations = useMemo(() => activeDomain ? getCareerRecommendations(profile, roleMatches, activeDomain) : [], [roleMatches, profile, activeDomain]);
  const strengths = useMemo(() => getProfileStrengths(profile), [profile]);
  const gaps = useMemo(() => getProfileGaps(profile), [profile]);
  const targetCard = recommendations.find((career) => roleNamesMatch(career.title, targetRole));
  const referenceCard = targetCard || recommendations[0];
  const visibleGaps = gaps.length ? gaps : referenceCard?.gaps || [];

  if (profileLoading) return <Skeleton active paragraph={{ rows: 12 }} />;
  if (!hasCareerProfile(profile)) return <div className="page-stack recommendations-page story-page">
    <GrowthJourney current="recommendations" />
    {profileError && <Alert type="error" showIcon message={profileError} action={<Button onClick={() => void reloadProfile()}>重新加载画像</Button>} />}
    <Card className="guided-empty-card" variant="borderless">
      <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="还没有足够的职业画像，暂时无法比较岗位标准" />
      <Typography.Paragraph type="secondary">先梳理真实能力和目标，系统再展示有依据的要求覆盖与差距。</Typography.Paragraph>
      <Button type="primary" icon={<RadarChartOutlined />} onClick={() => navigate('/assessment')}>开始 AI 职业测评</Button>
    </Card>
  </div>;

  return <div className="page-stack recommendations-page story-page">
    {profileError && <Alert type="warning" showIcon message={profileError} action={<Button onClick={() => void reloadProfile()}>重新加载画像</Button>} />}
    {catalogError && <Alert type="warning" showIcon message="职业目录暂时无法加载"
      description="当前无法核对支持的领域和岗位，暂不展示推荐排序。你的自填目标仍保留，可返回测评补充信息或重试目录。"
      action={<Button onClick={() => void reloadCatalog()}>重试目录</Button>} />}
    {matchError && <Alert type="warning" showIcon message={matchError} action={<Button onClick={() => void loadMatches()}>重试覆盖分析</Button>} />}

    <section className="module-hero recommendations-hero">
      <div>
        <Tag className="hero-kicker" icon={<CompassOutlined />}>Career Exploration</Tag>
        <Typography.Title>按就业领域探索岗位与能力差距</Typography.Title>
        <Typography.Paragraph>选择一个领域，查看已填能力覆盖了哪些岗位要求，以及下一步可以准备什么。覆盖参考不代表录用概率，不用于跨领域判断职业适合度。</Typography.Paragraph>
        <Space className="hero-actions" wrap>
          <Select size="large" className="career-domain-select" aria-label="探索领域" placeholder="先选择一个探索领域"
            loading={catalogLoading} disabled={!catalog} value={activeDomain || undefined}
            options={catalog?.domains.map((domain) => ({ value: domain.id, label: domain.label }))}
            onChange={(domain: string) => { setSelectedDomain(domain); setRoleMatches([]); }} />
          <Button type="primary" icon={<ThunderboltOutlined />} disabled={!referenceCard} onClick={() => referenceCard && navigate(`/roadmap?role=${encodeURIComponent(referenceCard.title)}`)}>为当前参考岗位生成路径</Button>
          <Button icon={<RadarChartOutlined />} onClick={() => navigate('/assessment')}>更新能力或目标</Button>
        </Space>
      </div>
      <div className="recommendation-summary-panel">
        <div><span>当前探索领域</span><strong>{domainLabel || '待选择'}</strong></div>
        <div><span>参考岗位</span><strong>{referenceCard?.title || (targetInDomain ? targetRole : '待选择')}</strong></div>
        <div><span>岗位标准覆盖参考</span><strong>{loadingMatches ? '计算中' : referenceCard?.match != null ? `${referenceCard.match}%` : '信息不足'}</strong></div>
      </div>
    </section>
    <GrowthJourney current="recommendations" />
    {catalog && <Alert type="info" showIcon message="如何阅读结果" description={catalog.scoring_note} />}
    {!catalogLoading && !catalogError && !activeDomain && <Alert type="info" showIcon message="请先选择一个领域"
      description="尚未识别到目标所属领域；不会把不同领域的覆盖分数排成统一的职业适合度榜单。" />}
    {catalog && targetRole && !targetStandard && <Alert type="info" showIcon message={`自填目标“${targetRole}”尚无岗位标准`}
      description="目标已保留，但暂不能计算覆盖参考。你可以选择领域查看现有岗位，或带着目标继续咨询 AI 顾问。" />}
    {catalog && targetStandard && activeDomain && !targetInDomain && <Alert type="info" showIcon
      message={`当前目标“${targetRole}”属于${targetStandard.domain_label}；下方只探索${domainLabel}岗位。`} />}
    {activeDomain && <section className="recommendation-insight-grid">
      <Card variant="borderless" title="已填写的能力证据"><Space wrap>{strengths.map((item) => <Tag color="cyan" key={item}><CheckCircleOutlined /> {item}</Tag>)}{!strengths.length && <Typography.Text type="secondary">尚未填写能力，请先更新画像。</Typography.Text>}</Space></Card>
      <Card variant="borderless" title="你的探索目标"><Typography.Paragraph>{profile?.target_roles?.length ? `你关注 ${profile.target_roles.join('、')}。请结合真实实践经历核对要求，再选择准备方向。` : '先选择一个主目标，或在当前领域浏览岗位任务。'}</Typography.Paragraph></Card>
      <Card variant="borderless" title="当前参考岗位的待补充项"><Space wrap>{visibleGaps.map((item) => <Tag color="gold" key={item}><ExclamationCircleOutlined /> {item}</Tag>)}{!visibleGaps.length && <Typography.Text type="secondary">请在目标岗位下进一步核对能力与经历。</Typography.Text>}</Space></Card>
    </section>}
    {loadingMatches && <Skeleton active paragraph={{ rows: 3 }} />}
    {activeDomain && !loadingMatches && !matchError && !recommendations.length && <Empty description="当前领域暂无可用岗位标准" />}
    <div className="recommendation-card-grid">
      {recommendations.map((career) => <Card className="recommendation-card" variant="borderless" key={career.title}>
        <div className="recommendation-card-header">
          <div><Tag color="blue">{roleNamesMatch(career.title, targetRole) ? '当前目标' : '同领域岗位'}</Tag><Typography.Title level={3}>{career.title}</Typography.Title><Typography.Text type="secondary">{career.subtitle}</Typography.Text></div>
          {career.match === null ? <Tag color="gold">信息不足</Tag> : <Progress type="circle" percent={career.match} size={88} strokeColor={{ '0%': '#5eead4', '100%': '#2563eb' }} />}
        </div>
        <div className="recommendation-section"><Typography.Text strong>覆盖与差距</Typography.Text><Typography.Paragraph>{career.reason}</Typography.Paragraph><Typography.Text type="secondary">{career.evidence}</Typography.Text></div>
        <StandardSourceNote source={career.standardSource} />
        <div className="recommendation-columns">
          <div><Typography.Text strong>已填写的相关依据</Typography.Text><List size="small" dataSource={career.fitReasons} renderItem={(item) => <List.Item><CheckCircleOutlined className="list-positive-icon" /><span>{item}</span></List.Item>} /></div>
          <div><Typography.Text strong>需要核对或补齐的能力</Typography.Text><List size="small" dataSource={career.gaps} renderItem={(item) => <List.Item><BranchesOutlined className="list-warning-icon" /><span>{item}</span></List.Item>} /></div>
        </div>
        <div className="recommendation-actions">
          <Button type="primary" icon={<FundProjectionScreenOutlined />} onClick={() => navigate(`/roadmap?role=${encodeURIComponent(career.title)}`)}>生成学习提升路径</Button>
          <Button icon={<CompassOutlined />} onClick={() => navigate(`/chat?role=${encodeURIComponent(career.title)}&prompt=${encodeURIComponent(`我想探索${career.title}方向，请结合我的真实能力、岗位标准范围和缺少的证据说明准备重点。`)}`)}>继续咨询 AI 职业顾问</Button>
        </div>
      </Card>)}
    </div>
    {activeDomain === 'technology' && <Card title="历史岗位样本（非实时招聘信息）" variant="borderless" loading={loadingJobs}>
      <Typography.Paragraph type="secondary">这些是原有企业材料中的岗位样本，发布时间缺少完整年份，不能据此判断当前招聘热度或薪资趋势，也不代表新增试点领域。</Typography.Paragraph>
      {jobError && <Alert type="warning" showIcon message={jobError} action={<Button onClick={() => void loadJobs()}>重试样本</Button>} />}
      {jobs.length ? <div className="job-card-grid">{jobs.slice(0, 4).map((job, index) => <div className="job-card" key={`${job.company}-${job.title}-${index}`}><div><Typography.Title level={4}>{job.title}</Typography.Title><Typography.Text>{job.company}</Typography.Text><div className="job-meta"><Tag>{job.location}</Tag><Tag color="blue">{job.salary_range || '未记录薪资'}</Tag></div></div></div>)}</div> : <Empty description="暂无对应历史岗位样本" />}
      <div className="section-next-action"><Button type="primary" icon={<ArrowRightOutlined />} onClick={() => navigate('/roadmap')}>进入学习路径规划</Button></div>
    </Card>}
    {activeDomain && activeDomain !== 'technology' && <Alert type="info" showIcon message="本领域尚未接入可追溯招聘样本"
      description="当前展示的是有限岗位能力标准试点，不提供招聘热度、薪资统计或岗位数量结论。" />}
  </div>;
}
