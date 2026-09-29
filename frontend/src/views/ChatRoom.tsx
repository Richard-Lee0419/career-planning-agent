import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Alert,
  Avatar,
  Button,
  Card,
  Empty,
  Input,
  List,
  Segmented,
  Select,
  Space,
  Spin,
  Tag,
  Tooltip,
  Typography,
  message
} from 'antd';
import {
  ClearOutlined,
  DownloadOutlined,
  FundProjectionScreenOutlined,
  QuestionCircleOutlined,
  RadarChartOutlined,
  ReloadOutlined,
  SaveOutlined,
  SendOutlined,
  ThunderboltOutlined
} from '@ant-design/icons';
import { useSearchParams } from 'react-router-dom';
import { clearChatSession, createChatSession, exportReport, fetchChatSession, fetchChatSessions, fetchGapAnalysis, fetchLearningPath, sendAgentChat } from '../api/agent';
import { getErrorMessage } from '../api/client';
import type { ChatSessionItem, GapAnalysisResponse, GraphData, LearningPathResponse, MockInterviewGraphData } from '../api/types';
import { CareerTree } from '../components/CareerTree';
import { ChatBubble } from '../components/ChatBubble';
import { GrowthJourney } from '../components/GrowthJourney';
import { GapRadar } from '../components/GapRadar';
import { RoadmapTimeline } from '../components/RoadmapTimeline';
import { useProfile } from '../hooks/useProfile';
import { downloadBlob } from '../utils/download';
import { pickFirstTarget } from '../utils/format';
import { getProfileGaps, getProfileStrengths, hasCareerProfile } from '../utils/careerPlan';

type CanvasMode = 'tree' | 'gap' | 'roadmap';

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
}

function isMockInterviewGraph(data?: GraphData | null): data is MockInterviewGraphData {
  return Boolean(data && (data as MockInterviewGraphData).type === 'mock_interview');
}

function getAssistantFallback(graphData?: GraphData | null) {
  if (!graphData) return 'AI 已完成分析，但没有返回可展示的文字内容。请换一种问法，或让我继续展开说明。';
  const graphType = (graphData as { type?: string }).type;
  if (graphType === 'mock_interview') return '我已生成模拟面试题组，请在右侧面板查看题目并开始练习。';
  if (graphType === 'career_map') return '我已生成职业发展图谱，请在右侧画板查看晋升阶段和能力要求。';
  return '我已生成结构化分析结果，请查看右侧智能职业画板。';
}

