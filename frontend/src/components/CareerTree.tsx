import { Empty } from 'antd';
import type { EChartsOption } from 'echarts';
import { useMemo } from 'react';
import type { CareerGraphData, CareerLevel, GraphData } from '../api/types';
import { ChartCanvas } from './ChartCanvas';

function isCareerGraphData(data?: GraphData | null): data is CareerGraphData {
  return Boolean(data && Array.isArray((data as CareerGraphData).levels));
}

function formatSkillLine(level: CareerLevel) {
  return level.coreSkills?.map((skill) => `${skill.isMastered ? '已掌握' : '待补齐'} ${skill.name}`).join('<br/>') || '';
}

function makeTree(levels: CareerLevel[]) {
  const hasLinks = levels.some((level) => level.nextLevels?.length);
  const map = new Map(levels.map((level) => [level.id, level]));

  if (!hasLinks) {
    const buildChain = (index: number): Record<string, unknown> => {
      const level = levels[index];
      return {
        name: `${level.level} ${level.title}`,
        value: level.salaryRange,
        itemStyle: { color: level.status === 'acquired' ? '#14b8a6' : '#7c3aed' },
        level,
        children: levels[index + 1] ? [buildChain(index + 1)] : []
      };
    };
    return levels[0] ? [buildChain(0)] : [];
  }

  const linked = new Set<string>();
  levels.forEach((level) => level.nextLevels?.forEach((id) => linked.add(id)));

  const buildNode = (level: CareerLevel): Record<string, unknown> => ({
    name: `${level.level} ${level.title}`,
    value: level.salaryRange,
    itemStyle: { color: level.status === 'acquired' ? '#14b8a6' : '#7c3aed' },
    level,
    children: level.nextLevels?.map((id) => map.get(id)).filter(Boolean).map((child) => buildNode(child as CareerLevel)) || []
  });

  return levels.filter((level) => !linked.has(level.id)).map(buildNode);
}

export function CareerTree({ data }: { data?: GraphData | null }) {
  const option = useMemo<EChartsOption | null>(() => {
    if (!isCareerGraphData(data) || data.levels.length === 0) return null;

    return {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'item',
        borderWidth: 0,
        backgroundColor: 'rgba(255,255,255,0.96)',
        textStyle: { color: '#15202b' },
        formatter: (params: unknown) => {
          const item = Array.isArray(params) ? params[0] : params;
          const typedItem = item as { data?: { level?: CareerLevel }; name?: string };
          const level = typedItem.data?.level;
          if (!level) return typedItem.name || '';
          return `<b>${level.level} ${level.title}</b><br/>薪资：${level.salaryRange}<br/>状态：${
            level.status === 'acquired' ? '已具备' : '待补齐'
          }<br/>${formatSkillLine(level)}`;
        }
      },
      series: [
        {
          type: 'tree',
          data: makeTree(data.levels),
          top: '8%',
          left: '6%',
          bottom: '8%',
          right: '20%',
          symbolSize: 18,
          orient: 'LR',
          roam: true,
          initialTreeDepth: 4,
          lineStyle: {
            width: 2,
            color: '#9fb8e8',
            curveness: 0.18
          },
          label: {
            position: 'left',
            verticalAlign: 'middle',
            align: 'right',
            color: '#10233f',
            fontSize: 13,
            fontWeight: 600
          },
          leaves: {
            label: {
              position: 'right',
              align: 'left'
            }
          },
          emphasis: {
            focus: 'descendant'
          }
        }
      ]
    };
  }, [data]);

  if (!option) {
    return <Empty className="panel-empty" description="等待职业图谱" />;
  }

  return <ChartCanvas option={option} className="chart-canvas tree-chart" />;
}
