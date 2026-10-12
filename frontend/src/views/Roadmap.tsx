import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Alert, Button, Card, Checkbox, Empty, Input, Progress, Skeleton, Space, Tag, Timeline, Typography, message } from 'antd';
import {
  ArrowRightOutlined,
  DownloadOutlined,
  FieldTimeOutlined,
  FundProjectionScreenOutlined,
  ReloadOutlined,
  ThunderboltOutlined
} from '@ant-design/icons';
import { exportReport, fetchLearningPath } from '../api/agent';
import { fetchRoadmapVersion, saveRoadmapProgress } from '../api/history';
import { getErrorMessage } from '../api/client';
import { GrowthJourney } from '../components/GrowthJourney';
import { StandardSourceNote } from '../components/StandardSourceNote';
import type { LearningMilestone, LearningPathResponse } from '../api/types';
import { useProfile } from '../hooks/useProfile';
import { downloadBlob } from '../utils/download';
import { getPrimaryTargetRole } from '../utils/careerPlan';
import { getUserStorageKey } from '../utils/privateStorage';
import { useAuthStore } from '../store/authStore';

function getStageName(index: number) {
  if (index === 0) return '短期：建立基础';
  if (index === 1) return '中期：形成作品';
  return '长期：冲刺岗位';
}

function getLegacyPlanKey(roadmap: LearningPathResponse) {
  const content = JSON.stringify([roadmap.target_role, roadmap.summary, roadmap.milestones]);
  let hash = 2166136261;
  for (let index = 0; index < content.length; index += 1) {
    hash = Math.imul(hash ^ content.charCodeAt(index), 16777619);
  }
  return `${roadmap.target_role}:${(hash >>> 0).toString(36)}`;
}

function getPlanKey(roadmap: LearningPathResponse) {
  return roadmap.id ? `version:${roadmap.id}` : getLegacyPlanKey(roadmap);
}

function getServerTaskKeys(roadmap: LearningPathResponse, completed: Record<string, boolean>) {
  const planKey = getPlanKey(roadmap);
  return roadmap.milestones.flatMap((milestone) => milestone.focus_targets
    .filter((task) => completed[getTaskKey(planKey, milestone.phase, task)])
    .map((task) => `${milestone.phase}::${task}`));
}

function getCompletedMap(roadmap: LearningPathResponse) {
  const planKey = getPlanKey(roadmap);
  return Object.fromEntries((roadmap.completed_tasks || []).map((task) => {
    const [phase, ...name] = task.split('::');
    return [getTaskKey(planKey, phase, name.join('::')), true];
  })) as Record<string, boolean>;
}

function mergeServerCompletion(current: Record<string, boolean>, roadmap: LearningPathResponse) {
  const planKey = getPlanKey(roadmap);
  const next = Object.fromEntries(Object.entries(current).filter(([key]) => !key.startsWith(`${planKey}::`))) as Record<string, boolean>;
  return { ...next, ...getCompletedMap(roadmap) };
}

function getTaskKey(planKey: string, phase: string, task: string) {
  return `${planKey}::${phase}::${task}`;
}

function RoadmapPhaseCard({
  planKey,
  milestone,
  index,
  completed,
  savingProgress,
  onToggle
}: {
  planKey: string;
  milestone: LearningMilestone;
  index: number;
  completed: Record<string, boolean>;
  savingProgress: boolean;
  onToggle: (key: string, checked: boolean) => void;
}) {
  const tasks = milestone.focus_targets;
  const doneCount = tasks.filter((task) => completed[getTaskKey(planKey, milestone.phase, task)]).length;
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
        <Typography.Paragraph>{tasks.map((task) => task.split('；产出：', 1)[0]).join('、')}</Typography.Paragraph>
      </div>

      <div className="roadmap-task-list">
        <Typography.Text strong>关键任务</Typography.Text>
        {tasks.map((task) => {
          const key = getTaskKey(planKey, milestone.phase, task);
          return (
            <Checkbox key={key} checked={Boolean(completed[key])} disabled={savingProgress} onChange={(event) => onToggle(key, event.target.checked)}>
              {task}
            </Checkbox>
          );
        })}
      </div>

      <div className="roadmap-resource-list">
        <Typography.Text strong>推荐资源</Typography.Text>
        <Space wrap>
          {milestone.recommended_resources.length
            ? milestone.recommended_resources.map((resource) => (
              <Tag className="gradient-tag" key={resource}>
                {resource}
              </Tag>
            ))
            : <Typography.Text type="secondary">本阶段暂无具体资源建议</Typography.Text>}
        </Space>
      </div>
    </Card>
  );
}

