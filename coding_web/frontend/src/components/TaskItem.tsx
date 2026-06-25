/* ═══════════════════════════════════════════════════════════════
   TaskItem — 任务队列中的单个任务条目
   ═══════════════════════════════════════════════════════════════ */

import type { AgentTask } from '../types';
import StatusBadge from './StatusBadge';
import ExpandableText from './ExpandableText';

interface Props {
  task: AgentTask;
}

export default function TaskItem({ task }: Props) {
  return (
    <div className="bg-gray-800/50 rounded-lg p-2.5 border border-gray-800 hover:border-gray-700 transition-colors">
      <div className="flex items-start justify-between gap-2 mb-1">
        <span className="text-white text-xs font-medium truncate flex-1">{task.name}</span>
        <StatusBadge status={task.status} />
      </div>
      {task.assigned_to && (
        <div className="text-gray-500 text-[10px]">分配给: {task.assigned_to}</div>
      )}
      {task.description && (
        <ExpandableText
          text={task.description}
          maxLines={1}
          maxChars={80}
          className="mt-0.5 text-gray-500 text-[10px]"
          label="任务描述"
        />
      )}
      {task.result && (
        <ExpandableText
          text={task.result}
          maxLines={2}
          maxChars={100}
          className="mt-1 text-gray-400 text-[10px] bg-gray-900/50 rounded px-1.5 py-0.5"
          label="任务结果"
        />
      )}
    </div>
  );
}
