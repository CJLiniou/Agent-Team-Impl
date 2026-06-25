/* ═══════════════════════════════════════════════════════════════
   AgentPanel — 智能体状态面板
   ═══════════════════════════════════════════════════════════════ */

import { useState } from 'react';
import AgentCard from './AgentCard';
import AgentMemoryPanel from './AgentMemoryPanel';
import { useTaskStore } from '../store/taskStore';

interface Props {
  taskId?: string;
}

export default function AgentPanel({ taskId }: Props) {
  const agents = useTaskStore((s) => s.agents);
  const agentList = Array.from(agents.values());
  const [memoryAgent, setMemoryAgent] = useState<{ id: string; name: string } | null>(null);

  if (agentList.length === 0) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
        <h3 className="text-white font-medium mb-4">🤖 智能体</h3>
        <div className="text-center text-gray-500 py-8">
          <p className="text-3xl mb-2">🤖</p>
          <p className="text-sm">等待智能体启动...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
      <h3 className="text-white font-medium mb-3">
        🤖 智能体 <span className="text-gray-500 text-sm font-normal ml-1">({agentList.length})</span>
      </h3>
      <div className="space-y-2 max-h-[400px] overflow-y-auto pr-1">
        {agentList.map((agent) => (
          <AgentCard
            key={agent.id}
            agent={agent}
            taskId={taskId}
            onViewMemory={(id, name) => setMemoryAgent({ id, name })}
          />
        ))}
      </div>

      {/* 记忆查看弹窗 */}
      {memoryAgent && taskId && (
        <AgentMemoryPanel
          taskId={taskId}
          agentId={memoryAgent.id}
          agentName={memoryAgent.name}
          onClose={() => setMemoryAgent(null)}
        />
      )}
    </div>
  );
}
