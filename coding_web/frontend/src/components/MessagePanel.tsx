/* ═══════════════════════════════════════════════════════════════
   MessagePanel — 消息盒子面板（智能体间消息）
   ═══════════════════════════════════════════════════════════════ */

import { useState } from 'react';
import MessageBubble from './MessageBubble';
import { useTaskStore } from '../store/taskStore';

type FilterType = 'all' | 'direct' | 'broadcast';

export default function MessagePanel() {
  const messages = useTaskStore((s) => s.messages);
  const [filter, setFilter] = useState<FilterType>('all');

  const filteredMessages = messages.filter((m) => {
    if (filter === 'direct') return !!m.recipient;
    if (filter === 'broadcast') return !m.recipient;
    return true;
  });

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 flex flex-col h-full">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-white font-medium">
          📨 消息盒子 <span className="text-gray-500 text-sm font-normal ml-1">({messages.length})</span>
        </h3>
        <div className="flex gap-1">
          {([
            ['all', '全部'],
            ['direct', '点对点'],
            ['broadcast', '广播'],
          ] as [FilterType, string][]).map(([key, label]) => (
            <button
              key={key}
              onClick={() => setFilter(key)}
              className={`px-2 py-1 text-xs rounded-md transition-colors ${
                filter === key
                  ? 'bg-accent-600 text-white'
                  : 'bg-gray-800 text-gray-400 hover:text-white'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto space-y-2 pr-1 min-h-[200px] max-h-[400px]">
        {filteredMessages.length === 0 ? (
          <div className="text-center text-gray-500 py-8">
            <p className="text-3xl mb-2">📨</p>
            <p className="text-sm">暂无消息</p>
            <p className="text-xs mt-1">智能体间的对话将在这里显示</p>
          </div>
        ) : (
          filteredMessages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} />
          ))
        )}
      </div>
    </div>
  );
}
