import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Alert, Button, Card, Empty, List, Progress, Skeleton, Space, Tag, Typography } from 'antd';
import {
  ArrowRightOutlined,
  BranchesOutlined,
  CheckCircleOutlined,
  CompassOutlined,
  ExclamationCircleOutlined,
  FundProjectionScreenOutlined,
  RadarChartOutlined,
  ThunderboltOutlined
} from '@ant-design/icons';
import { fetchJobs } from '../api/jobs';
import { fetchRecommendations } from '../api/recommendations';
import type { JobItem, RoleMatch } from '../api/types';
import { getErrorMessage } from '../api/client';
import { GrowthJourney } from '../components/GrowthJourney';
import { useProfile } from '../hooks/useProfile';
import {
  getCareerRecommendations,
  getPrimaryTargetRole,
  getProfileGaps,
  getProfileStrengths,
  hasCareerProfile,
  roleNamesMatch
} from '../utils/careerPlan';

export default function Recommendations() {
  const navigate = useNavigate();
  const { profile, loading: profileLoading, error: profileError, reload: reloadProfile } = useProfile();
  const [jobs, setJobs] = useState<JobItem[]>([]);
  const [loadingJobs, setLoadingJobs] = useState(true);
  const [jobError, setJobError] = useState<string | null>(null);
  const [roleMatches, setRoleMatches] = useState<RoleMatch[]>([]);
  const [matchError, setMatchError] = useState<string | null>(null);
  const [loadingMatches, setLoadingMatches] = useState(true);

  const loadJobs = useCallback(async () => {
    setLoadingJobs(true);
    setJobError(null);
    try {
      const response = await fetchJobs(8, getPrimaryTargetRole(profile, undefined));
      setJobs(response.data);
    } catch (error) {
      setJobError(getErrorMessage(error, '岗位样本加载失败'));
    } finally {
      setLoadingJobs(false);
    }
  }, [profile]);

  const loadMatches = useCallback(async () => {
    setLoadingMatches(true);
    setMatchError(null);
    try {
      setRoleMatches((await fetchRecommendations()).data);
    } catch (error) {
      setMatchError(getErrorMessage(error, '岗位匹配依据加载失败'));
    } finally {
      setLoadingMatches(false);
    }
  }, []);

  useEffect(() => {
    if (!profileLoading) {
      void loadJobs();
      void loadMatches();
    }
  }, [loadJobs, loadMatches, profileLoading]);

  const recommendations = useMemo(() => getCareerRecommendations(profile, roleMatches), [roleMatches, profile]);
  const strengths = useMemo(() => getProfileStrengths(profile), [profile]);
  const gaps = useMemo(() => getProfileGaps(profile), [profile]);
  const visibleGaps = gaps.length ? gaps : recommendations[0]?.gaps || [];
  const hasProfile = hasCareerProfile(profile);
  const targetRole = getPrimaryTargetRole(profile);
  const targetHasStandard = !targetRole || roleMatches.some((item) => roleNamesMatch(item.role_name, targetRole));

  if (profileLoading) return <Skeleton active paragraph={{ rows: 12 }} />;

  if (!hasProfile) {
    return (
      <div className="page-stack recommendations-page story-page">
        <GrowthJourney current="recommendations" />
        {profileError && (
          <Alert type="error" showIcon message={profileError} action={<Button onClick={() => void reloadProfile()}>重新加载画像</Button>} />
        )}
        <Card className="guided-empty-card" variant="borderless">
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="还没有足够的职业画像，暂时无法生成可靠推荐"
          />
          <Typography.Paragraph type="secondary">
            先完成 AI 职业测评，系统会根据你的专业、兴趣、能力和目标生成职业画像，再给出推荐理由和学习路径。
          </Typography.Paragraph>
          <Button type="primary" icon={<RadarChartOutlined />} onClick={() => navigate('/assessment')}>
            开始 AI 职业测评
          </Button>
        </Card>
      </div>
    );
  }

  return (
    <div className="page-stack recommendations-page story-page">
      {(profileError || jobError || matchError) && (
        <Alert
          type="warning"
          showIcon
          message={profileError || matchError || jobError}
          action={<Button onClick={() => void (profileError ? reloadProfile() : matchError ? loadMatches() : loadJobs())}>重新加载</Button>}
        />
      )}
      {!loadingMatches && !matchError && !targetHasStandard && (
        <Alert type="info" showIcon
          message={`目标岗位“${targetRole}”暂无标准画像，暂时无法计算该岗位的综合匹配度；下方展示的是其他有岗位标准的方向。`}
        />
      )}

      <section className="module-hero recommendations-hero">
        <div>
          <Tag className="hero-kicker" icon={<CompassOutlined />}>
            Career Recommendations
          </Tag>
          <Typography.Title>基于你当前能力的职业推荐</Typography.Title>
          <Typography.Paragraph>
            推荐结果会解释“为什么适合你、还缺什么、下一步做什么”，避免只给岗位名称。你可以直接进入学习路径或继续咨询 AI 顾问。
          </Typography.Paragraph>
          <Space className="hero-actions" wrap>
            <Button type="primary" icon={<ThunderboltOutlined />} disabled={!recommendations.length} onClick={() => navigate(`/roadmap?role=${encodeURIComponent(recommendations[0].title)}`)}>
              为最推荐方向生成学习路径
            </Button>
            <Button icon={<RadarChartOutlined />} onClick={() => navigate('/assessment')}>
              重新测评或更新目标
            </Button>
          </Space>
        </div>
        <div className="recommendation-summary-panel">
          <div>
            <span>最高匹配方向</span>
            <strong>{recommendations[0]?.title || '暂无可计算方向'}</strong>
          </div>
          <div>
            <span>综合匹配度</span>
            <strong>{loadingMatches ? '计算中' : recommendations[0] ? `${recommendations[0].match}%` : '证据不足'}</strong>
          </div>
          <div>
            <span>下一步建议</span>
            <strong>生成阶段计划</strong>
          </div>
        </div>
      </section>

      <GrowthJourney current="recommendations" />

      <section className="recommendation-insight-grid">
        <Card variant="borderless" title="你的核心优势">
          <Space wrap>
            {strengths.map((item) => (
              <Tag color="cyan" key={item}>
                <CheckCircleOutlined /> {item}
              </Tag>
            ))}
          </Space>
        </Card>
        <Card variant="borderless" title="你的职业倾向">
          <Typography.Paragraph>
            {profile?.target_roles?.length
              ? `你当前最关注 ${profile.target_roles.join('、')}，推荐优先验证最高匹配方向，再保留 1 个备选路径。`
              : '当前职业目标还不够明确，建议先选择 1 个主方向，再通过 AI 顾问做岗位验证。'}
          </Typography.Paragraph>
        </Card>
        <Card variant="borderless" title="需要补齐的能力">
          <Space wrap>
            {visibleGaps.map((item) => (
              <Tag color="gold" key={item}>
                <ExclamationCircleOutlined /> {item}
              </Tag>
            ))}
            {!visibleGaps.length && <Typography.Text type="secondary">暂无明确差距，可在目标岗位下进一步分析。</Typography.Text>}
          </Space>
        </Card>
      </section>

      {loadingMatches && <Skeleton active paragraph={{ rows: 3 }} />}
      {!loadingMatches && !recommendations.length && <Empty description="岗位标准或能力证据不足，暂时无法计算综合匹配度" />}
      <div className="recommendation-card-grid">
        {recommendations.map((career, index) => (
          <Card className="recommendation-card" variant="borderless" key={career.title}>
            <div className="recommendation-card-header">
              <div>
                <Tag color={index === 0 ? 'blue' : 'cyan'}>{index === 0 ? '最推荐方向' : '备选方向'}</Tag>
                <Typography.Title level={3}>{career.title}</Typography.Title>
                <Typography.Text type="secondary">{career.subtitle}</Typography.Text>
              </div>
              <Progress
                type="circle"
                percent={career.match}
                size={88}
                strokeColor={{ '0%': '#5eead4', '100%': '#2563eb' }}
              />
            </div>

            <div className="recommendation-section">
              <Typography.Text strong>推荐理由</Typography.Text>
              <Typography.Paragraph>{career.reason}</Typography.Paragraph>
              <Typography.Text type="secondary">{career.evidence}</Typography.Text>
            </div>

            <div className="recommendation-columns">
              <div>
                <Typography.Text strong>适合你的原因</Typography.Text>
                <List
                  size="small"
                  dataSource={career.fitReasons}
                  renderItem={(item) => (
                    <List.Item>
                      <CheckCircleOutlined className="list-positive-icon" />
                      <span>{item}</span>
                    </List.Item>
                  )}
                />
              </div>
              <div>
                <Typography.Text strong>需要补齐的能力</Typography.Text>
                <List
                  size="small"
                  dataSource={career.gaps}
                  renderItem={(item) => (
                    <List.Item>
                      <BranchesOutlined className="list-warning-icon" />
                      <span>{item}</span>
                    </List.Item>
                  )}
                />
              </div>
            </div>

            <div className="recommendation-actions">
              <Button
                type="primary"
                icon={<FundProjectionScreenOutlined />}
                onClick={() => navigate(`/roadmap?role=${encodeURIComponent(career.title)}`)}
              >
                生成学习提升路径
              </Button>
              <Button
                icon={<CompassOutlined />}
                onClick={() =>
                  navigate(`/chat?role=${encodeURIComponent(career.title)}&prompt=${encodeURIComponent(`我想深入了解${career.title}方向，请结合我的职业画像说明适配度和准备重点。`)}`)
                }
              >
                继续咨询 AI 职业顾问
              </Button>
            </div>
          </Card>
        ))}
      </div>

      <Card
        title={
          <Space>
            <FundProjectionScreenOutlined />
            <span>岗位样本与市场信号</span>
          </Space>
        }
        variant="borderless"
        loading={loadingJobs}
      >
        {jobs.length ? (
          <div className="job-card-grid">
            {jobs.slice(0, 4).map((job, index) => (
              <div className="job-card" key={`${job.company}-${job.title}-${index}`}>
                <div className="job-match-ring">{(() => {
                  const score = roleMatches.find((item) => roleNamesMatch(item.role_name, job.title))?.score;
                  return score === null || score === undefined ? '—' : `${score}%`;
                })()}</div>
                <div>
                  <Typography.Title level={4}>{job.title}</Typography.Title>
                  <Typography.Text>{job.company}</Typography.Text>
                  <div className="job-meta">
                    <Tag>{job.location}</Tag>
                    <Tag color="blue">{job.salary_range || '薪资面议'}</Tag>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <Empty description="暂无岗位样本，仍可先基于画像生成职业方向" />
        )}
        <div className="section-next-action">
          <Button type="primary" icon={<ArrowRightOutlined />} onClick={() => navigate('/roadmap')}>
            进入学习路径规划
          </Button>
        </div>
      </Card>
    </div>
  );
}
