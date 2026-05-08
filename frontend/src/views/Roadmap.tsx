import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Alert, Button, Card, Checkbox, Empty, Input, Progress, Skeleton, Space, Tag, Timeline, Typography, message } from 'antd';
import {
  ArrowRightOutlined,
  CheckCircleOutlined,
  DownloadOutlined,
  FieldTimeOutlined,
  FundProjectionScreenOutlined,
  ReloadOutlined,
  ThunderboltOutlined
} from '@ant-design/icons';
import { exportReport, fetchLearningPath } from '../api/agent';
import { getErrorMessage } from '../api/client';
import type { LearningMilestone, LearningPathResponse } from '../api/types';
import { useProfile } from '../hooks/useProfile';
import { downloadBlob } from '../utils/download';
import { getPrimaryTargetRole } from '../utils/careerPlan';

function getStageName(index: number) {
  if (index === 0) return '短期：建立基础';
  if (index === 1) return '中期：形成作品';
  return '长期：冲刺岗位';
}

function getTaskKey(role: string, phase: string, task: string) {
  return `${role}::${phase}::${task}`;
}

function RoadmapPhaseCard({
  role,
  milestone,
  index,
  completed,
  onToggle
}: {
  role: string;
  milestone: LearningMilestone;
  index: number;
  completed: Record<string, boolean>;
  onToggle: (key: string, checked: boolean) => void;
}) {
  const tasks = milestone.focus_targets.length ? milestone.focus_targets : ['明确阶段目标', '完成关键练习', '形成可展示证据'];
  const doneCount = tasks.filter((task) => completed[getTaskKey(role, milestone.phase, task)]).length;
  const percent = Math.round((doneCount / tasks.length) * 100);

  return (
    <Card className="roadmap-phase-card" variant="borderless">
      <div className="roadmap-phase-header">
        <div>
          <Tag color={index === 0 ? 'blue' : index === 1 ? 'cyan' : 'purple'}>{getStageName(index)}</Tag>
          <Typography.Title level={4}>{milestone.phase}</Typography.Title>
          <Typography.Text type="secondary">{milestone.period}</Typography.Text>
        </div>
        <Progress type="circle" percent={percent} size={76} strokeColor={{ '0%': '#5eead4', '100%': '#2563eb' }} />
      </div>

      <div className="roadmap-block">
        <Typography.Text strong>学习目标</Typography.Text>
        <Typography.Paragraph>{tasks.join('、')}</Typography.Paragraph>
      </div>

      <div className="roadmap-task-list">
        <Typography.Text strong>关键任务</Typography.Text>
        {tasks.map((task) => {
          const key = getTaskKey(role, milestone.phase, task);
          return (
            <Checkbox key={key} checked={Boolean(completed[key])} onChange={(event) => onToggle(key, event.target.checked)}>
              {task}
            </Checkbox>
          );
        })}
      </div>

      <div className="roadmap-resource-list">
        <Typography.Text strong>推荐资源</Typography.Text>
        <Space wrap>
          {(milestone.recommended_resources.length ? milestone.recommended_resources : ['官方文档', '实战项目', '模拟面试']).map((resource) => (
            <Tag className="gradient-tag" key={resource}>
              {resource}
            </Tag>
          ))}
        </Space>
      </div>
    </Card>
  );
}

