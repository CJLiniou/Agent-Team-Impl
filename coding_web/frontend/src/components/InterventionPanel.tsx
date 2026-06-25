/* ═══════════════════════════════════════════════════════════════
   InterventionPanel — 人工介入操作面板
   支持：消息注入、暂停/恢复、计划审批、介入历史
   ═══════════════════════════════════════════════════════════════ */

import { useState, useEffect, useCallback } from 'react';
import { useTaskStore } from '../store/taskStore';
import {
  injectMessage,
  pauseTask,
  resumeTask,
  listInterventions,
  listPendingPlans,
  reviewPlan,
  confirmCompletion,
  type InterventionRecord,
  type PendingPlan,
} from '../api/interventions';

interface Props {
  taskId: string;
}

export default function InterventionPanel({ taskId }: Props) {
  const agents = useTaskStore((s) => s.agents);
  const isRunning = useTaskStore((s) => s.isRunning);
  const agentList = Array.from(agents.values());

  // 状态
  const [selectedAgentId, setSelectedAgentId] = useState('');
  const [message, setMessage] = useState('');
  const [sending, setSending] = useState(false);
  const [status, setStatus] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [history, setHistory] = useState<InterventionRecord[]>([]);
  const [pendingPlans, setPendingPlans] = useState<PendingPlan[]>([]);
  const [paused, setPaused] = useState(false);
  const [showHistory, setShowHistory] = useState(false);

  // 加载待审批计划
  const loadPlans = useCallback(async () => {
    try {
      setPendingPlans(await listPendingPlans(taskId));
    } catch { /* silent */ }
  }, [taskId]);

  useEffect(() => {
    if (isRunning) {
      loadPlans();
      const interval = setInterval(loadPlans, 10000);
      return () => clearInterval(interval);
    }
  }, [isRunning, loadPlans]);

  // 发送消息
  const handleInject = async () => {
    if (!message.trim()) return;
    setSending(true);
    setStatus(null);
    try {
      await injectMessage(taskId, selectedAgentId, message.trim());
      setStatus({ type: 'success', text: `消息已发送给 ${selectedAgentId || '所有智能体'}` });
      setMessage('');
      loadHistory();
    } catch (err) {
      setStatus({ type: 'error', text: err instanceof Error ? err.message : '发送失败' });
    }
    setSending(false);
  };

  // 暂停/恢复
  const handlePauseResume = async () => {
    try {
      if (paused) {
        await resumeTask(taskId);
        setPaused(false);
        setStatus({ type: 'success', text: '任务已恢复' });
      } else {
        await pauseTask(taskId);
        setPaused(true);
        setStatus({ type: 'success', text: '任务已暂停' });
      }
    } catch (err) {
      setStatus({ type: 'error', text: err instanceof Error ? err.message : '操作失败' });
    }
  };

  // 完成项目
  const handleComplete = async () => {
    if (!confirm('确认项目完成？这将通知 Leader 收尾汇总。')) return;
    try {
      await confirmCompletion(taskId);
      setStatus({ type: 'success', text: '已通知 Leader 收尾汇总' });
    } catch (err) {
      setStatus({ type: 'error', text: err instanceof Error ? err.message : '操作失败' });
    }
  };

  // 计划审批
  const handleReview = async (planId: string, approved: boolean) => {
    try {
      await reviewPlan(taskId, planId, approved, approved ? '已批准' : '已驳回');
      setStatus({ type: 'success', text: `计划${approved ? '已批准' : '已驳回'}` });
      loadPlans();
    } catch (err) {
      setStatus({ type: 'error', text: err instanceof Error ? err.message : '审批失败' });
    }
  };

  // 加载历史
  const loadHistory = async () => {
    try {
      setHistory(await listInterventions(taskId));
      setShowHistory(true);
    } catch { /* silent */ }
  };

  if (!isRunning) return null;

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-white font-medium">🛡 人工介入</h3>
        <div className="flex items-center gap-2">
          <button
            onClick={loadHistory}
            className="text-xs text-gray-400 hover:text-gray-300"
          >
            {showHistory ? '刷新历史' : '查看历史'}
          </button>
          <button
            onClick={handlePauseResume}
            className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
              paused
                ? 'bg-emerald-600 hover:bg-emerald-500 text-white'
                : 'bg-amber-600 hover:bg-amber-500 text-white'
            }`}
          >
            {paused ? '▶ 恢复' : '⏸ 暂停'}
          </button>
          <button
            onClick={handleComplete}
            className="px-3 py-1 rounded text-xs font-medium bg-blue-600 hover:bg-blue-500 text-white transition-colors"
            title="通知 Leader 项目完成，收尾汇总"
          >
            ✅ 完成项目
          </button>
        </div>
      </div>

      {/* 状态提示 */}
      {status && (
        <div className={`rounded px-3 py-2 text-xs ${
          status.type === 'success'
            ? 'bg-emerald-500/10 border border-emerald-500/30 text-emerald-400'
            : 'bg-red-500/10 border border-red-500/30 text-red-400'
        }`}>
          {status.text}
        </div>
      )}

      {/* 消息注入 */}
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <select
            value={selectedAgentId}
            onChange={(e) => setSelectedAgentId(e.target.value)}
            className="bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs text-gray-200 flex-1"
          >
            <option value="">所有智能体（广播）</option>
            {agentList.map((a) => (
              <option key={a.id} value={a.id}>{a.name} ({a.role})</option>
            ))}
          </select>
        </div>
        <div className="flex gap-2">
          <input
            type="text"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleInject()}
            placeholder="输入要发送的消息..."
            className="flex-1 bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm text-gray-200
                       placeholder-gray-500 focus:outline-none focus:border-blue-500"
          />
          <button
            onClick={handleInject}
            disabled={sending || !message.trim()}
            className="bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 text-white px-3 py-1.5 rounded text-sm
                       transition-colors shrink-0"
          >
            {sending ? '...' : '发送'}
          </button>
        </div>
      </div>

      {/* 待审批计划 */}
      {pendingPlans.length > 0 && (
        <div>
          <h4 className="text-xs text-gray-400 mb-2">待审批计划 ({pendingPlans.length})</h4>
          <div className="space-y-2">
            {pendingPlans.map((plan) => (
              <div key={plan.id} className="bg-gray-800 rounded p-3 text-sm">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-gray-300 text-xs">智能体: {plan.agent_id}</span>
                  <span className="text-gray-600 text-xs">{plan.created_at?.slice(0, 19)}</span>
                </div>
                <p className={`text-gray-200 whitespace-pre-wrap text-xs ${plan._expanded ? '' : 'line-clamp-4'}`}>
                  {plan.content}
                </p>
                {plan.content && plan.content.length > 200 && (
                  <button
                    onClick={() => {
                      setPendingPlans(prev => prev.map(p =>
                        p.id === plan.id ? {...p, _expanded: !(p as any)._expanded} : p
                      ));
                    }}
                    className="text-blue-400 hover:text-blue-300 text-xs mt-0.5"
                  >
                    {(plan as any)._expanded ? '▲ 收起' : '▼ 展开详情'}
                  </button>
                )}
                <div className="flex gap-2 mt-2">
                  <button
                    onClick={() => handleReview(plan.id, true)}
                    className="px-2 py-0.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded text-xs"
                  >
                    批准
                  </button>
                  <button
                    onClick={() => handleReview(plan.id, false)}
                    className="px-2 py-0.5 bg-red-600 hover:bg-red-500 text-white rounded text-xs"
                  >
                    驳回
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 介入历史 */}
      {showHistory && (
        <div>
          <h4 className="text-xs text-gray-400 mb-2">
            介入历史 ({history.length})
            <button onClick={() => setShowHistory(false)} className="ml-2 text-gray-600 hover:text-gray-400">收起</button>
          </h4>
          {history.length === 0 ? (
            <p className="text-xs text-gray-600">暂无介入记录</p>
          ) : (
            <div className="space-y-1.5 max-h-48 overflow-y-auto">
              {history.map((h) => (
                <div key={h.id} className="bg-gray-800/50 rounded px-2.5 py-1.5 flex items-start gap-2">
                  <span className={`text-xs shrink-0 mt-0.5 ${
                    h.type === 'pause' ? 'text-amber-400' :
                    h.type === 'resume' ? 'text-emerald-400' :
                    h.type === 'plan_review' ? 'text-purple-400' :
                    'text-blue-400'
                  }`}>
                    {h.type === 'pause' ? '⏸' : h.type === 'resume' ? '▶' : h.type === 'plan_review' ? '📋' : '💬'}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="text-xs text-gray-300 truncate">
                      {h.type === 'message' ? `→ ${h.agent_id || 'ALL'}: ${h.content.slice(0, 60)}` :
                       h.type === 'pause' ? '暂停任务' :
                       h.type === 'resume' ? '恢复任务' :
                       h.content}
                    </p>
                    <p className="text-2xs text-gray-600">{h.created_at?.slice(11, 19)}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
