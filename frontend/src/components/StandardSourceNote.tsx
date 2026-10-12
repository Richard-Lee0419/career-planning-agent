import { Collapse, List, Space, Tag, Typography } from 'antd';
import type { StandardSource } from '../api/types';

export function StandardSourceNote({ source, notice }: { source?: StandardSource | null; notice?: string }) {
  if (!source) return <Typography.Paragraph type="secondary" className="standard-source-note">
    {notice || '此岗位未记录可核对的标准来源，覆盖结果仅供探索。'}
  </Typography.Paragraph>;
  const reviewed = source.review_status === 'source_checked';
  const label = source.type === 'manual_pilot' ? '有限范围试点' : source.type === 'demo_example' ? '演示标准' : '来源待核对';
  const links = source.sources.filter((item) => /^https?:\/\//i.test(item.url));
  return <div className="standard-source-note">
    <Space wrap>
      <Tag color={reviewed ? 'cyan' : 'gold'}>{label}</Tag>
      <Typography.Text type="secondary">{source.region}{source.version ? ` · 版本 ${source.version}` : ''}</Typography.Text>
      {!reviewed && <Tag color="gold">{source.review_status === 'modified_unverified' ? '内容变更后待复核' : '来源未确认'}</Tag>}
    </Space>
    {notice && <Typography.Paragraph type="secondary">{notice}</Typography.Paragraph>}
    <Collapse size="small" ghost items={[{
      key: 'sources', label: '查看工作任务、依据与适用范围', children: <>
        {source.tasks.length > 0 && <Typography.Paragraph>工作任务：{source.tasks.join('；')}</Typography.Paragraph>}
        {links.length ? <List size="small" dataSource={links} renderItem={(item) => <List.Item>
          <div>
            <Typography.Link href={item.url} target="_blank" rel="noopener noreferrer">{item.title}</Typography.Link>
            <Typography.Paragraph type="secondary">{item.kind === 'education_standard' ? '教学标准参考' : '招聘要求示例'}{item.published_at ? ` · 发布于 ${item.published_at}` : ''}{item.evidence_location ? ` · ${item.evidence_location}` : ''}</Typography.Paragraph>
            {item.access_status && <Typography.Text type="secondary">核对范围：{item.access_status}{item.accessed_at ? ` · ${item.accessed_at}` : ''}</Typography.Text>}
          </div>
        </List.Item>} /> : <Typography.Paragraph type="secondary">暂无可访问的来源链接。</Typography.Paragraph>}
        {source.limitations.length > 0 && <List size="small" dataSource={source.limitations} renderItem={(item) => <List.Item><Typography.Text type="secondary">{item}</Typography.Text></List.Item>} />}
        {source.reviewed_at && <Typography.Text type="secondary">来源整理日期：{source.reviewed_at}</Typography.Text>}
      </>
    }]} />
  </div>;
}
