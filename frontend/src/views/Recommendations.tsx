import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Alert, Button, Card, Empty, List, Progress, Skeleton, Space, Tag, Typography, message } from 'antd';
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
import type { JobItem } from '../api/types';
import { getErrorMessage } from '../api/client';
import { useProfile } from '../hooks/useProfile';
import {
  getCareerRecommendations,
  getPrimaryTargetRole,
  getProfileGaps,
  getProfileStrengths,
  hasCareerProfile
} from '../utils/careerPlan';

export default function Recommendations() {
  const navigate = useNavigate();
  const { profile, loading: profileLoading, error: profileError } = useProfile();
  const [jobs, setJobs] = useState<JobItem[]>([]);
  const [loadingJobs, setLoadingJobs] = useState(true);
  const [jobError, setJobError] = useState<string | null>(null);

  useEffect(() => {
    async function loadJobs() {
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
    }

    if (!profileLoading) void loadJobs();
  }, [profile, profileLoading]);

  const recommendations = useMemo(() => getCareerRecommendations(profile, jobs), [jobs, profile]);
  const strengths = useMemo(() => getProfileStrengths(profile), [profile]);
  const gaps = useMemo(() => getProfileGaps(profile), [profile]);
  const hasProfile = hasCareerProfile(profile);

  if (profileLoading) return <Skeleton active paragraph={{ rows: 12 }} />;

  if (!hasProfile) {
    return (
      <div className="page-stack">
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
    <div className="page-stack recommendations-page">
      {(profileError || jobError) && (
        <Alert
          type="warning"
          showIcon
          message={profileError || jobError}
          action={<Button onClick={() => message.info('请稍后刷新页面，或先基于当前画像继续生成职业推荐')}>显示加载失败处理建议</Button>}
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
            <Button type="primary" icon={<ThunderboltOutlined />} onClick={() => navigate(`/roadmap?role=${encodeURIComponent(recommendations[0]?.title || getPrimaryTargetRole(profile))}`)}>
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
            <strong>{recommendations[0]?.title || getPrimaryTargetRole(profile)}</strong>
          </div>
          <div>
            <span>AI 职业匹配度</span>
            <strong>{recommendations[0]?.match || profile?.competitiveness_score || 0}%</strong>
          </div>
          <div>
            <span>下一步建议</span>
            <strong>生成 12 周计划</strong>
          </div>
        </div>
      </section>

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
            {gaps.map((item) => (
              <Tag color="gold" key={item}>
                <ExclamationCircleOutlined /> {item}
              </Tag>
            ))}
          </Space>
        </Card>
      </section>

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
                <div className="job-match-ring">{Math.max(72, 94 - index * 4)}%</div>
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
