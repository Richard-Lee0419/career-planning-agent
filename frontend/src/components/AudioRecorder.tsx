import { Button, Space, Tooltip, Typography } from 'antd';
import { AudioOutlined, PauseCircleOutlined } from '@ant-design/icons';
import { useAudioRecorder } from '../hooks/useAudio';

interface AudioRecorderProps {
  onRecorded: (blob: Blob) => void | Promise<void>;
  loading?: boolean;
}

export function AudioRecorder({ onRecorded, loading }: AudioRecorderProps) {
  const { recording, permissionError, toggle } = useAudioRecorder(onRecorded);

  return (
    <Space align="center">
      <Tooltip title={recording ? '结束录音' : '开始录音'}>
        <Button
          shape="circle"
          type={recording ? 'primary' : 'default'}
          danger={recording}
          icon={recording ? <PauseCircleOutlined /> : <AudioOutlined />}
          loading={loading}
          onClick={() => void toggle()}
        />
      </Tooltip>
      {permissionError && <Typography.Text type="danger">{permissionError}</Typography.Text>}
    </Space>
  );
}
