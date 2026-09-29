import { Timeline, Typography } from 'antd';
import type { LearningPathResponse } from '../api/types';

export function RoadmapTimeline({ data }: { data: LearningPathResponse }) {
  return (
    <div className="roadmap-timeline">
      <Typography.Title level={4}>{data.target_role}</Typography.Title>
      <Typography.Paragraph className="muted-text">{data.summary}</Typography.Paragraph>
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
