/* ═══════════════════════════════════════════════════════════════
   AgentCard — 单个智能体状态卡片
   ═══════════════════════════════════════════════════════════════ */

import StatusBadge from './StatusBadge';
import type { AgentState } from '../types';

const roleIcons: Record<string, string> = {
  coordinator: '🏗️',
  executor: '💻',
  reviewer: '🔍',
  specialist: '⚡',
};

const roleLabels: Record<string, string> = {
  coordinator: '协调者',
  executor: '执行者',
  reviewer: '审查者',
  specialist: '专家',
};

interface Props {
  agent: AgentState;
  taskId?: string;
  onViewMemory?: (agentId: string, agentName: string) => void;
}

export default function AgentCard({ agent, taskId, onViewMemory }: Props) {
  const icon = roleIcons[agent.role] || '🤖';
  const roleLabel = roleLabels[agent.role] || agent.role;

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-3.5 transition-all duration-300">
      {/* 头部：图标 + 名称 + 状态 */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-xl">{icon}</span>
          <div>
            <div className="flex items-center gap-1.5">
              <span className="text-white font-medium text-sm">{agent.name}</span>
              {agent.parent_agent_name && (
                <span className="text-purple-400 text-2xs" title={`Forked from ${agent.parent_agent_name}`}
                  style={{ fontSize: '0.6rem' }}>
                  ← {agent.parent_agent_name}
                </span>
              )}
            </div>
            <div className="text-gray-500 text-xs">{roleLabel}</div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {agent.allow_fork && (
            <span className="text-purple-400 text-2xs" title="可 Fork" style={{ fontSize: '0.6rem' }}>🍴</span>
          )}
          <StatusBadge status={agent.state} />
        </div>
      </div>

      {/* 当前动作 */}
      <div className="text-gray-400 text-xs min-h-[32px] bg-gray-800/50 rounded px-2.5 py-1.5 leading-relaxed">
        {agent.current_action || (
          <span className="text-gray-600 italic">
            {agent.state === 'idle' ? '等待任务分配...' :
             agent.state === 'waiting' ? '等待依赖完成...' :
             agent.state === 'error' ? agent.error_message || '发生错误' :
             '...'}
          </span>
        )}
      </div>

      {/* 统计 */}
      <div className="flex items-center gap-3 mt-2 text-xs text-gray-500">
        <span className="text-emerald-400">✓ {agent.completed_tasks}</span>
        <span className="text-red-400">✗ {agent.failed_tasks}</span>
        {taskId && onViewMemory && (
          <button
            onClick={(e) => { e.stopPropagation(); onViewMemory(agent.id, agent.name); }}
            className="ml-auto text-blue-400 hover:text-blue-300 transition-colors"
            title="查看智能体记忆"
          >
            🧠 记忆
          </button>
        )}
      </div>

      {/* 错误信息 */}
      {agent.state === 'error' && agent.error_message && (
        <div className="mt-2 text-xs text-red-400 bg-red-500/10 rounded px-2 py-1">
          {agent.error_message}
        </div>
      )}
    </div>
  );
}