export default function Roadmap() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { profile, loading: profileLoading } = useProfile();
  const queryRole = searchParams.get('role') || '';
  const [targetRole, setTargetRole] = useState(queryRole);
  const [roadmap, setRoadmap] = useState<LearningPathResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [completed, setCompleted] = useState<Record<string, boolean>>({});

  useEffect(() => {
    const raw = localStorage.getItem('career-roadmap-completed');
    if (!raw) return;
    try {
      setCompleted(JSON.parse(raw) as Record<string, boolean>);
    } catch {
      localStorage.removeItem('career-roadmap-completed');
    }
  }, []);

  useEffect(() => {
    if (!profileLoading && !targetRole) {
      setTargetRole(getPrimaryTargetRole(profile));
    }
  }, [profile, profileLoading, targetRole]);

  const activeRole = targetRole.trim() || getPrimaryTargetRole(profile);

  const completionPercent = useMemo(() => {
    const tasks =
      roadmap?.milestones.flatMap((milestone) =>
        (milestone.focus_targets.length ? milestone.focus_targets : ['明确阶段目标']).map((task) =>
          getTaskKey(roadmap.target_role, milestone.phase, task)
        )
      ) || [];
    if (!tasks.length) return 0;
    return Math.round((tasks.filter((task) => completed[task]).length / tasks.length) * 100);
  }, [completed, roadmap]);

  const loadRoadmap = async (role = activeRole) => {
    if (!role.trim()) return message.warning('请先填写目标职业方向');
    setLoading(true);
    setError(null);
    setSearchParams({ role: role.trim() });
    try {
      const data = await fetchLearningPath(role.trim());
      setRoadmap(data);
      message.success('未来 12 周能力提升计划已生成');
    } catch (requestError) {
      setError(getErrorMessage(requestError, '学习路径生成失败'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (queryRole) void loadRoadmap(queryRole);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [queryRole]);

  const toggleTask = (key: string, checked: boolean) => {
    setCompleted((current) => {
      const next = { ...current, [key]: checked };
      localStorage.setItem('career-roadmap-completed', JSON.stringify(next));
      return next;
    });
  };

  const runExport = async () => {
    if (!activeRole) return message.warning('请先填写目标职业方向');
    setExporting(true);
    try {
      const report = await exportReport(activeRole);
      downloadBlob(report.blob, report.filename);
      message.success('本次规划结果已保存为报告');
    } catch (requestError) {
      message.error(getErrorMessage(requestError, '规划结果保存失败'));
    } finally {
      setExporting(false);
    }
  };

  if (profileLoading) return <Skeleton active paragraph={{ rows: 10 }} />;

  return (
    <div className="page-stack roadmap-page">
      <section className="module-hero roadmap-hero">
        <div>
          <Tag className="hero-kicker" icon={<FundProjectionScreenOutlined />}>
            Learning Roadmap
          </Tag>
          <Typography.Title>未来 12 周能力提升计划</Typography.Title>
          <Typography.Paragraph>
            将职业推荐转化为短期、中期、长期阶段任务。你可以标记完成状态、保存规划结果，并随时带着当前画像继续咨询 AI 顾问。
          </Typography.Paragraph>
          <Space className="hero-actions" wrap>
            <Input
              className="roadmap-role-input"
              size="large"
              value={targetRole}
              onChange={(event) => setTargetRole(event.target.value)}
              placeholder="输入目标职业，例如：产品经理"
              disabled={loading}
            />
            <Button type="primary" size="large" icon={<ThunderboltOutlined />} loading={loading} onClick={() => void loadRoadmap()}>
              生成未来 12 周学习路径
            </Button>
          </Space>
        </div>
        <div className="module-hero-stats">
          <div>
            <span>当前目标</span>
            <strong>{activeRole}</strong>
          </div>
          <div>
            <span>任务进度</span>
            <strong>{completionPercent}%</strong>
          </div>
          <div>
            <span>下一步</span>
            <strong>执行任务</strong>
          </div>
        </div>
      </section>

      {error && (
        <Alert
          type="error"
          showIcon
          message={error}
          action={
            <Button icon={<ReloadOutlined />} onClick={() => void loadRoadmap()}>
              重新生成学习路径
            </Button>
          }
        />
      )}

      {!roadmap && !loading && (
        <Card className="guided-empty-card" variant="borderless">
          <Empty description="还没有生成学习路径" />
          <Typography.Paragraph type="secondary">
            从职业推荐页进入，或在这里输入目标岗位，AI 会生成可执行的阶段任务和推荐资源。
          </Typography.Paragraph>
          <Button type="primary" icon={<ThunderboltOutlined />} onClick={() => void loadRoadmap()}>
            生成我的学习提升路径
          </Button>
        </Card>
      )}

      {loading && (
        <Card className="guided-empty-card" variant="borderless">
          <ThunderboltOutlined className="loading-hero-icon" />
          <Typography.Title level={4}>正在生成你的阶段任务、推荐资源与下一步行动</Typography.Title>
          <Progress percent={66} status="active" showInfo={false} />
        </Card>
      )}

      {roadmap && !loading && (
        <>
          <Card className="roadmap-summary-card" variant="borderless">
            <div className="roadmap-summary-layout">
              <div>
                <Tag className="gradient-tag">{roadmap.target_role}</Tag>
                <Typography.Title level={3}>从能力差距到行动计划</Typography.Title>
                <Typography.Paragraph>{roadmap.summary}</Typography.Paragraph>
              </div>
              <Progress type="dashboard" percent={completionPercent} strokeColor={{ '0%': '#5eead4', '100%': '#2563eb' }} />
            </div>
          </Card>

          <div className="roadmap-phase-grid">
            {roadmap.milestones.map((milestone, index) => (
              <RoadmapPhaseCard
                key={`${milestone.phase}-${milestone.period}`}
                role={roadmap.target_role}
                milestone={milestone}
                index={index}
                completed={completed}
                onToggle={toggleTask}
              />
            ))}
          </div>

          <Card className="roadmap-next-card" variant="borderless">
            <div className="roadmap-next-layout">
              <div>
                <Typography.Title level={4}>下一步推荐</Typography.Title>
                <Typography.Paragraph>{roadmap.conclusion || '优先完成第一阶段任务，并把学习成果沉淀为可展示的项目证据。'}</Typography.Paragraph>
                <Timeline
                  items={[
                    { color: '#2563eb', dot: <FieldTimeOutlined />, children: '本周：完成第一阶段 1 个关键任务' },
                    { color: '#14b8a6', dot: <CheckCircleOutlined />, children: '下周：产出作品、复盘或面试表达材料' },
                    { color: '#7c3aed', dot: <ArrowRightOutlined />, children: '之后：带着新进度继续咨询 AI 顾问' }
                  ]}
                />
              </div>
              <Space direction="vertical" size={12}>
                <Button type="primary" icon={<ArrowRightOutlined />} onClick={() => navigate(`/chat?role=${encodeURIComponent(roadmap.target_role)}&prompt=${encodeURIComponent(`请基于我的${roadmap.target_role}学习路径，帮我细化本周行动计划。`)}`)}>
                  继续咨询 AI 职业顾问
                </Button>
                <Button icon={<DownloadOutlined />} loading={exporting} onClick={() => void runExport()}>
                  保存本次规划结果
                </Button>
              </Space>
            </div>
          </Card>
        </>
      )}
    </div>
  );
}
