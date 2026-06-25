/* ═══════════════════════════════════════════════════════════════
   EventTimeline — 事件时间线
   ═══════════════════════════════════════════════════════════════ */

import { useEffect, useRef } from 'react';
import { useTaskStore } from '../store/taskStore';
import type { LogEntry } from '../types';

const levelStyles: Record<string, string> = {
  info: 'border-l-gray-600',
  warn: 'border-l-amber-500',
  error: 'border-l-red-500',
};

const levelDots: Record<string, string> = {
  info: 'bg-gray-500',
  warn: 'bg-amber-500',
  error: 'bg-red-500',
};

export default function EventTimeline() {
  const logs = useTaskStore((s) => s.logs);
  const containerRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const userScrolledUp = useRef(false);

  // 检测用户是否手动上滚
  const handleScroll = () => {
    const el = containerRef.current;
    if (!el) return;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
    userScrolledUp.current = !atBottom;
  };

  // 仅当用户在底部时自动滚动（只滚容器内部，不滚页面）
  useEffect(() => {
    if (!userScrolledUp.current && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [logs.length]);

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
      <h3 className="text-white font-medium mb-3">
        ⏱️ 事件时间线 <span className="text-gray-500 text-sm font-normal ml-1">({logs.length})</span>
      </h3>

      {logs.length === 0 ? (
        <div className="text-center text-gray-500 py-8">
          <p className="text-3xl mb-2">⏱️</p>
          <p className="text-sm">等待事件...</p>
        </div>
      ) : (
        <div ref={containerRef} onScroll={handleScroll} className="max-h-[300px] overflow-y-auto pr-1 space-y-0">
          {logs.map((log, i) => (
            <div
              key={i}
              className={`flex items-start gap-2 py-1.5 px-2 border-l-2 ${levelStyles[log.level] || levelStyles.info} ml-1`}
            >
              <span className={`w-2 h-2 rounded-full mt-1.5 flex-shrink-0 ${levelDots[log.level] || levelDots.info}`} />
              <span className="text-gray-600 text-[10px] flex-shrink-0 w-12 text-right">
                {new Date(log.timestamp).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
              </span>
              {log.name && (
                <span className="text-accent-400 text-xs font-medium flex-shrink-0">[{log.name}]</span>
              )}
              <span className="text-gray-400 text-xs flex-1">{log.message}</span>
            </div>
          ))}
          <div ref={bottomRef} />
        </div>
      )}
    </div>
  );
}
