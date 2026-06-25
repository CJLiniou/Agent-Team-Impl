/* ═══════════════════════════════════════════════════════════════
   TaskQueuePanel — 任务队列面板（列视图）
   ═══════════════════════════════════════════════════════════════ */

import TaskItem from './TaskItem';
import { useTaskStore } from '../store/taskStore';

const COLUMNS = [
  { status: 'pending', label: '⏳ 待处理', color: 'border-t-gray-500' },
  { status: 'in_progress', label: '🔄 进行中', color: 'border-t-amber-500' },
  { status: 'completed', label: '✅ 已完成', color: 'border-t-emerald-500' },
  { status: 'failed', label: '❌ 失败', color: 'border-t-red-500' },
  { status: 'blocked', label: '🔒 被阻止', color: 'border-t-purple-500' },
];

export default function TaskQueuePanel() {
  const taskQueue = useTaskStore((s) => s.taskQueue);

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
      <h3 className="text-white font-medium mb-3">
        📋 任务队列 <span className="text-gray-500 text-sm font-normal ml-1">({taskQueue.length})</span>
      </h3>

      {taskQueue.length === 0 ? (
        <div className="text-center text-gray-500 py-8">
          <p className="text-3xl mb-2">📋</p>
          <p className="text-sm">等待任务创建...</p>
        </div>
      ) : (
        <div className="grid grid-cols-5 gap-2">
          {COLUMNS.map((col) => {
            const items = taskQueue.filter((t) => t.status === col.status);
            return (
              <div key={col.status} className={`bg-gray-800/30 rounded-lg border-t-2 ${col.color}`}>
                <div className="px-2 py-2 text-xs font-medium text-gray-400 flex items-center justify-between">
                  <span>{col.label}</span>
                  <span className="text-gray-600">{items.length}</span>
                </div>
                <div className="px-1.5 pb-1.5 space-y-1 max-h-[240px] overflow-y-auto">
                  {items.map((task) => (
                    <TaskItem key={task.id} task={task} />
                  ))}
                  {items.length === 0 && (
                    <div className="text-center text-gray-600 text-xs py-4">-</div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
