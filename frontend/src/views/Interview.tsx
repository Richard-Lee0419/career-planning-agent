import { useEffect, useMemo, useState } from 'react';
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
  fetchInterviewHistory,
  fetchInterviewQuestions,
  fetchTargetedQuestion,
  speechToText
} from '../api/interview';
import { getErrorMessage, getStaticAssetUrl } from '../api/client';
import type { GeneralQuestionItem, InterviewHistoryItem, MockEvaluation, TargetedInterviewResponse } from '../api/types';
import { AudioRecorder } from '../components/AudioRecorder';
import { recordedBlobToWavFile } from '../utils/audio';

export default function Interview() {
  const [targetRole, setTargetRole] = useState('前端工程师');
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

  useEffect(() => {
    void fetchInterviewHistory()
      .then((response) => setHistory(response.data))
      .catch(() => setHistory([]));
  }, []);

  const selectedQuestion = useMemo(
    () => questions.find((question) => question.id === selectedId) || questions[0],
    [questions, selectedId]
  );

  const activeQuestion = targeted?.question_data.question || selectedQuestion?.question || '';
  const activeFocus = targeted?.question_data.focus_topic || selectedQuestion?.topic || '综合能力';
  const activeAudioUrl = targeted?.audio_url || selectedQuestion?.audio_url;

  const generateQuestions = async () => {
    setLoadingQuestions(true);
    setTargeted(null);
    setEvaluation(null);
    try {
      const data = await fetchInterviewQuestions(targetRole.trim(), focusTopics.trim());
      setQuestions(data.questions);
      setSelectedId(data.questions[0]?.id ?? null);
      setAnswer('');
      setVoiceAnswer(null);
    } catch (error) {
      message.error(getErrorMessage(error, '面试题生成失败'));
    } finally {
      setLoadingQuestions(false);
    }
  };

  const generateTargeted = async () => {
    setLoadingTargeted(true);
    setEvaluation(null);
    try {
      const data = await fetchTargetedQuestion(targetRole.trim());
      setTargeted(data);
      setAnswer('');
      setVoiceAnswer(null);
    } catch (error) {
      message.error(getErrorMessage(error, '定向题生成失败'));
    } finally {
      setLoadingTargeted(false);
    }
  };

  const runEvaluation = async (answerText: string) => {
    if (!activeQuestion) return message.warning('请先生成面试题');
    const submittedAnswer = answerText.trim();
    if (!submittedAnswer) return message.warning('请填写回答');

    setEvaluating(true);
    try {
      const data = await evaluateInterviewAnswer({
        target_role: targetRole,
        question: activeQuestion,
        user_answer: submittedAnswer,
        focus_area: activeFocus
      });
      setEvaluation(data);
      const historyResponse = await fetchInterviewHistory();
      setHistory(historyResponse.data);
    } catch (error) {
      message.error(getErrorMessage(error, '回答评估失败'));
    } finally {
      setEvaluating(false);
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

    setSttLoading(true);
    try {
      const file = await recordedBlobToWavFile(blob);
      const response = await speechToText(file);
      const spokenAnswer = response.text?.trim();
      if (spokenAnswer) {
        setAnswer('');
        setVoiceAnswer(spokenAnswer);
        await runEvaluation(spokenAnswer);
      } else {
        message.warning(response.error || '语音转写失败');
      }
    } catch (error) {
      message.error(getErrorMessage(error, '语音处理失败'));
    } finally {
      setSttLoading(false);
    }
  };

  return (
    <div className="interview-page">
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
            <strong>{targetRole}</strong>
          </div>
        </div>
      </section>

      <Card className="interview-controls" variant="borderless">
        <Space wrap size={12} className="interview-control-row">
          <Input value={targetRole} onChange={(event) => setTargetRole(event.target.value)} placeholder="目标岗位" />
          <Input
            value={focusTopics}
            onChange={(event) => setFocusTopics(event.target.value)}
            placeholder="考察重点"
            className="focus-input"
          />
          <Button type="primary" icon={<RocketOutlined />} loading={loadingQuestions} onClick={() => void generateQuestions()}>
            生成岗位面试题组
          </Button>
          <Button icon={<BulbOutlined />} loading={loadingTargeted} onClick={() => void generateTargeted()}>
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
              {activeAudioUrl && (
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
                  setEvaluation(null);
                  setVoiceAnswer(null);
                  setAnswer('');
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
              message="语音回答已提交"
              description={voiceAnswer}
            />
          )}
          <div className="answer-actions">
            <AudioRecorder onRecorded={handleRecorded} loading={sttLoading} />
            <Button type="primary" icon={<CheckCircleOutlined />} loading={evaluating} onClick={() => void submitAnswer()}>
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