export default function Roadmap() {
  const navigate = useNavigate();
  const userId = useAuthStore((state) => state.account?.id);
  const completedKey = getUserStorageKey('career-roadmap-completed', userId);
  const [searchParams, setSearchParams] = useSearchParams();
  const { profile, loading: profileLoading } = useProfile();
  const queryRole = searchParams.get('role') || '';
  const historyId = Number(searchParams.get('history_id') || 0);
  const [targetRole, setTargetRole] = useState(queryRole);
  const [roadmap, setRoadmap] = useState<LearningPathResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [completed, setCompleted] = useState<Record<string, boolean>>({});
  const [savingProgress, setSavingProgress] = useState(false);
  const lastAutoRole = useRef<string | null>(null);
  const requestId = useRef(0);
  const progressBusy = useRef(false);

  useEffect(() => {
    requestId.current += 1;
    lastAutoRole.current = null;
    setRoadmap(null);
    setCompleted({});
    if (!completedKey) return;
    const raw = localStorage.getItem(completedKey);
    if (!raw) return;
    try {
      setCompleted(JSON.parse(raw) as Record<string, boolean>);
    } catch {
      localStorage.removeItem(completedKey);
    }
  }, [completedKey]);

  useEffect(() => {
    if (!profileLoading && !targetRole) {
      setTargetRole(getPrimaryTargetRole(profile));
    }
  }, [profile, profileLoading, targetRole]);

  const activeRole = targetRole.trim() || getPrimaryTargetRole(profile);
  const planKey = roadmap ? getPlanKey(roadmap) : '';

  const completionPercent = useMemo(() => {
    const tasks =
      roadmap?.milestones.flatMap((milestone) =>
        milestone.focus_targets.map((task) =>
          getTaskKey(planKey, milestone.phase, task)
        )
      ) || [];
    if (!tasks.length) return 0;
    return Math.round((tasks.filter((task) => completed[task]).length / tasks.length) * 100);
  }, [completed, roadmap, planKey]);
  const nextPendingTask = roadmap?.milestones.flatMap((milestone) =>
    milestone.focus_targets.map((task) => ({ phase: milestone.phase, period: milestone.period, task }))
  ).find(({ phase, task }) => !completed[getTaskKey(planKey, phase, task)]);

  const loadRoadmap = async (role = activeRole) => {
    if (!role.trim()) return message.warning('请先填写目标职业方向');
    const currentRequest = ++requestId.current;
    setLoading(true);
    setError(null);
    try {
      const data = await fetchLearningPath(role.trim());
      if (currentRequest === requestId.current) {
        setRoadmap(data);
        setCompleted((current) => mergeServerCompletion(current, data));
        message.success('学习路径已生成并保存为新版本');
      }
    } catch (requestError) {
      if (currentRequest === requestId.current) setError(getErrorMessage(requestError, '学习路径生成失败'));
    } finally {
      if (currentRequest === requestId.current) setLoading(false);
    }
  };

  const requestRoadmap = () => {
    if (!completedKey) return message.warning('账号信息加载中，请稍后再试');
    const role = activeRole.trim();
    if (!role) return message.warning('请先填写目标职业方向');
    if (role !== queryRole) setSearchParams({ role });
    else void loadRoadmap(role);
  };

  useEffect(() => {
    if (historyId > 0 || !completedKey) return;
    if (queryRole && queryRole !== lastAutoRole.current) {
      lastAutoRole.current = queryRole;
      setTargetRole(queryRole);
      void loadRoadmap(queryRole);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [queryRole, completedKey, historyId]);

  useEffect(() => {
    if (!completedKey || !Number.isInteger(historyId) || historyId <= 0) return;
    const currentRequest = ++requestId.current;
    setLoading(true);
    setError(null);
    void fetchRoadmapVersion(historyId).then(async (saved) => {
      if (currentRequest !== requestId.current) return;
      if (saved.id && !saved.completed_tasks?.length) {
        try {
          const local = JSON.parse(localStorage.getItem(completedKey) || '{}') as Record<string, boolean>;
          const legacyKey = getLegacyPlanKey(saved);
          const migrated = saved.milestones.flatMap((milestone) => milestone.focus_targets
            .filter((task) => local[getTaskKey(legacyKey, milestone.phase, task)])
            .map((task) => `${milestone.phase}::${task}`));
          if (migrated.length) {
            await saveRoadmapProgress(saved.id, migrated);
            saved.completed_tasks = migrated;
            Object.keys(local).filter((key) => key.startsWith(`${legacyKey}::`)).forEach((key) => delete local[key]);
            localStorage.setItem(completedKey, JSON.stringify(local));
          }
        } catch {
          // The saved version remains available even if old local progress cannot be migrated.
        }
      }
      if (currentRequest !== requestId.current) return;
      setRoadmap(saved);
      setTargetRole(saved.target_role);
      setCompleted((current) => mergeServerCompletion(current, saved));
    }).catch((requestError) => {
      if (currentRequest === requestId.current) setError(getErrorMessage(requestError, '历史路径加载失败'));
    }).finally(() => {
      if (currentRequest === requestId.current) setLoading(false);
    });
  }, [completedKey, historyId]);

  const toggleTask = async (key: string, checked: boolean) => {
    if (!roadmap?.id || progressBusy.current) return;
    progressBusy.current = true;
    setSavingProgress(true);
    const previous = completed;
    const next = { ...completed, [key]: checked };
    setCompleted(next);
    if (completedKey) localStorage.setItem(completedKey, JSON.stringify(next));
    try {
      await saveRoadmapProgress(roadmap.id, getServerTaskKeys(roadmap, next));
    } catch (requestError) {
      setCompleted(previous);
      if (completedKey) localStorage.setItem(completedKey, JSON.stringify(previous));
      message.error(getErrorMessage(requestError, '任务进度保存失败'));
    } finally {
      progressBusy.current = false;
      setSavingProgress(false);
    }
  };

  const runExport = async () => {
    if (!activeRole) return message.warning('请先填写目标职业方向');
    setExporting(true);
    try {
      const report = await exportReport(roadmap?.target_role || activeRole, roadmap?.id);
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
    <div className="page-stack roadmap-page story-page">
      <section className="module-hero roadmap-hero">
        <div>
          <Tag className="hero-kicker" icon={<FundProjectionScreenOutlined />}>
            Learning Roadmap
          </Tag>
          <Typography.Title>阶段能力提升计划</Typography.Title>
          <Typography.Paragraph>
            结合目标职业和可投入的时间安排阶段任务。你可以标记完成状态、回看已保存版本，并随时带着当前画像继续咨询 AI 顾问。
          </Typography.Paragraph>
          <Space className="hero-actions" wrap>
            <Input
              className="roadmap-role-input"
              size="large"
              value={targetRole}
              onChange={(event) => setTargetRole(event.target.value)}
              placeholder="输入目标职业，例如：内容运营 / 招聘助理"
              disabled={loading}
            />
            <Button type="primary" size="large" icon={<ThunderboltOutlined />} loading={loading} onClick={requestRoadmap}>
              生成新的学习路径版本
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

      <GrowthJourney current="roadmap" />

      {error && (
        <Alert
          type="error"
          showIcon
          message={error}
          action={
            <Button icon={<ReloadOutlined />} onClick={requestRoadmap}>
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
          <Button type="primary" icon={<ThunderboltOutlined />} onClick={requestRoadmap}>
            生成我的学习提升路径
          </Button>
        </Card>
      )}

      {loading && (
        <Card className="guided-empty-card" variant="borderless">
          <ThunderboltOutlined className="loading-hero-icon" />
          <Typography.Title level={4}>正在生成你的阶段任务、推荐资源与下一步行动</Typography.Title>
          <Skeleton active paragraph={{ rows: 3 }} />
        </Card>
      )}

      {roadmap && !loading && (
        <>
          {historyId > 0 && <Alert type="info" showIcon
            message={`正在回看保存的路径版本 #${roadmap.id}`}
            description={roadmap.created_at ? `保存于 ${new Date(roadmap.created_at).toLocaleString()}；点击生成按钮可创建新版本。` : '旧版本未记录保存时间；点击生成按钮可创建新版本。'} />}
          <Card title="本路径使用的标准依据" variant="borderless">
            <StandardSourceNote source={roadmap.standard_source} notice={roadmap.standard_notice || (roadmap.standard_source ? 'AI 生成的任务与资源需要自行核对。' : '此路径未保存标准来源；AI 生成的任务与资源需要自行核对。')} />
          </Card>
          <Card className="story-next-task" variant="borderless">
            <div>
              <Typography.Text className="story-section-label">当前行动 · {roadmap.target_role}</Typography.Text>
              <Typography.Title level={3}>{nextPendingTask?.task.split('；产出：', 1)[0] || '当前版本的任务已全部完成'}</Typography.Title>
              <Typography.Paragraph type="secondary">
                {nextPendingTask ? `${nextPendingTask.phase} · ${nextPendingTask.period}。完成后在阶段任务中记录进度。` : '你可以回看已完成的任务，或明确下一阶段目标后生成新版本。'}
              </Typography.Paragraph>
            </div>
            <Button type="primary" icon={<ArrowRightOutlined />} onClick={() => document.getElementById('roadmap-phases')?.scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start' })}>
              查看阶段任务
            </Button>
          </Card>
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

          <div className="roadmap-phase-grid" id="roadmap-phases">
            {roadmap.milestones.map((milestone, index) => (
              <RoadmapPhaseCard
                key={`${milestone.phase}-${milestone.period}`}
                planKey={planKey}
                milestone={milestone}
                index={index}
                completed={completed}
                savingProgress={savingProgress}
                onToggle={toggleTask}
              />
            ))}
          </div>

          <Card className="roadmap-next-card" variant="borderless">
            <div className="roadmap-next-layout">
              <div>
                <Typography.Title level={4}>下一步推荐</Typography.Title>
                <Typography.Paragraph>{roadmap.conclusion}</Typography.Paragraph>
                <Timeline
                  items={roadmap.milestones.flatMap((milestone) => milestone.focus_targets.map((task) => ({
                    color: '#2563eb',
                    dot: <FieldTimeOutlined />,
                    children: `${milestone.period}：${task}`
                  }))).slice(0, 3)}
                />
              </div>
              <Space direction="vertical" size={12}>
                <Button type="primary" icon={<ArrowRightOutlined />} onClick={() => navigate(`/chat?role=${encodeURIComponent(roadmap.target_role)}&roadmap_id=${roadmap.id}&prompt=${encodeURIComponent(`请基于我的${roadmap.target_role}学习路径，帮我细化本周行动计划。`)}`)}>
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
