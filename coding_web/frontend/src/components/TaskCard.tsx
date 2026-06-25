/* ═══════════════════════════════════════════════════════════════
   TaskCard — 任务列表卡片，点击弹出详情，右键/按钮删除
   ═══════════════════════════════════════════════════════════════ */

import { useState } from 'react';
import StatusBadge from './StatusBadge';
import ExpandableText from './ExpandableText';
import type { CodingTask } from '../types';

interface Props {
  task: CodingTask;
  onClick?: (taskId: string) => void;
  onDelete?: (taskId: string) => void;
}

export default function TaskCard({ task, onClick, onDelete }: Props) {
  const [confirmDelete, setConfirmDelete] = useState(false);

  const handleDelete = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (confirmDelete) {
      onDelete?.(task.id);
      setConfirmDelete(false);
    } else {
      setConfirmDelete(true);
      setTimeout(() => setConfirmDelete(false), 3000);
    }
  };

  return (
    <div
      onClick={() => onClick?.(task.id)}
      className="bg-gray-900 border border-gray-800 rounded-lg p-4 cursor-pointer hover:border-gray-700 hover:bg-gray-850 transition-all duration-200 relative group"
    >
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-white font-medium truncate flex-1 mr-3">{task.title}</h3>
        <StatusBadge status={task.status} />
      </div>

      <ExpandableText text={task.description} maxLines={2} className="text-gray-400 text-sm mb-3" label="任务描述" />

      <div className="flex items-center gap-3 text-xs text-gray-500">
        <span className="flex items-center gap-1">
          <span className="inline-block w-3 h-3 rounded bg-accent-500/30 text-accent-400 text-[10px] leading-3 text-center">
            {task.language === 'typescript' ? 'TS' : task.language === 'javascript' ? 'JS' : task.language === 'python' ? 'Py' : task.language.slice(0, 2).toUpperCase()}
          </span>
          {task.language}
        </span>
        <span>{task.mode === 'team' ? '👥 团队' : '👤 单人'}</span>
        <span className="ml-auto">{new Date(task.created_at).toLocaleString('zh-CN')}</span>
      </div>

      {/* 删除按钮 */}
      <button
        onClick={handleDelete}
        className={`absolute top-2 right-2 text-xs px-2 py-0.5 rounded transition-all ${
          confirmDelete
            ? 'bg-red-600 text-white'
            : 'text-gray-600 hover:text-red-400 opacity-0 group-hover:opacity-100'
        }`}
        title={confirmDelete ? '确认删除' : '删除任务'}
      >
        {confirmDelete ? '确认删除？' : '🗑'}
      </button>
    </div>
  );
}