export default function ChatRoom() {
  const { profile } = useProfile();
  const [searchParams] = useSearchParams();
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'hello',
      role: 'assistant',
      content: '你好，我是你的 AI 职业顾问。我可以基于职业画像继续分析岗位适配度、能力差距、学习计划和实习准备。'
    }
  ]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessions, setSessions] = useState<ChatSessionItem[]>([]);
  const [sessionBusy, setSessionBusy] = useState(false);
  const [roadmapId, setRoadmapId] = useState<number | null>(null);
  const [input, setInput] = useState('');
  const [targetRole, setTargetRole] = useState('');
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [canvasMode, setCanvasMode] = useState<CanvasMode>('tree');
  const [gapData, setGapData] = useState<GapAnalysisResponse | null>(null);
  const [roadmapData, setRoadmapData] = useState<LearningPathResponse | null>(null);
  const [sending, setSending] = useState(false);
  const [actionLoading, setActionLoading] = useState<CanvasMode | 'export' | null>(null);
  const [lastFailedPrompt, setLastFailedPrompt] = useState<string | null>(null);
  const [lastFailedRequestId, setLastFailedRequestId] = useState<string | null>(null);
  const chatStreamRef = useRef<HTMLDivElement | null>(null);
  const queryPromptApplied = useRef(false);
  const sendInFlight = useRef(false);
  const sendController = useRef<AbortController | null>(null);
  const sendGeneration = useRef(0);
  const canvasGeneration = useRef(0);
  const canvasBusy = useRef(false);
  const sessionGeneration = useRef(0);

  useEffect(() => () => {
    sendGeneration.current += 1;
    canvasGeneration.current += 1;
    sendController.current?.abort();
  }, []);

  useEffect(() => {
    const role = searchParams.get('role');
    const selectedRoadmap = Number(searchParams.get('roadmap_id') || 0);
    const prompt = searchParams.get('prompt');
    if (role) setTargetRole(role);
    if (Number.isInteger(selectedRoadmap) && selectedRoadmap > 0) setRoadmapId(selectedRoadmap);
    if (prompt && !queryPromptApplied.current) {
      setInput(prompt);
      queryPromptApplied.current = true;
    }
  }, [searchParams]);

  useEffect(() => {
    void fetchChatSessions().then(setSessions).catch(() => message.warning('历史对话暂时无法加载'));
  }, []);

  useEffect(() => {
    setTargetRole((current) => current || pickFirstTarget(profile?.target_roles, ''));
  }, [profile]);

  useEffect(() => {
    const stream = chatStreamRef.current;
    if (!stream) return;
    stream.scrollTo({
      top: stream.scrollHeight,
      behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth'
    });
  }, [messages, sending]);

  const quickPrompts = useMemo(
    () => [
      `我适合从事${targetRole || '目标岗位'}吗？请说明理由`,
      `我现在最需要提升什么能力？目标是${targetRole || '我选择的岗位'}`,
      `请帮我制定一个 4 周${targetRole || '职业探索'}学习计划`,
      `我的专业适合哪些岗位？请给出 3 个方向`,
      `我该如何准备${targetRole || '目标方向'}的实习？`
    ],
    [targetRole]
  );

  const profileStrengths = useMemo(() => getProfileStrengths(profile), [profile]);
  const profileGaps = useMemo(() => getProfileGaps(profile), [profile]);

  const submitMessage = async (text = input, retryRequestId?: string) => {
    const content = text.trim();
    if (!content || sendInFlight.current || sessionBusy) return;

    sendInFlight.current = true;
    const generation = ++sendGeneration.current;
    const controller = new AbortController();
    sendController.current = controller;
    setInput('');
    setSending(true);
    setLastFailedPrompt(null);
    setLastFailedRequestId(null);
    const requestId = retryRequestId || crypto.randomUUID();
    const userMessage: ChatMessage = { id: crypto.randomUUID(), role: 'user', content };
    setMessages((current) => [...(retryRequestId ? current.slice(0, -2) : current), userMessage]);

    try {
      let activeSessionId = sessionId;
      if (!activeSessionId) {
        const created = await createChatSession(targetRole.trim(), roadmapId || undefined);
        if (generation !== sendGeneration.current) return;
        activeSessionId = created.id;
        setSessionId(created.id);
        setSessions((current) => [created, ...current]);
      }
      const response = await sendAgentChat({
        session_id: activeSessionId,
        message: content,
        request_id: requestId,
        target_role: targetRole.trim(),
        roadmap_id: roadmapId
      }, controller.signal);
      if (generation !== sendGeneration.current) return;
      setSessionId(response.session_id);
      const assistantReply = response.reply?.trim() || getAssistantFallback(response.graph_data);
      setMessages((current) => [
        ...current,
        { id: crypto.randomUUID(), role: 'assistant', content: assistantReply }
      ]);
      if (response.graph_data) {
        setGraphData(response.graph_data);
        setCanvasMode('tree');
      }
    } catch (error) {
      if (generation !== sendGeneration.current || controller.signal.aborted) return;
      message.error(getErrorMessage(error, '对话失败'));
      setLastFailedPrompt(content);
      setLastFailedRequestId(requestId);
      setMessages((current) => [
        ...current,
        { id: crypto.randomUUID(), role: 'assistant', content: '服务暂时没有返回。你可以点击“重试上一次问题”，或稍后继续咨询。' }
      ]);
    } finally {
      if (generation === sendGeneration.current) {
        sendInFlight.current = false;
        sendController.current = null;
        setSending(false);
      }
    }
  };

  const runGapAnalysis = async () => {
    if (!targetRole.trim()) return message.warning('请输入目标岗位');
    if (canvasBusy.current) return;
    canvasBusy.current = true;
    const generation = ++canvasGeneration.current;
    setCanvasMode('gap');
    setActionLoading('gap');
    try {
      const data = await fetchGapAnalysis(targetRole.trim());
      if (generation === canvasGeneration.current) setGapData(data);
    } catch (error) {
      if (generation === canvasGeneration.current) message.error(getErrorMessage(error, '差距分析失败'));
    } finally {
      if (generation === canvasGeneration.current) {
        canvasBusy.current = false;
        setActionLoading(null);
      }
    }
  };

  const runLearningPath = async () => {
    if (!targetRole.trim()) return message.warning('请输入目标岗位');
    if (canvasBusy.current) return;
    canvasBusy.current = true;
    const generation = ++canvasGeneration.current;
    setCanvasMode('roadmap');
    setActionLoading('roadmap');
    try {
      const data = await fetchLearningPath(targetRole.trim());
      if (generation === canvasGeneration.current) {
        setRoadmapData(data);
        setRoadmapId(data.id || null);
      }
    } catch (error) {
      if (generation === canvasGeneration.current) message.error(getErrorMessage(error, '学习路径生成失败'));
    } finally {
      if (generation === canvasGeneration.current) {
        canvasBusy.current = false;
        setActionLoading(null);
      }
    }
  };

  const runExport = async () => {
    if (!targetRole.trim()) return message.warning('请输入目标岗位');
    if (canvasBusy.current) return;
    canvasBusy.current = true;
    const generation = ++canvasGeneration.current;
    setActionLoading('export');
    try {
      const report = await exportReport(targetRole.trim(), roadmapData?.id || roadmapId);
      if (generation !== canvasGeneration.current) return;
      downloadBlob(report.blob, report.filename);
      message.success('报告已生成');
    } catch (error) {
      if (generation === canvasGeneration.current) message.error(getErrorMessage(error, '报告导出失败'));
    } finally {
      if (generation === canvasGeneration.current) {
        canvasBusy.current = false;
        setActionLoading(null);
      }
    }
  };

  const renderCanvas = () => {
    if (canvasMode === 'gap') {
      if (actionLoading === 'gap') return <Spin className="center-spin" />;
      if (!gapData) {
        return (
          <Empty
            className="panel-empty"
            description="还没有能力差距分析"
          >
            <Button type="primary" icon={<RadarChartOutlined />} onClick={() => void runGapAnalysis()}>
              生成能力差距分析
            </Button>
          </Empty>
        );
      }
      return (
        <div className="canvas-grid">
          <GapRadar data={gapData} />
          <div className="analysis-notes">
            <Typography.Title level={4}>{gapData.overall_match_score}% 综合匹配度</Typography.Title>
            <Typography.Paragraph type="secondary">已匹配：{gapData.matched_requirements?.join('、') || '暂无直接匹配'}；主要差距：{gapData.missing_requirements?.slice(0, 3).join('、') || '暂无'}</Typography.Paragraph>
            <Typography.Paragraph>{gapData.roadmap_preview}</Typography.Paragraph>
            <Space wrap>
              {gapData.immediate_next_steps.map((step) => (
                <Tag color="cyan" key={step}>
                  {step}
                </Tag>
              ))}
            </Space>
          </div>
        </div>
      );
    }

    if (canvasMode === 'roadmap') {
      if (actionLoading === 'roadmap') return <Spin className="center-spin" />;
      if (!roadmapData) {
        return (
          <Empty className="panel-empty" description="还没有学习路径">
            <Button type="primary" icon={<ThunderboltOutlined />} onClick={() => void runLearningPath()}>
              生成学习提升路径
            </Button>
          </Empty>
        );
      }
      return <RoadmapTimeline data={roadmapData} />;
    }

    if (isMockInterviewGraph(graphData)) {
      return (
        <div className="mock-questions-panel">
          <Typography.Title level={4}>{graphData.role}</Typography.Title>
          <List
            dataSource={graphData.questions}
            renderItem={(question, index) => (
              <List.Item>
                <Tag color="gold">Q{index + 1}</Tag>
                <Typography.Text>{question}</Typography.Text>
              </List.Item>
            )}
          />
        </div>
      );
    }

    return <CareerTree data={graphData} />;
  };

  const resetConversation = () => {
    sessionGeneration.current += 1;
    canvasGeneration.current += 1;
    canvasBusy.current = false;
    setActionLoading(null);
    sendGeneration.current += 1;
    sendController.current?.abort();
    sendController.current = null;
    sendInFlight.current = false;
    setSending(false);
    setSessionId(null);
    setInput('');
    setGraphData(null);
    setGapData(null);
    setRoadmapData(null);
    setCanvasMode('tree');
    setMessages([
      {
        id: 'hello',
        role: 'assistant',
        content: '对话已清空。你可以重新描述目标岗位、当前困惑或希望我细化的学习计划。'
      }
    ]);
    setLastFailedPrompt(null);
    setLastFailedRequestId(null);
  };

  const startNewSession = async () => {
    resetConversation();
    setRoadmapId(null);
    const generation = sessionGeneration.current;
    setSessionBusy(true);
    try {
      const created = await createChatSession(targetRole.trim());
      if (generation !== sessionGeneration.current) return;
      setSessionId(created.id);
      setSessions((current) => [created, ...current]);
    } catch (error) {
      if (generation === sessionGeneration.current) message.error(getErrorMessage(error, '新建对话失败'));
    } finally {
      if (generation === sessionGeneration.current) setSessionBusy(false);
    }
  };

  const continueSession = async (id: string) => {
    resetConversation();
    const generation = sessionGeneration.current;
    setSessionBusy(true);
    try {
      const saved = await fetchChatSession(id);
      if (generation !== sessionGeneration.current) return;
      setSessionId(saved.id);
      setTargetRole(saved.target_role || '');
      setRoadmapId(saved.roadmap_id || null);
      setMessages(saved.messages.length ? saved.messages.map((item) => ({
        id: `saved-${item.id}`, role: item.role, content: item.content
      })) : [{ id: 'hello', role: 'assistant', content: '这是一个新对话，请描述你的职业规划问题。' }]);
      setGraphData([...saved.messages].reverse().find((item) => item.graph_data)?.graph_data || null);
    } catch (error) {
      if (generation === sessionGeneration.current) message.error(getErrorMessage(error, '历史对话加载失败'));
    } finally {
      if (generation === sessionGeneration.current) setSessionBusy(false);
    }
  };

  const clearConversation = async () => {
    const previousId = sessionId;
    resetConversation();
    setRoadmapId(null);
    if (!previousId) return;
    try {
      await clearChatSession(previousId);
      setSessions((current) => current.filter((item) => item.id !== previousId));
    } catch (error) {
      message.error(getErrorMessage(error, '服务器端清空失败，请稍后重试'));
    }
  };

  const saveAdvice = () => {
    const content = messages.map((item) => `${item.role === 'user' ? '我' : 'AI 顾问'}：${item.content}`).join('\n\n');
    downloadBlob(new Blob([content], { type: 'text/plain;charset=utf-8' }), `AI职业顾问建议-${targetRole}.txt`);
    message.success('AI 顾问建议已保存');
  };

  return (
    <div className="page-stack story-page chat-story-page">
      <section className="story-chat-header" aria-label="AI 顾问当前上下文">
        <div>
          <Tag className="hero-kicker" icon={<ThunderboltOutlined />}>AI Career Advisor</Tag>
          <Typography.Title level={2}>带着你的画像，继续向目标岗位前进</Typography.Title>
          <Typography.Paragraph>当前问题、能力差距与学习路径在同一段对话中持续衔接。</Typography.Paragraph>
        </div>
        <div className="story-chat-context">
          <div><span>目标岗位</span><strong>{targetRole || '待选择'}</strong></div>
          <div><span>学习路径</span><strong>{roadmapId ? `版本 #${roadmapId}` : '尚未关联'}</strong></div>
          <div><span>当前对话</span><strong>{sessionId ? '已保存的 Session' : '新对话'}</strong></div>
        </div>
      </section>

      <GrowthJourney current="chat" />

      <div className="chat-room">
      <Card className="chat-panel" variant="borderless">
        <div className="chat-panel-header">
          <Avatar className="coach-avatar" icon={<ThunderboltOutlined />} />
          <div>
            <Typography.Title level={4}>AI 职业顾问</Typography.Title>
            <Typography.Text type="secondary">基于当前职业画像继续追问，而不是从零开始聊天</Typography.Text>
          </div>
        </div>
        <Space wrap className="chat-secondary-actions">
          <Select
            aria-label="选择历史对话"
            placeholder="选择历史对话"
            value={sessionId || undefined}
            disabled={sessionBusy}
            style={{ minWidth: 210 }}
            options={sessions.map((item) => ({
              value: item.id,
              label: `${item.target_role || '职业咨询'} · ${new Date(item.created_at).toLocaleString()}`
            }))}
            onChange={(id) => void continueSession(id)}
          />
          <Button loading={sessionBusy} onClick={() => void startNewSession()}>新建对话</Button>
        </Space>
        {!hasCareerProfile(profile) && (
          <Alert
            className="chat-profile-alert"
            type="info"
            showIcon
            message="职业画像尚未完整"
            description="你仍可提问，但完成职业测评后，AI 顾问会给出更贴合你的回答。"
          />
        )}
        <div className="coach-status-grid">
          <div>
            <span>目标岗位</span>
            <strong>{targetRole || '待选择'}</strong>
          </div>
          <div>
            <span>画像摘要</span>
            <strong>{profile?.major || profileStrengths[0] || '待完善'}</strong>
          </div>
          <div>
            <span>核心优势</span>
            <strong>{profileStrengths.slice(0, 2).join('、')}</strong>
          </div>
          <div>
            <span>优先补齐</span>
            <strong>{profileGaps[0] || '待分析'}</strong>
          </div>
        </div>
        <div className="chat-stream" ref={chatStreamRef}>
          {messages.map((item) => (
            <ChatBubble key={item.id} role={item.role} content={item.content} />
          ))}
          {sending && (
            <div className="assistant-thinking">
              <Spin size="small" />
              <span>AI 正在生成</span>
            </div>
          )}
        </div>
        <div className="quick-prompts">
          {quickPrompts.map((prompt) => (
            <Button className="quick-prompt-button" key={prompt} size="small" icon={<QuestionCircleOutlined />} disabled={sending} onClick={() => void submitMessage(prompt)}>
              {prompt}
            </Button>
          ))}
        </div>
        {lastFailedPrompt && (
          <Alert
            className="chat-retry-alert"
            type="error"
            showIcon
            message="上一次问题发送失败"
            action={
              <Button icon={<ReloadOutlined />} disabled={sending} onClick={() => void submitMessage(lastFailedPrompt, lastFailedRequestId || undefined)}>
                重试上一次问题
              </Button>
            }
          />
        )}
        <div className="chat-input-row">
          <Input.TextArea
            value={input}
            onChange={(event) => setInput(event.target.value)}
            autoSize={{ minRows: 2, maxRows: 5 }}
            placeholder="输入你的职业规划问题"
            onPressEnter={(event) => {
              if (!event.shiftKey && !event.nativeEvent.isComposing) {
                event.preventDefault();
                void submitMessage();
              }
            }}
          />
          <Tooltip title="发送">
            <Button type="primary" icon={<SendOutlined />} loading={sending} disabled={!input.trim() || sessionBusy} aria-label="发送消息" onClick={() => void submitMessage()} />
          </Tooltip>
        </div>
        <div className="chat-secondary-actions">
          <Button icon={<SaveOutlined />} onClick={saveAdvice} disabled={messages.length <= 1}>
            保存顾问建议
          </Button>
          <Button icon={<ClearOutlined />} disabled={sessionBusy} onClick={() => void clearConversation()}>
            清空对话
          </Button>
        </div>
      </Card>

      <Card
        className="canvas-panel"
        variant="borderless"
        title={
          <Space>
            <FundProjectionScreenOutlined />
            <span>智能职业画板</span>
          </Space>
        }
        extra={
          <Space wrap>
            <Input
              className="target-role-input"
              value={targetRole}
              onChange={(event) => {
                if (sessionId && event.target.value !== targetRole) resetConversation();
                setTargetRole(event.target.value);
                setRoadmapId(null);
                setRoadmapData(null);
                setGapData(null);
              }}
              placeholder="目标岗位"
              disabled={actionLoading !== null}
            />
            <Segmented
              value={canvasMode}
              onChange={(value) => setCanvasMode(value as CanvasMode)}
              options={[
                { label: '图谱', value: 'tree', icon: <FundProjectionScreenOutlined /> },
                { label: '差距', value: 'gap', icon: <RadarChartOutlined /> },
                { label: '路径', value: 'roadmap', icon: <ThunderboltOutlined /> }
              ]}
            />
            <Button icon={<RadarChartOutlined />} loading={actionLoading === 'gap'} disabled={actionLoading !== null && actionLoading !== 'gap'} onClick={() => void runGapAnalysis()}>
              生成能力差距分析
            </Button>
            <Button icon={<ThunderboltOutlined />} loading={actionLoading === 'roadmap'} disabled={actionLoading !== null && actionLoading !== 'roadmap'} onClick={() => void runLearningPath()}>
              生成学习提升路径
            </Button>
            <Button icon={<DownloadOutlined />} loading={actionLoading === 'export'} disabled={actionLoading !== null && actionLoading !== 'export'} onClick={() => void runExport()}>
              保存本次规划结果
            </Button>
          </Space>
        }
      >
        <div className="canvas-content">{renderCanvas()}</div>
      </Card>
      </div>
    </div>
  );
}
