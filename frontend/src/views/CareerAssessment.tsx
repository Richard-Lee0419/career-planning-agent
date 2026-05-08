import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Alert,
  Button,
  Card,
  Checkbox,
  Form,
  Input,
  Modal,
  Progress,
  Radio,
  Space,
  Steps,
  Tag,
  Typography,
  message
} from 'antd';
import {
  ArrowLeftOutlined,
  ArrowRightOutlined,
  CheckCircleOutlined,
  CloudSyncOutlined,
  CompassOutlined,
  SaveOutlined,
  ThunderboltOutlined
} from '@ant-design/icons';
import { extractProfileFromText } from '../api/profile';
import { getErrorMessage } from '../api/client';
import { buildAssessmentProfileText } from '../utils/careerPlan';

const DRAFT_KEY = 'career-assessment-draft';

const interestOptions = ['产品设计', '技术开发', '数据分析', 'AI 应用', '内容运营', '教育培训', '商业分析', '创意表达'];
const skillOptions = ['沟通表达', 'Python', 'JavaScript', 'SQL', 'Office/Excel', '项目管理', '用户研究', '视频剪辑'];
const softSkillOptions = ['逻辑分析', '主动学习', '团队协作', '抗压复盘', '同理心', '执行力'];
const targetOptions = ['产品经理', '前端工程师', '数据分析师', 'AI 应用工程师', '运营增长', '后端工程师'];

const steps = [
  {
    title: '第 1 步：了解你的基本情况',
    description: '用于建立职业画像的基础信息。',
    fields: ['name', 'education', 'major', 'grade']
  },
  {
    title: '第 2 步：分析你的兴趣与能力',
    description: '选择你感兴趣、已具备或愿意投入的方向。',
    fields: ['interests', 'skills', 'softSkills']
  },
  {
    title: '第 3 步：确认职业目标与经历',
    description: '让 AI 结合真实经历判断岗位匹配度。',
    fields: ['targetRoles', 'experience']
  },
  {
    title: '第 4 步：生成 AI 职业画像',
    description: '确认信息后，系统会分析兴趣、能力与职业倾向。',
    fields: ['weeklyTime', 'concerns']
  }
];

function OptionGrid({ options }: { options: string[] }) {
  return (
    <div className="assessment-option-grid">
      {options.map((option) => (
        <Checkbox value={option} className="assessment-option-card" key={option}>
          {option}
        </Checkbox>
      ))}
    </div>
  );
}

