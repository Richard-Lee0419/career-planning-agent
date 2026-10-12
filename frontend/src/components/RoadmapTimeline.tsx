import { Timeline, Typography } from 'antd';
import type { LearningPathResponse } from '../api/types';
import { StandardSourceNote } from './StandardSourceNote';

export function RoadmapTimeline({ data }: { data: LearningPathResponse }) {
  return (
    <div className="roadmap-timeline">
      <Typography.Title level={4}>{data.target_role}</Typography.Title>
      <Typography.Paragraph className="muted-text">{data.summary}</Typography.Paragraph>
      <StandardSourceNote source={data.standard_source} notice={data.standard_notice || (data.standard_source ? 'AI 生成的任务与资源需要自行核对。' : '此路径未保存标准来源；AI 生成的任务与资源需要自行核对。')} />
      <Timeline
        mode="left"
        items={data.milestones.map((milestone) => ({
          label: milestone.period,
          color: '#2563eb',
          children: (
            <div className="timeline-block">
              <Typography.Text strong>{milestone.phase}</Typography.Text>
              <div className="timeline-list">{milestone.focus_targets.join(' / ')}</div>
              <div className="timeline-resources">{milestone.recommended_resources.join(' · ')}</div>
            </div>
          )
        }))}
      />
      <Typography.Paragraph className="roadmap-conclusion">{data.conclusion}</Typography.Paragraph>
    </div>
  );
}
