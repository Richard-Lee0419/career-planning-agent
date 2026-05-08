import { useState } from 'react';
import { Alert, Button, Card, Col, Form, Input, Progress, Row, Skeleton, Space, Tag, Typography, Upload, message, Modal } from 'antd';
import type { UploadRequestOption } from 'rc-upload/lib/interface';
import {
  CloudSyncOutlined,
  CompassOutlined,
  InboxOutlined,
  ProfileOutlined,
  RadarChartOutlined,
  TagsOutlined
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { extractProfileFromText, syncProfileFromChat, uploadResume } from '../api/profile';
import { getErrorMessage } from '../api/client';
import { useProfile } from '../hooks/useProfile';

const { Dragger } = Upload;

interface ResumeFormValues {
  resumeText: string;
}

function TagCloud({ title, items, color }: { title: string; items?: string[]; color?: string }) {
  return (
    <div className="tag-section">
      <Typography.Text strong>{title}</Typography.Text>
      <div className="tag-cloud">
        {(items || []).length > 0 ? (
          items?.map((item) => (
            <Tag color={color} className={!color ? 'gradient-tag' : undefined} key={item}>
              {item}
            </Tag>
          ))
        ) : (
          <Typography.Text type="secondary">暂无</Typography.Text>
        )}
      </div>
    </div>
  );
}

export default function Profile() {
  const navigate = useNavigate();
  const { profile, loading, error, reload } = useProfile();
  const [extracting, setExtracting] = useState(false);
  const [syncing, setSyncing] = useState(false);

  const extractProfile = async (values: ResumeFormValues) => {
    if (!values.resumeText?.trim()) return message.warning('请粘贴简历或自我介绍文本');
    setExtracting(true);
    try {
      await extractProfileFromText(values.resumeText.trim());
      await reload();
      message.success('画像已更新');
    } catch (requestError) {
      message.error(getErrorMessage(requestError, '画像解析失败'));
    } finally {
      setExtracting(false);
    }
  };

  const customUpload = async (options: UploadRequestOption) => {
    const file = options.file as File;
    try {
      await uploadResume(file);
      options.onSuccess?.({}, file);
      await reload();
      message.success('简历解析完成');
    } catch (requestError) {
      options.onError?.(requestError as Error);
      message.error(getErrorMessage(requestError, '上传解析失败'));
    }
  };

  const runSync = async () => {
    setSyncing(true);
    try {
      const response = await syncProfileFromChat();
      await reload();
      Modal.success({
        title: '智能同步完成',
        content: (
          <div className="sync-modal-content">
            <Typography.Paragraph>{response.message}</Typography.Paragraph>
            <Typography.Text strong>新评分：{response.new_score}</Typography.Text>
            <TagCloud title="新增技能" items={response.detected_updates.current_skills} color="cyan" />
            <TagCloud title="新增证书" items={response.detected_updates.certificates} color="gold" />
          </div>
        )
      });
    } catch (requestError) {
      message.error(getErrorMessage(requestError, '智能同步失败'));
    } finally {
      setSyncing(false);
    }
  };

  if (loading) return <Skeleton active paragraph={{ rows: 12 }} />;

  return (
    <div className="page-stack">
      {error && <Alert type="info" showIcon message={error} />}
      <section className="module-hero profile-module-hero">
        <div>
          <Tag className="hero-kicker" icon={<RadarChartOutlined />}>
            Capability Profile
          </Tag>
          <Typography.Title>个人能力画像中心</Typography.Title>
          <Typography.Paragraph>
            从简历、对话和测评中沉淀你的专业能力、目标岗位、项目证据与成长潜力，让 AI 推荐更精准。
          </Typography.Paragraph>
          <Space className="hero-actions" wrap>
            <Button type="primary" icon={<RadarChartOutlined />} onClick={() => navigate('/assessment')}>
              重新进行 AI 职业测评
            </Button>
            <Button icon={<CompassOutlined />} onClick={() => navigate('/recommendations')}>
              查看推荐职业方向
            </Button>
          </Space>
        </div>
        <div className="module-hero-stats">
          <div>
            <span>竞争力评分</span>
            <strong>{profile?.competitiveness_score || 0}</strong>
          </div>
          <div>
            <span>技能标签</span>
            <strong>{profile?.current_skills.length || 0}</strong>
          </div>
          <div>
            <span>目标方向</span>
            <strong>{profile?.target_roles.length || 0}</strong>
          </div>
        </div>
      </section>

      <Row gutter={[18, 18]}>
        <Col xs={24} xl={9}>
          <Card className="profile-overview-card" variant="borderless">
            <div className="profile-hero">
              <Progress
                type="dashboard"
                percent={profile?.competitiveness_score || 0}
                strokeColor={{ '0%': '#38bdf8', '100%': '#2563eb' }}
              />
              <div>
                <Typography.Title level={3}>{profile?.name || '未设置姓名'}</Typography.Title>
                <Typography.Text type="secondary">
                  {profile?.education_level || '学历待完善'} · {profile?.major || '专业待完善'}
                </Typography.Text>
                <div className="profile-meta-line">{profile?.location || '地点待完善'}</div>
              </div>
            </div>
            <Space className="profile-actions" wrap>
              <Button type="primary" icon={<CloudSyncOutlined />} loading={syncing} onClick={() => void runSync()}>
                从 AI 对话同步画像
              </Button>
              <Button icon={<ProfileOutlined />} onClick={() => void reload()}>
                刷新个人画像
              </Button>
            </Space>
          </Card>
        </Col>
        <Col xs={24} xl={15}>
          <Card
            title={
              <Space>
                <CompassOutlined />
                <span>技能档案</span>
              </Space>
            }
            className="profile-detail-card"
            variant="borderless"
          >
            <Row gutter={[18, 18]}>
              <Col xs={24} md={12}>
                <TagCloud title="专业技能" items={profile?.current_skills} color="cyan" />
              </Col>
              <Col xs={24} md={12}>
                <TagCloud title="目标岗位" items={profile?.target_roles} color="blue" />
              </Col>
              <Col xs={24} md={12}>
                <TagCloud title="证书奖项" items={profile?.certificates} color="gold" />
              </Col>
              <Col xs={24} md={12}>
                <TagCloud title="软素质" items={profile?.soft_skills?.length ? profile.soft_skills : profile?.interests} color="green" />
              </Col>
            </Row>
          </Card>
        </Col>
      </Row>

      <Row gutter={[18, 18]}>
        <Col xs={24} lg={11}>
          <Card title="PDF 简历解析并更新画像" variant="borderless" className="profile-input-card">
            <Dragger
              accept=".pdf"
              multiple={false}
              maxCount={1}
              customRequest={(options) => void customUpload(options)}
              beforeUpload={(file) => {
                const isPdf = file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf');
                if (!isPdf) message.error('仅支持 PDF 文件');
                return isPdf || Upload.LIST_IGNORE;
              }}
            >
              <p className="ant-upload-drag-icon">
                <InboxOutlined />
              </p>
              <p className="ant-upload-text">上传 PDF 简历并更新职业画像</p>
              <p className="ant-upload-hint">系统会提取教育背景、技能、项目经历和目标方向</p>
            </Dragger>
          </Card>
        </Col>
        <Col xs={24} lg={13}>
          <Card title="文本信息解析并更新画像" variant="borderless" className="profile-input-card">
            <Form layout="vertical" onFinish={extractProfile} requiredMark={false}>
              <Form.Item name="resumeText" label="简历文本或自我介绍">
                <Input.TextArea autoSize={{ minRows: 8, maxRows: 14 }} placeholder="粘贴教育背景、项目经历、技能、证书与意向岗位" />
              </Form.Item>
              <Button type="primary" htmlType="submit" icon={<TagsOutlined />} loading={extracting}>
                AI 解析并更新职业画像
              </Button>
            </Form>
          </Card>
        </Col>
      </Row>

      <Card title="实践经历" variant="borderless" className="profile-detail-card">
        <Typography.Paragraph>{profile?.internship_experience || '暂无实践经历'}</Typography.Paragraph>
        {profile?.innovation_potential && (
          <Alert type="success" showIcon message="创新与学习潜力" description={profile.innovation_potential} />
        )}
      </Card>
    </div>
  );
}
