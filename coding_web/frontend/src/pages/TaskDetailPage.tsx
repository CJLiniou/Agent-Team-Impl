/* ═══════════════════════════════════════════════════════════════
   TaskDetailPage — 实时监控仪表盘
   ═══════════════════════════════════════════════════════════════ */

import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTaskStore } from '../store/taskStore';
import { useWebSocket } from '../hooks/useWebSocket';
import { getTask, cancelTask, getFileTree, deleteTask, continueTask } from '../api/tasks';
import AgentPanel from '../components/AgentPanel';
import MessagePanel from '../components/MessagePanel';
import TaskQueuePanel from '../components/TaskQueuePanel';
import EventTimeline from '../components/EventTimeline';
import SandboxFileTree from '../components/SandboxFileTree';
import ExecutionPanel from '../components/ExecutionPanel';
import InterventionPanel from '../components/InterventionPanel';
import StatusBadge from '../components/StatusBadge';
import ExpandableText from '../components/ExpandableText';

export default function TaskDetailPage() {
  const { taskId } = useParams<{ taskId: string }>();
  const navigate = useNavigate();
  const store = useTaskStore();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [cancelling, setCancelling] = useState(false);
  const [showContinue, setShowContinue] = useState(false);
  const [continueInstructions, setContinueInstructions] = useState('');
  const [continuing, setContinuing] = useState(false);

  // WebSocket 连接
  useWebSocket(taskId || null);

  // 加载任务详情
  useEffect(() => {
    if (!taskId) return;

    const loadTask = async () => {
      try {
        const task = await getTask(taskId);
        store.setTask(task);
        setLoading(false);

        // 如果任务在运行中，开始定期刷新文件树
        if (task.status === 'running') {
          refreshFileTree();
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : '加载失败');
        setLoading(false);
      }
    };

    loadTask();
    return () => {
      store.reset();
    };
  }, [taskId]);

  const refreshFileTree = async () => {
    if (!taskId) return;
    try {
      const tree = await getFileTree(taskId);
      store.setFileTree(tree);
    } catch {
      // silent
    }
  };

  // 定期刷新文件树（任务运行中时）
  useEffect(() => {
    if (!store.isRunning) return;
    const interval = setInterval(refreshFileTree, 10000);
    return () => clearInterval(interval);
  }, [store.isRunning, taskId]);

  // 取消任务
  const handleCancel = async () => {
    if (!taskId || cancelling) return;
    setCancelling(true);
    try {
      await cancelTask(taskId);
      store.setTask({ ...store.task!, status: 'cancelled' });
    } catch (err) {
      setError(err instanceof Error ? err.message : '取消失败');
    }
    setCancelling(false);
  };

  // 继续编辑
  const handleContinue = async () => {
    if (!taskId || !continueInstructions.trim() || continuing) return;
    setContinuing(true);
    try {
      const newTask = await continueTask(taskId, continueInstructions.trim());
      navigate(`/tasks/${newTask.id}`, { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : '继续编辑失败');
      setContinuing(false);
      setShowContinue(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="w-12 h-12 border-4 border-accent-500/30 border-t-accent-500 rounded-full animate-spin mx-auto mb-4" />
          <p className="text-gray-400">加载中...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <p className="text-red-400 text-lg mb-4">{error}</p>
          <button onClick={() => navigate('/')} className="text-accent-400 hover:underline">
            返回首页
          </button>
        </div>
      </div>
    );
  }

  const task = store.task;
  if (!task) return null;

  return (
    <div className="max-w-[1440px] mx-auto p-4 space-y-4">
      {/* ── 顶部标题栏 ── */}
      <div className="flex items-center justify-between bg-gray-900 border border-gray-800 rounded-lg p-4">
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate('/')}
            className="text-gray-400 hover:text-white transition-colors"
          >
            ← 返回
          </button>
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-xl font-bold text-white">{task.title}</h1>
              <StatusBadge status={task.status} />
              {store.wsConnected && (
                <span className="flex items-center gap-1 text-xs text-emerald-400">
                  <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                  实时连接
                </span>
              )}
            </div>
            <ExpandableText text={task.description} maxLines={2} className="text-gray-400 text-sm mt-1" label="任务描述" />
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="text-right text-xs text-gray-500">
            <div>语言: {task.language}</div>
            <div>模式: {task.mode === 'team' ? '团队' : '单人'}</div>
            {task.mode === 'team' && <div>Coder: {task.num_coders}</div>}
          </div>
          {store.isRunning && (
            <button
              onClick={handleCancel}
              disabled={cancelling}
              className="bg-red-600 hover:bg-red-500 disabled:bg-gray-700 text-white px-4 py-2 rounded-md text-sm font-medium transition-colors"
            >
              {cancelling ? '取消中...' : '⏹ 取消任务'}
            </button>
          )}
          {!store.isRunning && (
            <div className="flex items-center gap-3">
              <button
                onClick={() => setShowContinue(true)}
                className="bg-accent-600 hover:bg-accent-500 text-white px-4 py-2 rounded-md text-sm font-medium transition-colors"
              >
                继续编辑
              </button>
              <button
                onClick={() => { if (confirm('确定删除此任务？')) { deleteTask(taskId!).then(() => navigate('/')); } }}
                className="text-gray-500 hover:text-red-400 text-sm transition-colors"
              >
                🗑 删除
              </button>
            </div>
          )}
        </div>
      </div>

      {/* ── 主仪表盘 ── */}
      <div className="grid grid-cols-2 gap-4">
        {/* 左侧：智能体面板 */}
        <AgentPanel taskId={taskId} />
        {/* 右侧：消息盒子 */}
        <MessagePanel />
      </div>

      {/* ── 人工介入（仅运行中）── */}
      {store.isRunning && taskId && <InterventionPanel taskId={taskId} />}

      {/* ── 任务队列 ── */}
      <TaskQueuePanel />

      {/* ── 事件时间线 ── */}
      <EventTimeline />

      {/* ── 沙盒文件 ── */}
      <SandboxFileTree />

      {/* ── 代码执行 ── */}
      <ExecutionPanel />

      {/* ── 最终结果（任务完成后显示）── */}
      {task.status === 'completed' && task.result && (
        <div className="bg-gray-900 border border-emerald-500/30 rounded-lg p-4">
          <h3 className="text-white font-medium mb-3">✅ 执行结果</h3>
          <div className="bg-gray-950 border border-gray-800 rounded-lg p-4 max-h-[500px] overflow-y-auto">
            <pre className="text-gray-300 text-sm whitespace-pre-wrap font-mono">
              {task.result}
            </pre>
          </div>
          {task.stats && (
            <div className="mt-3 text-xs text-gray-500">
              {task.stats.total_completed_tasks !== undefined && (
                <span className="mr-4">完成任务: {task.stats.total_completed_tasks}</span>
              )}
              {task.stats.token_usage && (
                <span>
                  Token 消耗: {task.stats.token_usage.total_tokens.toLocaleString()}
                  {' · '}
                  成本: ${task.stats.token_usage.total_cost.toFixed(4)}
                </span>
              )}
            </div>
          )}
        </div>
      )}

      {/* 失败信息 */}
      {task.status === 'failed' && task.error_message && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4">
          <h3 className="text-red-400 font-medium mb-2">❌ 执行失败</h3>
          <p className="text-red-300 text-sm whitespace-pre-wrap">{task.error_message}</p>
        </div>
      )}

      {/* 已取消 */}
      {task.status === 'cancelled' && (
        <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-4 text-center">
          <p className="text-gray-400">⏹ 任务已取消</p>
        </div>
      )}

      {/* 溯源链接 */}
      {(task as any).continue_from_task_id && (
        <div className="text-xs text-gray-600">
          基于任务{' '}
          <button
            onClick={() => navigate(`/tasks/${(task as any).continue_from_task_id}`)}
            className="text-accent-500 hover:underline"
          >
            {(task as any).continue_from_task_id.slice(0, 8)}...
          </button>
          {' '}继续编辑
        </div>
      )}

      {/* ── 继续编辑弹窗 ── */}
      {showContinue && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="bg-gray-900 border border-gray-700 rounded-lg p-6 w-full max-w-lg mx-4">
            <h3 className="text-white font-medium mb-2">继续编辑此项目</h3>
            <p className="text-gray-400 text-sm mb-4">
              输入新的修改需求，AI 智能体团队将在现有代码基础上进行修改。项目文件会被保留。
            </p>
            <textarea
              value={continueInstructions}
              onChange={(e) => setContinueInstructions(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter' && e.ctrlKey) handleContinue(); }}
              placeholder="例如：请为所有函数添加类型注解和文档字符串，并补充单元测试..."
              className="w-full bg-gray-800 border border-gray-700 rounded-md px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-accent-500 resize-none"
              rows={4}
              autoFocus
            />
            <p className="text-xs text-gray-600 mt-1">Ctrl+Enter 快速提交</p>
            <div className="flex justify-end gap-3 mt-4">
              <button
                onClick={() => { setShowContinue(false); setContinueInstructions(''); }}
                disabled={continuing}
                className="text-gray-400 hover:text-white text-sm transition-colors"
              >
                取消
              </button>
              <button
                onClick={handleContinue}
                disabled={!continueInstructions.trim() || continuing}
                className="bg-accent-600 hover:bg-accent-500 disabled:bg-gray-700 text-white px-4 py-2 rounded-md text-sm font-medium transition-colors"
              >
                {continuing ? '创建中...' : '开始编辑'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
