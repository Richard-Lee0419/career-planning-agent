import { Progress, Space, Typography } from 'antd';
import type { GapAnalysisResponse } from '../api/types';

export function GapRadar({ data }: { data: GapAnalysisResponse }) {
  return (
    <Space direction="vertical" size={16} className="full-width">
      <div>
        <Typography.Text strong>核心技能要求覆盖率</Typography.Text>
        <Progress percent={data.skill_coverage} strokeColor={{ '0%': '#5eead4', '100%': '#2563eb' }} />
      </div>
      <div>
        <Typography.Text strong>软素质要求覆盖率</Typography.Text>
        {data.soft_skill_coverage === null
          ? <Typography.Paragraph type="secondary">岗位标准未列出软素质要求</Typography.Paragraph>
          : <Progress percent={data.soft_skill_coverage} strokeColor={{ '0%': '#5eead4', '100%': '#2563eb' }} />}
      </div>
      <Typography.Text type="secondary">覆盖率只统计画像中已填写且与岗位标准直接匹配的要求。</Typography.Text>
    </Space>
  );
}
