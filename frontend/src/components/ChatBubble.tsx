import { Avatar, Typography } from 'antd';
import { RobotOutlined, UserOutlined } from '@ant-design/icons';

interface ChatBubbleProps {
  role: 'user' | 'assistant';
  content: string;
}

export function ChatBubble({ role, content }: ChatBubbleProps) {
  const isUser = role === 'user';

  return (
    <div className={`chat-bubble-row ${isUser ? 'is-user' : 'is-assistant'}`}>
      {!isUser && (
        <Avatar className="chat-avatar assistant-avatar" icon={<RobotOutlined />} />
      )}
      <div className={`chat-bubble ${isUser ? 'user-bubble' : 'assistant-bubble'}`}>
        <Typography.Paragraph>{content}</Typography.Paragraph>
      </div>
      {isUser && <Avatar className="chat-avatar user-avatar" icon={<UserOutlined />} />}
    </div>
  );
}
