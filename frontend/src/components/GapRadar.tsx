import { useMemo } from 'react';
import type { EChartsOption } from 'echarts';
import type { GapAnalysisResponse } from '../api/types';
import { ChartCanvas } from './ChartCanvas';

export function GapRadar({ data }: { data: GapAnalysisResponse }) {
  const option = useMemo<EChartsOption>(
    () => ({
      backgroundColor: 'transparent',
      tooltip: {},
      radar: {
        radius: '66%',
        splitNumber: 4,
        axisName: { color: '#10233f', fontWeight: 700 },
        splitLine: { lineStyle: { color: ['rgba(120,151,190,0.28)'] } },
        splitArea: { areaStyle: { color: ['rgba(56, 189, 248, 0.06)', 'rgba(37, 99, 235, 0.1)'] } },
        axisLine: { lineStyle: { color: 'rgba(96, 165, 250, 0.42)' } },
        indicator: [
          { name: '基础素质', max: 100 },
          { name: '专业技能', max: 100 },
          { name: '职业素养', max: 100 },
          { name: '发展潜力', max: 100 }
        ]
      },
      series: [
        {
          type: 'radar',
          data: [
            {
              value: [
                data.basic_matching.score,
                data.skill_matching.score,
                data.soft_skill_matching.score,
                data.potential_matching.score
              ],
              name: data.target_role,
              areaStyle: { color: 'rgba(37, 99, 235, 0.22)' },
              lineStyle: { color: '#2563eb', width: 3, shadowBlur: 12, shadowColor: 'rgba(37,99,235,0.34)' },
              itemStyle: { color: '#38bdf8', borderColor: '#fff', borderWidth: 2 }
            }
          ]
        }
      ]
    }),
    [data]
  );

  return <ChartCanvas option={option} className="chart-canvas radar-chart" />;
}
