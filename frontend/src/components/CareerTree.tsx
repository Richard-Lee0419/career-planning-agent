import { Button, Empty, Tag, Typography } from 'antd';
import type { EChartsOption } from 'echarts';
import { useMemo, useState } from 'react';
import type { CareerGraphData, CareerLevel, GraphData } from '../api/types';
import { ChartCanvas } from './ChartCanvas';

export function isCareerGraphData(data?: GraphData | null): data is CareerGraphData {
  if (!data || !Array.isArray((data as CareerGraphData).levels)) return false;
  const levels = (data as CareerGraphData).levels;
  if (levels.length > 60) return false;
  return levels.every((level) =>
    level &&
    typeof level.id === 'string' &&
    typeof level.level === 'string' &&
    typeof level.title === 'string' &&
    typeof level.salaryRange === 'string' &&
    (level.status === 'acquired' || level.status === 'not acquired') &&
    Array.isArray(level.coreSkills) &&
    level.coreSkills.every((skill) => skill && typeof skill.name === 'string' && typeof skill.isMastered === 'boolean') &&
    (level.nextLevels === undefined || (Array.isArray(level.nextLevels) && level.nextLevels.every((id) => typeof id === 'string')))
  );
}

export function escapeHtml(value: string) {
  return value.replace(/[&<>"']/g, (char) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[char] || char);
}

function formatSkillLine(level: CareerLevel) {
  return level.coreSkills?.map((skill) => `${skill.isMastered ? '已掌握' : '待补齐'} ${escapeHtml(skill.name)}`).join('<br/>') || '';
}

export function makeTree(levels: CareerLevel[]) {
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
        children: index < 11 && levels[index + 1] ? [buildChain(index + 1)] : []
      };
    };
    return levels[0] ? [buildChain(0)] : [];
  }

  const linked = new Set<string>();
  levels.forEach((level) => level.nextLevels?.forEach((id) => linked.add(id)));

  const buildNode = (level: CareerLevel, path: Set<string>): Record<string, unknown> => {
    const visited = new Set(path);
    visited.add(level.id);
    return {
      name: `${level.level} ${level.title}`,
      value: level.salaryRange,
      itemStyle: { color: level.status === 'acquired' ? '#14b8a6' : '#7c3aed' },
      level,
      children: visited.size >= 12 ? [] : (level.nextLevels || [])
        .filter((id) => !visited.has(id) && map.has(id))
        .map((id) => buildNode(map.get(id) as CareerLevel, visited))
    };
  };

  return levels.filter((level) => !linked.has(level.id)).map((level) => buildNode(level, new Set()));
}

export function CareerTree({ data }: { data?: GraphData | null }) {
  const [listView, setListView] = useState(() => window.matchMedia('(max-width: 860px)').matches);
  const option = useMemo<EChartsOption | null>(() => {
    if (!isCareerGraphData(data) || data.levels.length === 0) return null;
    const tree = makeTree(data.levels);
    if (tree.length === 0) return null;

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
          if (!level) return escapeHtml(typedItem.name || '');
          return `<b>${escapeHtml(level.level)} ${escapeHtml(level.title)}</b><br/>薪资：${escapeHtml(level.salaryRange)}<br/>状态：${
            level.status === 'acquired' ? '已具备' : '待补齐'
          }<br/>${formatSkillLine(level)}`;
        }
      },
      series: [
        {
          type: 'tree',
          data: tree,
          top: '8%',
          left: '14%',
          bottom: '8%',
          right: '14%',
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
            position: 'top',
            verticalAlign: 'middle',
            align: 'center',
            color: '#10233f',
            fontSize: 12,
            fontWeight: 600,
            lineHeight: 17,
            distance: 14,
            formatter: (params: unknown) => {
              const level = (params as { data?: { level?: CareerLevel } })?.data?.level;
              return level ? `${level.level}\n${level.title}` : '';
            }
          },
          leaves: {
            label: {
              position: 'top',
              align: 'center'
            }
          },
          emphasis: {
            focus: 'descendant'
          }
        }
      ]
    };
  }, [data]);

  if (!option || !isCareerGraphData(data)) {
    return <Empty className="panel-empty" description={data ? '职业图谱数据无效，请重试' : '等待职业图谱'} />;
  }

  const acquired = data.levels.filter((level) => level.status === 'acquired');
  const next = data.levels.find((level) => level.status !== 'acquired');

  return (
    <div className="career-graph-view">
      <div className="career-graph-intro">
        <div>
          <Typography.Text className="story-section-label">从当前能力到下一阶段</Typography.Text>
          <Typography.Title level={4}>
            {acquired[acquired.length - 1]?.title || '当前阶段待确认'} → {next?.title || '后续阶段待确认'}
          </Typography.Title>
          <Typography.Text type="secondary">
            已具备 {acquired.length} 个阶段节点；{next ? `下一节点需要 ${next.coreSkills.filter((skill) => !skill.isMastered).length} 项待补能力。` : '当前图谱中没有待补节点。'}
          </Typography.Text>
        </div>
        <Button onClick={() => setListView((current) => !current)} aria-pressed={listView}>
          {listView ? '查看图谱' : '查看节点列表'}
        </Button>
      </div>
      {listView ? (
        <ol className="career-graph-list" aria-label="职业图谱节点列表">
          {data.levels.map((level) => (
            <li key={level.id}>
              <div className="career-graph-list-head">
                <div><Typography.Text type="secondary">{level.level}</Typography.Text><strong>{level.title}</strong><Typography.Text type="secondary">{level.salaryRange}</Typography.Text></div>
                <Tag color={level.status === 'acquired' ? 'cyan' : 'blue'}>{level.status === 'acquired' ? '已具备' : '待提升'}</Tag>
              </div>
              <div className="career-graph-skills">
                {level.coreSkills.map((skill) => (
                  <Tag color={skill.isMastered ? 'cyan' : 'gold'} key={`${level.id}-${skill.name}`}>
                    {skill.name} · {skill.isMastered ? '已掌握' : '待补齐'}
                  </Tag>
                ))}
              </div>
            </li>
          ))}
        </ol>
      ) : <ChartCanvas option={option} className="chart-canvas tree-chart" />}
    </div>
  );
}
