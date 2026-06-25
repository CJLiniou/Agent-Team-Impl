/* ═══════════════════════════════════════════════════════════════
   HomePage — 任务列表 + 创建表单，点击任务卡片弹出详情弹窗
   ═══════════════════════════════════════════════════════════════ */

import { useEffect, useState, useCallback } from 'react';
import TaskCreator from '../components/TaskCreator';
import TaskCard from '../components/TaskCard';
import TaskDetailModal from '../components/TaskDetailModal';
import { listTasks, createTask, deleteTask } from '../api/tasks';
import type { CodingTask, CodingTaskCreate } from '../types';

export default function HomePage() {
  const [tasks, setTasks] = useState<CodingTask[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [statusFilter, setStatusFilter] = useState('');

  // 弹窗状态
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);

  const fetchTasks = useCallback(async () => {
    try {
      const data = await listTasks(statusFilter);
      setTasks(data);
    } catch {
      // silent
    }
  }, [statusFilter]);

  useEffect(() => {
    fetchTasks();
    const interval = setInterval(fetchTasks, 5000);
    return () => clearInterval(interval);
  }, [fetchTasks]);

  const handleCreate = async (req: CodingTaskCreate) => {
    setLoading(true);
    setError('');
    try {
      const task = await createTask(req);
      // 创建成功后自动打开弹窗查看实时进度
      setSelectedTaskId(task.id);
      // 刷新列表
      await fetchTasks();
      setLoading(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : '创建失败');
      setLoading(false);
    }
  };

  const handleTaskClick = (taskId: string) => {
    setSelectedTaskId(taskId);
  };

  const handleDeleteTask = async (taskId: string) => {
    try {
      await deleteTask(taskId);
      setSelectedTaskId(null);
      fetchTasks();
    } catch { /* silent */ }
  };

  const handleCloseModal = () => {
    setSelectedTaskId(null);
    fetchTasks();
  };

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      {/* 顶部 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">🤖 Coding Agent Team</h1>
          <p className="text-gray-400 text-sm mt-1">创建编码任务，实时观察多智能体协作过程</p>
        </div>
        <div className="flex items-center gap-4 text-sm text-gray-400">
          <span>WebSocket</span>
          <div className="flex gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
          </div>
        </div>
      </div>

      {/* 错误提示 */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 text-red-400 text-sm">
          {error}
        </div>
      )}

      {/* 创建表单 */}
      <TaskCreator onSubmit={handleCreate} loading={loading} />

      {/* 过滤 + 任务列表 */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold text-white">任务列表</h2>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="bg-gray-800 border border-gray-700 rounded-md px-3 py-1.5 text-sm text-gray-300 focus:outline-none focus:border-accent-500"
          >
            <option value="">全部</option>
            <option value="running">运行中</option>
            <option value="completed">已完成</option>
            <option value="failed">失败</option>
            <option value="cancelled">已取消</option>
          </select>
        </div>

        {tasks.length === 0 ? (
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-12 text-center text-gray-500">
            <p className="text-4xl mb-2">📋</p>
            <p>暂无任务</p>
            <p className="text-sm mt-1">创建一个任务开始吧</p>
          </div>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2">
            {tasks.map((task) => (
              <TaskCard key={task.id} task={task} onClick={handleTaskClick} onDelete={handleDeleteTask} />
            ))}
          </div>
        )}
      </div>

      {/* ── 任务详情弹窗 ── */}
      <TaskDetailModal taskId={selectedTaskId} onClose={handleCloseModal} onDelete={handleDeleteTask} />
    </div>
  );
}