export default function CareerAssessment() {
  const [form] = Form.useForm();
  const navigate = useNavigate();
  const [currentStep, setCurrentStep] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [lastSavedAt, setLastSavedAt] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    const raw = localStorage.getItem(DRAFT_KEY);
    if (!raw) return;
    try {
      const draft = JSON.parse(raw) as { values?: Record<string, unknown>; step?: number; updatedAt?: string };
      if (draft.values) form.setFieldsValue(draft.values);
      if (typeof draft.step === 'number') setCurrentStep(Math.min(Math.max(draft.step, 0), steps.length - 1));
      if (draft.updatedAt) setLastSavedAt(draft.updatedAt);
    } catch {
      localStorage.removeItem(DRAFT_KEY);
    }
  }, [form]);

  useEffect(() => {
    const beforeUnload = (event: BeforeUnloadEvent) => {
      if (!dirty || submitting) return;
      event.preventDefault();
    };
    window.addEventListener('beforeunload', beforeUnload);
    return () => window.removeEventListener('beforeunload', beforeUnload);
  }, [dirty, submitting]);

  const progress = useMemo(() => Math.round(((currentStep + 1) / steps.length) * 100), [currentStep]);

  const saveDraft = () => {
    const updatedAt = new Date().toLocaleString();
    localStorage.setItem(
      DRAFT_KEY,
      JSON.stringify({
        values: form.getFieldsValue(true),
        step: currentStep,
        updatedAt
      })
    );
    setLastSavedAt(updatedAt);
    setDirty(false);
    message.success('测评进度已保存');
  };

  const goNext = async () => {
    await form.validateFields(steps[currentStep].fields);
    saveDraft();
    setCurrentStep((step) => Math.min(step + 1, steps.length - 1));
  };

  const submitAssessment = async () => {
    await form.validateFields();
    Modal.confirm({
      title: '确认生成你的 AI 职业画像？',
      content: '系统将根据本次测评信息更新个人画像，并进入职业推荐结果页。生成过程中请不要关闭页面。',
      okText: '生成我的职业画像',
      cancelText: '返回修改测评信息',
      centered: true,
      onOk: async () => {
        setSubmitting(true);
        try {
          const text = buildAssessmentProfileText(form.getFieldsValue(true));
          await extractProfileFromText(text);
          localStorage.removeItem(DRAFT_KEY);
          setDirty(false);
          message.success('职业画像已生成');
          navigate('/recommendations', { replace: true });
        } catch (error) {
          message.error(getErrorMessage(error, '职业画像生成失败，请稍后重试'));
        } finally {
          setSubmitting(false);
        }
      }
    });
  };

  const renderStep = () => {
    if (currentStep === 0) {
      return (
        <div className="assessment-fields-grid">
          <Form.Item name="name" label="你的姓名" rules={[{ required: true, message: '请填写姓名或昵称' }]}>
            <Input size="large" placeholder="例如：李同学" />
          </Form.Item>
          <Form.Item name="education" label="当前学历" rules={[{ required: true, message: '请选择当前学历' }]}>
            <Radio.Group optionType="button" buttonStyle="solid">
              <Radio.Button value="本科">本科</Radio.Button>
              <Radio.Button value="硕士">硕士</Radio.Button>
              <Radio.Button value="专科">专科</Radio.Button>
              <Radio.Button value="高中/中职">高中/中职</Radio.Button>
            </Radio.Group>
          </Form.Item>
          <Form.Item name="major" label="所学专业" rules={[{ required: true, message: '请填写专业' }]}>
            <Input size="large" placeholder="例如：计算机科学与技术" />
          </Form.Item>
          <Form.Item name="grade" label="当前阶段" rules={[{ required: true, message: '请选择当前阶段' }]}>
            <Radio.Group optionType="button" buttonStyle="solid">
              <Radio.Button value="大一/研一">大一/研一</Radio.Button>
              <Radio.Button value="大二/研二">大二/研二</Radio.Button>
              <Radio.Button value="大三">大三</Radio.Button>
              <Radio.Button value="大四/毕业">大四/毕业</Radio.Button>
            </Radio.Group>
          </Form.Item>
          <Form.Item name="location" label="期望发展城市">
            <Input size="large" placeholder="例如：上海 / 杭州 / 远程" />
          </Form.Item>
        </div>
      );
    }

    if (currentStep === 1) {
      return (
        <Space direction="vertical" size={18} className="full-width">
          <Form.Item name="interests" label="你感兴趣的方向" rules={[{ required: true, message: '请至少选择 1 个兴趣方向' }]}>
            <Checkbox.Group className="full-width">
              <OptionGrid options={interestOptions} />
            </Checkbox.Group>
          </Form.Item>
          <Form.Item name="skills" label="你目前具备的技能" rules={[{ required: true, message: '请至少选择 1 项当前技能' }]}>
            <Checkbox.Group className="full-width">
              <OptionGrid options={skillOptions} />
            </Checkbox.Group>
          </Form.Item>
          <Form.Item name="softSkills" label="你的优势特质">
            <Checkbox.Group className="full-width">
              <OptionGrid options={softSkillOptions} />
            </Checkbox.Group>
          </Form.Item>
        </Space>
      );
    }

    if (currentStep === 2) {
      return (
        <Space direction="vertical" size={18} className="full-width">
          <Form.Item name="targetRoles" label="你想重点探索的职业方向" rules={[{ required: true, message: '请至少选择 1 个职业方向' }]}>
            <Checkbox.Group className="full-width">
              <OptionGrid options={targetOptions} />
            </Checkbox.Group>
          </Form.Item>
          <Form.Item name="experience" label="项目、实习或实践经历" rules={[{ required: true, message: '请简要描述一段经历，暂无也可说明想补齐的经历' }]}>
            <Input.TextArea
              autoSize={{ minRows: 5, maxRows: 8 }}
              placeholder="例如：做过课程项目、社团活动、比赛、实习、个人作品，或当前还没有实践经历"
            />
          </Form.Item>
        </Space>
      );
    }

    return (
      <Space direction="vertical" size={18} className="full-width">
        <Alert
          type="info"
          showIcon
          message="最后确认"
          description="提交后会进入 AI 分析阶段，系统将更新你的个人画像，并为你生成职业推荐与学习路径入口。"
        />
        <Form.Item name="weeklyTime" label="未来每周可投入学习时间" rules={[{ required: true, message: '请选择可投入时间' }]}>
          <Radio.Group optionType="button" buttonStyle="solid">
            <Radio.Button value="每周 3-5 小时">每周 3-5 小时</Radio.Button>
            <Radio.Button value="每周 6-10 小时">每周 6-10 小时</Radio.Button>
            <Radio.Button value="每周 10 小时以上">每周 10 小时以上</Radio.Button>
          </Radio.Group>
        </Form.Item>
        <Form.Item name="concerns" label="你当前最想解决的问题">
          <Input.TextArea autoSize={{ minRows: 4, maxRows: 7 }} placeholder="例如：不知道适合什么岗位、缺少项目经历、不清楚如何准备实习" />
        </Form.Item>
      </Space>
    );
  };

  return (
    <div className="page-stack assessment-page">
      <section className="module-hero assessment-hero">
        <div>
          <Tag className="hero-kicker" icon={<CompassOutlined />}>
            Career Assessment
          </Tag>
          <Typography.Title>AI 职业测评：先认识你，再推荐方向</Typography.Title>
          <Typography.Paragraph>
            用 4 个步骤梳理基本信息、兴趣能力、目标方向和成长约束，生成可用于职业推荐、学习路径和 AI 顾问对话的个人画像。
          </Typography.Paragraph>
        </div>
        <div className="module-hero-stats">
          <div>
            <span>当前步骤</span>
            <strong>{currentStep + 1}/4</strong>
          </div>
          <div>
            <span>完成进度</span>
            <strong>{progress}%</strong>
          </div>
          <div>
            <span>下一站</span>
            <strong>职业推荐</strong>
          </div>
        </div>
      </section>

      <Card className="assessment-card" variant="borderless">
        <div className="assessment-layout">
          <aside className="assessment-side">
            <Progress percent={progress} showInfo={false} strokeColor={{ '0%': '#5eead4', '100%': '#2563eb' }} />
            <Steps
              direction="vertical"
              current={currentStep}
              items={steps.map((step) => ({
                title: step.title.replace('第 ', '').replace(' 步：', '. '),
                description: step.description
              }))}
            />
            <div className="draft-status">
              <SaveOutlined />
              <span>{lastSavedAt ? `上次保存：${lastSavedAt}` : '填写过程中可随时保存进度'}</span>
            </div>
          </aside>

          <main className="assessment-main">
            <Tag className="gradient-tag">我是谁 → 适合什么 → 缺什么 → 如何提升</Tag>
            <Typography.Title level={3}>{steps[currentStep].title}</Typography.Title>
            <Typography.Paragraph type="secondary">{steps[currentStep].description}</Typography.Paragraph>

            <Form
              form={form}
              layout="vertical"
              requiredMark={false}
              onValuesChange={() => setDirty(true)}
              disabled={submitting}
            >
              {renderStep()}
            </Form>

            {submitting && (
              <Alert
                className="assessment-loading-alert"
                type="success"
                showIcon
                icon={<CloudSyncOutlined spin />}
                message="正在分析你的兴趣、能力与职业倾向"
                description="AI 正在生成职业画像和推荐依据，完成后会自动进入推荐结果页。"
              />
            )}

            <div className="assessment-actions">
              <Button icon={<SaveOutlined />} onClick={saveDraft} disabled={submitting}>
                保存本次测评进度
              </Button>
              <Space wrap>
                <Button
                  icon={<ArrowLeftOutlined />}
                  disabled={currentStep === 0 || submitting}
                  onClick={() => setCurrentStep((step) => Math.max(step - 1, 0))}
                >
                  返回上一组问题
                </Button>
                {currentStep < steps.length - 1 ? (
                  <Button type="primary" icon={<ArrowRightOutlined />} onClick={() => void goNext()}>
                    {currentStep === 0 ? '继续分析兴趣与能力' : currentStep === 1 ? '继续确认职业目标' : '进入画像生成确认'}
                  </Button>
                ) : (
                  <Button
                    type="primary"
                    icon={<CheckCircleOutlined />}
                    loading={submitting}
                    onClick={() => void submitAssessment()}
                  >
                    生成我的职业画像
                  </Button>
                )}
              </Space>
            </div>
          </main>
        </div>
      </Card>
    </div>
  );
}
