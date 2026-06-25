/* ═══════════════════════════════════════════════════════════════
   TaskDetailModal — 弹窗形式的任务详情仪表盘
   ═══════════════════════════════════════════════════════════════ */

import { useEffect, useState, useCallback } from 'react';
import { useTaskStore } from '../store/taskStore';
import { useWebSocket } from '../hooks/useWebSocket';
import { getTask, cancelTask, getFileTree, getTaskAgents, getTaskMessages, continueTask } from '../api/tasks';
import Modal from './Modal';
import AgentPanel from './AgentPanel';
import MessagePanel from './MessagePanel';
import TaskQueuePanel from './TaskQueuePanel';
import EventTimeline from './EventTimeline';
import SandboxFileTree from './SandboxFileTree';
import StatusBadge from './StatusBadge';
import ExecutionPanel from './ExecutionPanel';
import InterventionPanel from './InterventionPanel';
import ExpandableText from './ExpandableText';
import type { AgentTask, LogEntry } from '../types';

interface Props {
  taskId: string | null;
  onClose: () => void;
  onDelete?: (taskId: string) => void;
}

export default function TaskDetailModal({ taskId, onClose, onDelete }: Props) {
  const store = useTaskStore();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [cancelling, setCancelling] = useState(false);
  const [showContinue, setShowContinue] = useState(false);
  const [continueInstructions, setContinueInstructions] = useState('');
  const [continuing, setContinuing] = useState(false);

  // WebSocket 连接
  useWebSocket(taskId);

  // 加载任务详情
  useEffect(() => {
    if (!taskId) return;

    const loadTask = async () => {
      setLoading(true);
      try {
        const task = await getTask(taskId);
        store.setTask(task);
        setLoading(false);

        // 加载文件树
        refreshFileTree();

        // 立即拉取智能体和消息（不受 isRunning 限制）
        try {
          const [agents, messages] = await Promise.all([
            getTaskAgents(taskId),
            getTaskMessages(taskId),
          ]);
          if (agents.length > 0) store.setAgents(agents);
          if (messages.length > 0) store.setMessages(messages);
        } catch { /* ok if not ready yet */ }

        // 已完成/失败/取消的任务：从 run_history 恢复完整运行数据
        if (task.status === 'completed' || task.status === 'failed' || task.status === 'cancelled') {
          const history = (task as Record<string, unknown>).run_history as Record<string, unknown> | undefined;
          if (history) {
            // 优先使用 REST API 数据（可能比 run_history 更新）
            try {
              const [agents, messages] = await Promise.all([
                getTaskAgents(taskId),
                getTaskMessages(taskId),
              ]);
              if (agents.length > 0) store.setAgents(agents);
              if (messages.length > 0) store.setMessages(messages);
            } catch { /* fallback */ }
            // 从 run_history 恢复任务队列和日志
            if (!store.taskQueue.length && history.task_queue) {
              store.setTaskQueue(history.task_queue as AgentTask[]);
            }
            if (!store.logs.length && history.logs) {
              store.setLogs(history.logs as LogEntry[]);
            }
          } else {
            // 无 run_history，尝试 REST API
            try {
              const [agents, messages] = await Promise.all([
                getTaskAgents(taskId),
                getTaskMessages(taskId),
              ]);
              if (agents.length > 0) store.setAgents(agents);
              if (messages.length > 0) store.setMessages(messages);
            } catch { /* silent */ }
          }
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

  const refreshFileTree = useCallback(async () => {
    if (!taskId) return;
    try {
      const tree = await getFileTree(taskId);
      store.setFileTree(tree);
    } catch {
      // silent
    }
  }, [taskId]);

  // 定期刷新文件树
  useEffect(() => {
    if (!store.isRunning) return;
    const interval = setInterval(refreshFileTree, 10000);
    return () => clearInterval(interval);
  }, [store.isRunning, refreshFileTree]);

  // 任务结束后的收尾刷新（orchestrator 已注销，WebSocket 已断开）
  useEffect(() => {
    if (!taskId || store.isRunning) return;
    if (store.task && store.task.status !== 'pending' && store.task.status !== 'running') {
      const finalRefresh = async () => {
        try {
          const task = await getTask(taskId);
          store.setTask(task);
          const [agents, messages] = await Promise.all([
            getTaskAgents(taskId),
            getTaskMessages(taskId),
          ]);
          if (agents.length > 0) store.setAgents(agents);
          if (messages.length > 0) store.setMessages(messages);
          refreshFileTree();
        } catch { /* silent */ }
      };
      finalRefresh();
    }
  }, [taskId, store.isRunning]);

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
      // 关闭当前弹窗，打开新任务
      onClose();
      // 通过 onDelete 类似的回调通知父组件导航
      window.location.href = `/tasks/${newTask.id}`;
    } catch (err) {
      setError(err instanceof Error ? err.message : '继续编辑失败');
      setContinuing(false);
      setShowContinue(false);
    }
  };

  const task = store.task;

  return (
    <Modal open={!!taskId} onClose={onClose} size="full">
      <div className="h-full flex flex-col">
        {loading ? (
          <div className="flex items-center justify-center flex-1">
            <div className="text-center">
              <div className="w-10 h-10 border-3 border-accent-500/30 border-t-accent-500 rounded-full animate-spin mx-auto mb-3" />
              <p className="text-gray-400 text-sm">加载中...</p>
            </div>
          </div>
        ) : error ? (
          <div className="flex items-center justify-center flex-1">
            <div className="text-center">
              <p className="text-red-400 mb-3">{error}</p>
              <button onClick={onClose} className="text-accent-400 hover:underline text-sm">
                关闭
              </button>
            </div>
          </div>
        ) : !task ? (
          <div className="flex items-center justify-center flex-1">
            <p className="text-gray-500">任务不存在</p>
          </div>
        ) : (
          <div className="p-4 space-y-3 overflow-y-auto flex-1">
            {/* ── 标题栏 ── */}
            <div className="flex items-center justify-between bg-gray-900 border border-gray-800 rounded-lg p-3 flex-shrink-0">
              <div className="flex items-center gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="text-lg font-bold text-white">{task.title}</h2>
                    <StatusBadge status={task.status} />
                    {store.wsConnected && (
                      <span className="flex items-center gap-1 text-xs text-emerald-400">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                        实时
                      </span>
                    )}
                  </div>
                  <ExpandableText text={task.description} maxLines={1} className="text-gray-400 text-xs mt-0.5" label="任务描述" />
                </div>
              </div>

              <div className="flex items-center gap-2">
                <div className="text-right text-xs text-gray-500 mr-2">
                  <span>{task.language}</span>
                  <span className="mx-1">·</span>
                  <span>{task.mode === 'team' ? `团队(${task.num_coders})` : '单人'}</span>
                </div>
                {store.isRunning && (
                  <button
                    onClick={handleCancel}
                    disabled={cancelling}
                    className="bg-red-600 hover:bg-red-500 disabled:bg-gray-700 text-white px-3 py-1.5 rounded text-xs font-medium transition-colors"
                  >
                    {cancelling ? '取消中...' : '⏹ 取消'}
                  </button>
                )}
                {!store.isRunning && (
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setShowContinue(true)}
                      className="bg-accent-600 hover:bg-accent-500 text-white px-3 py-1.5 rounded text-xs font-medium transition-colors"
                    >
                      继续编辑
                    </button>
                    <button
                      onClick={() => { if (confirm('确定删除此任务？沙盒文件和运行历史将被永久删除。')) { onDelete?.(task.id); onClose(); } }}
                      className="text-gray-500 hover:text-red-400 text-xs transition-colors"
                      title="删除任务"
                    >
                      🗑 删除
                    </button>
                  </div>
                )}
              </div>
            </div>

            {/* ── 主仪表盘 ── */}
            <div className="grid grid-cols-2 gap-3">
              <AgentPanel taskId={taskId ?? undefined} />
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

            {/* ── 结果 ── */}
            {task.status === 'completed' && task.result && (
              <div className="bg-gray-900 border border-emerald-500/30 rounded-lg p-3">
                <h3 className="text-white font-medium mb-2 text-sm">✅ 执行结果</h3>
                <div className="bg-gray-950 border border-gray-800 rounded-lg p-3 max-h-[300px] overflow-y-auto">
                  <pre className="text-gray-300 text-xs whitespace-pre-wrap font-mono">{task.result}</pre>
                </div>
                {task.stats && (
                  <div className="mt-2 text-xs text-gray-500">
                    {task.stats.total_completed_tasks !== undefined && (
                      <span className="mr-3">完成任务: {task.stats.total_completed_tasks}</span>
                    )}
                    {task.stats.token_usage && (
                      <span>
                        Token: {task.stats.token_usage.total_tokens.toLocaleString()} · $
                        {task.stats.token_usage.total_cost.toFixed(4)}
                      </span>
                    )}
                  </div>
                )}
              </div>
            )}

            {task.status === 'failed' && task.error_message && (
              <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3">
                <h3 className="text-red-400 font-medium mb-1 text-sm">❌ 失败</h3>
                <p className="text-red-300 text-xs whitespace-pre-wrap">{task.error_message}</p>
              </div>
            )}

            {task.status === 'cancelled' && (
              <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-3 text-center">
                <p className="text-gray-400 text-sm">⏹ 任务已取消</p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── 继续编辑弹窗 ── */}
      {showContinue && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-[60]">
          <div className="bg-gray-900 border border-gray-700 rounded-lg p-6 w-full max-w-lg mx-4">
            <h3 className="text-white font-medium mb-2">继续编辑此项目</h3>
            <p className="text-gray-400 text-sm mb-4">
              输入新的修改需求，AI 智能体团队将在现有代码基础上进行修改。
            </p>
            <textarea
              value={continueInstructions}
              onChange={(e) => setContinueInstructions(e.target.value)}
              placeholder="例如：请为所有函数添加类型注解和文档字符串..."
              className="w-full bg-gray-800 border border-gray-700 rounded-md px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-accent-500 resize-none"
              rows={4}
              autoFocus
            />
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
    </Modal>
  );
}
