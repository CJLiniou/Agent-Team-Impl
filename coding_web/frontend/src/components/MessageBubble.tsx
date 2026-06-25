/* ═══════════════════════════════════════════════════════════════
   MessageBubble — 单条消息气泡
   ═══════════════════════════════════════════════════════════════ */

import ExpandableText from './ExpandableText';
import type { AgentMessage } from '../types';

interface Props {
  message: AgentMessage;
}

export default function MessageBubble({ message }: Props) {
  const isBroadcast = !message.recipient;

  return (
    <div className="msg-enter bg-gray-800/50 rounded-lg p-3 border border-gray-800">
      <div className="flex items-center gap-2 mb-1.5">
        <span className="text-accent-400 font-medium text-xs">{message.sender}</span>
        <span className="text-gray-600 text-xs">→</span>
        <span className="text-gray-400 text-xs">
          {isBroadcast ? '📢 广播' : message.recipient}
        </span>
        <span className="ml-auto text-gray-600 text-[10px]">
          {new Date(message.created_at).toLocaleTimeString('zh-CN')}
        </span>
      </div>
      {message.subject && (
        <div className="text-white font-medium text-sm mb-1">{message.subject}</div>
      )}
      <ExpandableText
        text={message.content}
        maxChars={300}
        className="text-gray-300 text-sm whitespace-pre-wrap break-words"
        label={`消息: ${message.subject || message.sender}`}
      />
    </div>
  );
}
