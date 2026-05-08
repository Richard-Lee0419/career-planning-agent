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
import { exportReport, fetchGapAnalysis, fetchLearningPath, sendAgentChat } from '../api/agent';
import { getErrorMessage } from '../api/client';
import type { GapAnalysisResponse, GraphData, LearningPathResponse, MockInterviewGraphData } from '../api/types';
import { CareerTree } from '../components/CareerTree';
import { ChatBubble } from '../components/ChatBubble';
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
  const [input, setInput] = useState('');
  const [targetRole, setTargetRole] = useState('前端工程师');
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [canvasMode, setCanvasMode] = useState<CanvasMode>('tree');
  const [gapData, setGapData] = useState<GapAnalysisResponse | null>(null);
  const [roadmapData, setRoadmapData] = useState<LearningPathResponse | null>(null);
  const [sending, setSending] = useState(false);
  const [actionLoading, setActionLoading] = useState<CanvasMode | 'export' | null>(null);
  const [lastFailedPrompt, setLastFailedPrompt] = useState<string | null>(null);
  const chatEndRef = useRef<HTMLDivElement | null>(null);
  const queryPromptApplied = useRef(false);

  useEffect(() => {
    const role = searchParams.get('role');
    const prompt = searchParams.get('prompt');
    if (role) setTargetRole(role);
    if (prompt && !queryPromptApplied.current) {
      setInput(prompt);
      queryPromptApplied.current = true;
    }
  }, [searchParams]);

  useEffect(() => {
    setTargetRole((current) => (current === '前端工程师' ? pickFirstTarget(profile?.target_roles, current) : current));
  }, [profile]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, sending]);

  const quickPrompts = useMemo(
    () => [
      `我适合从事${targetRole}吗？请说明理由`,
      `我现在最需要提升什么能力？目标是${targetRole}`,
      `请帮我制定一个 4 周${targetRole}学习计划`,
      `我的专业适合哪些岗位？请给出 3 个方向`,
      `我该如何准备${targetRole}方向的实习？`
    ],
    [targetRole]
  );

  const profileStrengths = useMemo(() => getProfileStrengths(profile), [profile]);
  const profileGaps = useMemo(() => getProfileGaps(profile), [profile]);

  const submitMessage = async (text = input) => {
    const content = text.trim();
    if (!content) return;

    setInput('');
    setSending(true);
    setLastFailedPrompt(null);
    const userMessage: ChatMessage = { id: crypto.randomUUID(), role: 'user', content };
    setMessages((current) => [...current, userMessage]);

    try {
      const response = await sendAgentChat({
        session_id: sessionId,
        message: content,
        profile
      });
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
      message.error(getErrorMessage(error, '对话失败'));
      setLastFailedPrompt(content);
      setMessages((current) => [
        ...current,
        { id: crypto.randomUUID(), role: 'assistant', content: '服务暂时没有返回。你可以点击“重试上一次问题”，或稍后继续咨询。' }
      ]);
    } finally {
      setSending(false);
    }
  };

  const runGapAnalysis = async () => {
    if (!targetRole.trim()) return message.warning('请输入目标岗位');
    setCanvasMode('gap');
    setActionLoading('gap');
    try {
      const data = await fetchGapAnalysis(targetRole.trim());
      setGapData(data);
    } catch (error) {
      message.error(getErrorMessage(error, '差距分析失败'));
    } finally {
      setActionLoading(null);
    }
  };

  const runLearningPath = async () => {
    if (!targetRole.trim()) return message.warning('请输入目标岗位');
    setCanvasMode('roadmap');
    setActionLoading('roadmap');
    try {
      const data = await fetchLearningPath(targetRole.trim());
      setRoadmapData(data);
    } catch (error) {
      message.error(getErrorMessage(error, '学习路径生成失败'));
    } finally {
      setActionLoading(null);
    }
  };

  const runExport = async () => {
    if (!targetRole.trim()) return message.warning('请输入目标岗位');
    setActionLoading('export');
    try {
      const report = await exportReport(targetRole.trim());
      downloadBlob(report.blob, report.filename);
      message.success('报告已生成');
    } catch (error) {
      message.error(getErrorMessage(error, '报告导出失败'));
    } finally {
      setActionLoading(null);
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
            <Typography.Title level={4}>{gapData.overall_match_score} 分匹配度</Typography.Title>
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

  const clearConversation = () => {
    setMessages([
      {
        id: 'hello',
        role: 'assistant',
        content: '对话已清空。你可以重新描述目标岗位、当前困惑或希望我细化的学习计划。'
      }
    ]);
    setLastFailedPrompt(null);
  };

  const saveAdvice = () => {
    const content = messages.map((item) => `${item.role === 'user' ? '我' : 'AI 顾问'}：${item.content}`).join('\n\n');
    downloadBlob(new Blob([content], { type: 'text/plain;charset=utf-8' }), `AI职业顾问建议-${targetRole}.txt`);
    message.success('AI 顾问建议已保存');
  };

  return (
    <div className="chat-room">
      <Card className="chat-panel" variant="borderless">
        <div className="chat-panel-header">
          <Avatar className="coach-avatar" icon={<ThunderboltOutlined />} />
          <div>
            <Typography.Title level={4}>AI 职业顾问</Typography.Title>
            <Typography.Text type="secondary">基于当前职业画像继续追问，而不是从零开始聊天</Typography.Text>
          </div>
        </div>
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
            <strong>{targetRole}</strong>
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
            <strong>{profileGaps[0]}</strong>
          </div>
        </div>
        <div className="chat-stream">
          {messages.map((item) => (
            <ChatBubble key={item.id} role={item.role} content={item.content} />
          ))}
          {sending && (
            <div className="assistant-thinking">
              <Spin size="small" />
              <span>AI 正在生成</span>
            </div>
          )}
          <div ref={chatEndRef} />
        </div>
        <div className="quick-prompts">
          {quickPrompts.map((prompt) => (
            <Button className="quick-prompt-button" key={prompt} size="small" icon={<QuestionCircleOutlined />} onClick={() => void submitMessage(prompt)}>
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
              <Button icon={<ReloadOutlined />} onClick={() => void submitMessage(lastFailedPrompt)}>
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
              if (!event.shiftKey) {
                event.preventDefault();
                void submitMessage();
              }
            }}
          />
          <Tooltip title="发送">
            <Button type="primary" icon={<SendOutlined />} loading={sending} onClick={() => void submitMessage()} />
          </Tooltip>
        </div>
        <div className="chat-secondary-actions">
          <Button icon={<SaveOutlined />} onClick={saveAdvice} disabled={messages.length <= 1}>
            保存顾问建议
          </Button>
          <Button icon={<ClearOutlined />} onClick={clearConversation}>
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
              onChange={(event) => setTargetRole(event.target.value)}
              placeholder="目标岗位"
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
            <Button icon={<RadarChartOutlined />} loading={actionLoading === 'gap'} onClick={() => void runGapAnalysis()}>
              生成能力差距分析
            </Button>
            <Button icon={<ThunderboltOutlined />} loading={actionLoading === 'roadmap'} onClick={() => void runLearningPath()}>
              生成学习提升路径
            </Button>
            <Button icon={<DownloadOutlined />} loading={actionLoading === 'export'} onClick={() => void runExport()}>
              保存本次规划结果
            </Button>
          </Space>
        }
      >
        <div className="canvas-content">{renderCanvas()}</div>
      </Card>
    </div>
  );
}
