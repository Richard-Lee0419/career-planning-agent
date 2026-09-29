import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Alert,
  Button,
  Card,
  Collapse,
  Empty,
  Input,
  List,
  Progress,
  Space,
  Spin,
  Tag,
  Typography,
  message
} from 'antd';
import { BulbOutlined, CheckCircleOutlined, FieldTimeOutlined, RocketOutlined, SoundOutlined } from '@ant-design/icons';
import {
  evaluateInterviewAnswer,
  fetchAudioStatus,
  fetchInterviewHistory,
  fetchInterviewQuestions,
  fetchTargetedQuestion,
  speechToText
} from '../api/interview';
import type { AudioJobStatus } from '../api/interview';
import { getErrorMessage, getStaticAssetUrl } from '../api/client';
import type { GeneralQuestionItem, InterviewHistoryItem, MockEvaluation, TargetedInterviewResponse } from '../api/types';
import { AudioRecorder } from '../components/AudioRecorder';
import { GrowthJourney } from '../components/GrowthJourney';
import { recordedBlobToWavFile } from '../utils/audio';
import { useProfile } from '../hooks/useProfile';

export default function Interview() {
  const { profile } = useProfile();
  const [targetRole, setTargetRole] = useState('');
  const [focusTopics, setFocusTopics] = useState('基础知识, 实战经验, 项目复盘');
  const [questions, setQuestions] = useState<GeneralQuestionItem[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [targeted, setTargeted] = useState<TargetedInterviewResponse | null>(null);
  const [answer, setAnswer] = useState('');
  const [voiceAnswer, setVoiceAnswer] = useState<string | null>(null);
  const [evaluation, setEvaluation] = useState<MockEvaluation | null>(null);
  const [history, setHistory] = useState<InterviewHistoryItem[]>([]);
  const [loadingQuestions, setLoadingQuestions] = useState(false);
  const [loadingTargeted, setLoadingTargeted] = useState(false);
  const [evaluating, setEvaluating] = useState(false);
  const [sttLoading, setSttLoading] = useState(false);
  const [audioStatus, setAudioStatus] = useState<AudioJobStatus | null>(null);
  const questionGeneration = useRef(0);
  const questionBusy = useRef(false);
  const evaluationGeneration = useRef(0);
  const evaluationBusy = useRef(false);
  const voiceGeneration = useRef(0);

  useEffect(() => {
    void fetchInterviewHistory()
      .then((response) => setHistory(response.data))
      .catch(() => setHistory([]));
  }, []);

  useEffect(() => {
    setTargetRole((current) => current || profile?.target_roles?.[0] || '');
  }, [profile]);

  const selectedQuestion = useMemo(
    () => questions.find((question) => question.id === selectedId) || questions[0],
    [questions, selectedId]
  );

  const activeQuestion = targeted?.question_data.question || selectedQuestion?.question || '';
  const activeFocus = targeted?.question_data.focus_topic || selectedQuestion?.topic || '综合能力';
  const activeAudioUrl = targeted ? targeted.audio_url : selectedQuestion?.audio_url;

  useEffect(() => {
    if (!activeAudioUrl) {
      setAudioStatus(null);
      return;
    }
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let attempts = 0;
    setAudioStatus('pending');
    const poll = async () => {
      attempts += 1;
      try {
        const status = await fetchAudioStatus(activeAudioUrl);
        if (cancelled) return;
        if (status === 'pending' && attempts < 60) {
          timer = setTimeout(() => void poll(), 2000);
        } else {
          setAudioStatus(status === 'pending' ? 'failed' : status);
        }
      } catch {
        if (cancelled) return;
        if (attempts < 3) timer = setTimeout(() => void poll(), 2000);
        else setAudioStatus('failed');
      }
    };
    void poll();
    return () => { cancelled = true; if (timer) clearTimeout(timer); };
  }, [activeAudioUrl]);

  const invalidateAnswer = () => {
    evaluationGeneration.current += 1;
    voiceGeneration.current += 1;
    evaluationBusy.current = false;
    setEvaluating(false);
    setSttLoading(false);
    setEvaluation(null);
    setAnswer('');
    setVoiceAnswer(null);
  };

  const changeTargetRole = (role: string) => {
    questionGeneration.current += 1;
    questionBusy.current = false;
    setLoadingQuestions(false);
    setLoadingTargeted(false);
    setTargetRole(role);
    setQuestions([]);
    setSelectedId(null);
    setTargeted(null);
    invalidateAnswer();
  };

  const generateQuestions = async () => {
    if (questionBusy.current) return;
    if (!targetRole.trim()) return message.warning('请先填写目标岗位');
    questionBusy.current = true;
    const generation = ++questionGeneration.current;
    setLoadingQuestions(true);
    setTargeted(null);
    invalidateAnswer();
    try {
      const data = await fetchInterviewQuestions(targetRole.trim(), focusTopics.trim());
      if (generation !== questionGeneration.current) return;
      setQuestions(data.questions);
      setSelectedId(data.questions[0]?.id ?? null);
    } catch (error) {
      if (generation === questionGeneration.current) message.error(getErrorMessage(error, '面试题生成失败'));
    } finally {
      if (generation === questionGeneration.current) {
        questionBusy.current = false;
        setLoadingQuestions(false);
      }
    }
  };

  const generateTargeted = async () => {
    if (questionBusy.current) return;
    if (!targetRole.trim()) return message.warning('请先填写目标岗位');
    questionBusy.current = true;
    const generation = ++questionGeneration.current;
    setLoadingTargeted(true);
    invalidateAnswer();
    try {
      const data = await fetchTargetedQuestion(targetRole.trim());
      if (generation !== questionGeneration.current) return;
      setTargeted(data);
    } catch (error) {
      if (generation === questionGeneration.current) message.error(getErrorMessage(error, '定向题生成失败'));
    } finally {
      if (generation === questionGeneration.current) {
        questionBusy.current = false;
        setLoadingTargeted(false);
      }
    }
  };

  const runEvaluation = async (answerText: string) => {
    if (!activeQuestion) return message.warning('请先生成面试题');
    if (evaluationBusy.current) return;
    const submittedAnswer = answerText.trim();
    if (!submittedAnswer) return message.warning('请填写回答');

    evaluationBusy.current = true;
    const generation = ++evaluationGeneration.current;
    setEvaluating(true);
    try {
      const data = await evaluateInterviewAnswer({
        target_role: targetRole,
        question: activeQuestion,
        user_answer: submittedAnswer,
        focus_area: activeFocus
      });
      if (generation !== evaluationGeneration.current) return;
      setEvaluation(data);
      try {
        const historyResponse = await fetchInterviewHistory();
        if (generation === evaluationGeneration.current) setHistory(historyResponse.data);
      } catch {
        if (generation === evaluationGeneration.current) message.warning('评分已保存，历史记录暂时无法刷新');
      }
    } catch (error) {
      if (generation === evaluationGeneration.current) message.error(getErrorMessage(error, '回答评估失败'));
    } finally {
      if (generation === evaluationGeneration.current) {
        evaluationBusy.current = false;
        setEvaluating(false);
      }
    }
  };

  const submitAnswer = async () => {
    setVoiceAnswer(null);
    await runEvaluation(answer);
  };

  const handleRecorded = async (blob: Blob) => {
    if (!activeQuestion) {
      message.warning('请先生成面试题');
      return;
    }

    const generation = ++voiceGeneration.current;
    setSttLoading(true);
    try {
      const file = await recordedBlobToWavFile(blob);
      const response = await speechToText(file);
      if (generation !== voiceGeneration.current) return;
      const spokenAnswer = response.text?.trim();
      if (spokenAnswer) {
        setAnswer(spokenAnswer);
        setVoiceAnswer(spokenAnswer);
      } else {
        message.warning(response.error || '语音转写失败');
      }
    } catch (error) {
      if (generation === voiceGeneration.current) message.error(getErrorMessage(error, '语音处理失败'));
    } finally {
      if (generation === voiceGeneration.current) setSttLoading(false);
    }
  };

  return (
    <div className="interview-page story-page">
      <section className="module-hero interview-hero">
        <div>
          <Tag className="hero-kicker" icon={<SoundOutlined />}>
            AI Mock Interview
          </Tag>
          <Typography.Title>把面试准备变成可复盘的能力训练</Typography.Title>
          <Typography.Paragraph>
            根据目标岗位生成题组、弱点定向追问和结构化反馈，用评分、建议与参考答案帮助你持续优化表达。
          </Typography.Paragraph>
        </div>
        <div className="module-hero-stats">
          <div>
            <span>题目数</span>
            <strong>{questions.length || '--'}</strong>
          </div>
          <div>
            <span>最近评分</span>
            <strong>{history[0]?.score ?? '--'}</strong>
          </div>
          <div>
            <span>目标岗位</span>
            <strong>{targetRole || '待选择'}</strong>
          </div>
        </div>
      </section>

      <GrowthJourney current="interview" />

      <div className="story-focus-strip" aria-live="polite">
        <span>当前训练阶段</span>
        <strong>{evaluation ? '复盘本题反馈' : activeQuestion ? '回答当前题目' : '生成目标岗位题目'}</strong>
        <span>{activeQuestion ? activeFocus : '先确定岗位与考察重点'}</span>
      </div>

      <Card className="interview-controls" variant="borderless">
        <Space wrap size={12} className="interview-control-row">
          <Input value={targetRole} onChange={(event) => changeTargetRole(event.target.value)} placeholder="目标岗位" />
          <Input
            value={focusTopics}
            onChange={(event) => setFocusTopics(event.target.value)}
            placeholder="考察重点"
            className="focus-input"
          />
          <Button type="primary" icon={<RocketOutlined />} loading={loadingQuestions} disabled={loadingTargeted} onClick={() => void generateQuestions()}>
            生成岗位面试题组
          </Button>
          <Button icon={<BulbOutlined />} loading={loadingTargeted} disabled={loadingQuestions} onClick={() => void generateTargeted()}>
            生成弱点定向追问
          </Button>
        </Space>
        <Progress
          className="interview-progress"
          percent={activeQuestion ? Math.round(((questions.findIndex((item) => item.id === selectedQuestion?.id) + 1) / Math.max(questions.length, 1)) * 100) : 0}
          showInfo={false}
          strokeColor={{ '0%': '#38bdf8', '100%': '#2563eb' }}
        />
      </Card>

      <div className="interview-grid">
        <Card title="题目" className="question-card" variant="borderless">
          {(loadingQuestions || loadingTargeted) && <Spin className="center-spin" />}
          {!loadingQuestions && !loadingTargeted && !activeQuestion && (
            <Empty description="还没有面试题">
              <Button type="primary" icon={<RocketOutlined />} onClick={() => void generateQuestions()}>
                生成岗位面试题组
              </Button>
            </Empty>
          )}
          {targeted && (
            <Alert
              type="info"
              showIcon
              message={`${targeted.question_data.difficulty} · ${targeted.question_data.focus_topic}`}
              description={targeted.question_data.background_context}
              className="question-alert"
            />
          )}
          {activeQuestion && (
            <div className="active-question">
              <Tag color="cyan">{activeFocus}</Tag>
              <Typography.Title level={4}>{activeQuestion}</Typography.Title>
              {activeAudioUrl && audioStatus === 'pending' && <Typography.Text type="secondary">语音生成中，可先阅读题目作答…</Typography.Text>}
              {activeAudioUrl && (audioStatus === 'failed' || audioStatus === 'expired') && <Typography.Text type="secondary">语音暂不可用，请使用文字题目继续练习。</Typography.Text>}
              {activeAudioUrl && audioStatus === 'success' && (
                <audio controls src={getStaticAssetUrl(activeAudioUrl)} className="question-audio">
                  <track kind="captions" />
                </audio>
              )}
            </div>
          )}
          <List
            className="question-list"
            dataSource={questions}
            renderItem={(question) => (
              <List.Item
                className={question.id === selectedId && !targeted ? 'is-selected' : ''}
                onClick={() => {
                  setSelectedId(question.id);
                  setTargeted(null);
                  invalidateAnswer();
                }}
                role="button"
                tabIndex={0}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    setSelectedId(question.id);
                    setTargeted(null);
                    invalidateAnswer();
                  }
                }}
              >
                <Space>
                  <Tag className="gradient-tag">Q{question.id}</Tag>
                  <Typography.Text>{question.topic}</Typography.Text>
                </Space>
              </List.Item>
            )}
          />
        </Card>

        <Card title="回答" className="answer-card" variant="borderless">
          <Input.TextArea
            value={answer}
            disabled={evaluating || sttLoading}
            onChange={(event) => {
              setVoiceAnswer(null);
              setAnswer(event.target.value);
            }}
            autoSize={{ minRows: 10, maxRows: 16 }}
            placeholder="输入或录入你的回答，建议用 STAR 结构说明背景、任务、行动和结果"
          />
          {voiceAnswer && (
            <Alert
              className="voice-answer-preview"
              type="info"
              showIcon
              message="语音已转写，请核对后提交"
              description={voiceAnswer}
            />
          )}
          <div className="answer-actions">
            <AudioRecorder onRecorded={handleRecorded} loading={sttLoading || evaluating} />
            <Button type="primary" icon={<CheckCircleOutlined />} loading={evaluating} disabled={sttLoading} onClick={() => void submitAnswer()}>
              提交回答并获取评估
            </Button>
          </div>
        </Card>

        <Card title="反馈" className="evaluation-card" variant="borderless">
          {!evaluation && <Empty description="提交回答后会展示评分、改进建议和 AI 参考答案" />}
          {evaluation && (
            <div className="evaluation-content">
              <Progress type="circle" percent={evaluation.score} strokeColor="#147c80" />
              <div>
                <Typography.Title level={4}>面试官评价</Typography.Title>
                <Typography.Paragraph>{evaluation.evaluation}</Typography.Paragraph>
                <Alert type="warning" showIcon message="改进建议" description={evaluation.improvement_suggestion} />
                <Collapse
                  ghost
                  items={[
                    {
                      key: 'reference',
                      label: 'AI 参考答案',
                      children: <Typography.Paragraph>{evaluation.reference_answer}</Typography.Paragraph>
                    }
                  ]}
                />
              </div>
            </div>
          )}
        </Card>

        <Card title="历史复盘" className="history-card" variant="borderless">
          <List
            dataSource={history.slice(0, 5)}
            locale={{ emptyText: '暂无复盘记录' }}
            renderItem={(item) => (
              <List.Item>
                <List.Item.Meta
                  title={
                <Space>
                  <Tag color={item.score >= 80 ? 'green' : item.score >= 60 ? 'gold' : 'red'}>{item.score}</Tag>
                  <FieldTimeOutlined />
                  <Typography.Text ellipsis>{item.question}</Typography.Text>
                </Space>
                  }
                  description={item.improvement_suggestion}
                />
              </List.Item>
            )}
          />
        </Card>
      </div>
    </div>
  );
}
