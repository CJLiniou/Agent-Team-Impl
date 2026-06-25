/* ═══════════════════════════════════════════════════════════════
   AgentMemoryPanel — 智能体记忆查看弹窗
   分 4 个 Tab: 对话、决策、文件变更、笔记
   ═══════════════════════════════════════════════════════════════ */

import { useState, useEffect } from 'react';
import {
  getMemorySummary,
  getConversation,
  getDecisions,
  getFileChanges,
  getNotes,
  type MemorySummary,
  type ConversationEntry,
  type DecisionEntry,
  type FileChangeEntry,
  type NoteEntry,
} from '../api/memory';

interface Props {
  taskId: string;
  agentId: string;
  agentName: string;
  onClose: () => void;
}

type Tab = 'conversation' | 'decisions' | 'files' | 'notes';

const TAB_LABELS: Record<Tab, string> = {
  conversation: '对话历史',
  decisions: '决策记录',
  files: '文件变更',
  notes: '笔记',
};

export default function AgentMemoryPanel({ taskId, agentId, agentName, onClose }: Props) {
  const [tab, setTab] = useState<Tab>('conversation');
  const [summary, setSummary] = useState<MemorySummary | null>(null);
  const [conversations, setConversations] = useState<ConversationEntry[]>([]);
  const [decisions, setDecisions] = useState<DecisionEntry[]>([]);
  const [fileChanges, setFileChanges] = useState<FileChangeEntry[]>([]);
  const [notes, setNotes] = useState<NoteEntry[]>([]);
  const [loading, setLoading] = useState(false);

  // 加载摘要
  useEffect(() => {
    getMemorySummary(taskId, agentId).then(setSummary).catch(() => {});
  }, [taskId, agentId]);

  // 按 Tab 加载数据
  useEffect(() => {
    setLoading(true);
    const load = async () => {
      try {
        switch (tab) {
          case 'conversation': {
            const data = await getConversation(taskId, agentId, 50);
            setConversations(data.items);
            break;
          }
          case 'decisions':
            setDecisions(await getDecisions(taskId, agentId));
            break;
          case 'files':
            setFileChanges(await getFileChanges(taskId, agentId));
            break;
          case 'notes':
            setNotes(await getNotes(taskId, agentId));
            break;
        }
      } catch { /* silent */ }
      setLoading(false);
    };
    load();
  }, [taskId, agentId, tab]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onClose}>
      <div
        className="bg-gray-900 border border-gray-700 rounded-xl w-[800px] max-h-[85vh] flex flex-col shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* 头部 */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-gray-800">
          <div>
            <h2 className="text-lg font-bold text-white">🧠 {agentName} 记忆</h2>
            {summary && (
              <p className="text-xs text-gray-500 mt-0.5">
                对话 {summary.conversation_count} · 决策 {summary.decision_count} ·
                文件变更 {summary.file_change_count} · 笔记 {summary.note_count}
              </p>
            )}
          </div>
          <button onClick={onClose} className="text-gray-500 hover:text-white text-lg transition-colors">✕</button>
        </div>

        {/* Tab 切换 */}
        <div className="flex border-b border-gray-800 px-5">
          {(Object.keys(TAB_LABELS) as Tab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-4 py-2 text-sm transition-colors border-b-2 -mb-px ${
                tab === t
                  ? 'text-blue-400 border-blue-400'
                  : 'text-gray-500 border-transparent hover:text-gray-300'
              }`}
            >
              {TAB_LABELS[t]}
            </button>
          ))}
        </div>

        {/* 内容区 */}
        <div className="flex-1 overflow-y-auto p-5">
          {loading ? (
            <p className="text-gray-500 text-sm text-center py-12">加载中...</p>
          ) : (
            <>
              {/* 对话历史 */}
              {tab === 'conversation' && (
                <div className="space-y-3">
                  {conversations.length === 0 ? (
                    <p className="text-gray-500 text-sm text-center py-12">暂无对话记录</p>
                  ) : (
                    conversations.map((c) => (
                      <div key={c.id} className="bg-gray-800 rounded-lg p-3">
                        <div className="flex items-center gap-2 mb-1">
                          <span className={`text-xs px-1.5 py-0.5 rounded ${
                            c.role === 'assistant' ? 'bg-blue-500/20 text-blue-300' :
                            c.role === 'user' ? 'bg-gray-700 text-gray-300' :
                            c.role === 'system' ? 'bg-purple-500/20 text-purple-300' :
                            'bg-green-500/20 text-green-300'
                          }`}>
                            {c.role}
                          </span>
                          {c.tool_name && (
                            <span className="text-xs text-amber-400">🔧 {c.tool_name}</span>
                          )}
                          <span className="text-xs text-gray-600 ml-auto">{c.created_at?.slice(11, 19) || ''}</span>
                        </div>
                        <p className="text-sm text-gray-300 whitespace-pre-wrap line-clamp-6">{c.content}</p>
                        {c.tool_output && (
                          <details className="mt-1">
                            <summary className="text-xs text-gray-500 cursor-pointer">工具输出</summary>
                            <pre className="text-xs text-gray-400 mt-1 bg-gray-900 p-2 rounded overflow-x-auto max-h-32">
                              {c.tool_output}
                            </pre>
                          </details>
                        )}
                      </div>
                    ))
                  )}
                </div>
              )}

              {/* 决策记录 */}
              {tab === 'decisions' && (
                <div className="space-y-3">
                  {decisions.length === 0 ? (
                    <p className="text-gray-500 text-sm text-center py-12">暂无决策记录</p>
                  ) : (
                    decisions.map((d) => (
                      <div key={d.id} className="bg-gray-800 rounded-lg p-3 border-l-2 border-amber-500/50">
                        <div className="flex items-center gap-2 mb-1">
                          <span className={`text-xs px-1.5 py-0.5 rounded ${
                            d.outcome === 'completed' ? 'bg-emerald-500/20 text-emerald-300' : 'bg-red-500/20 text-red-300'
                          }`}>
                            {d.outcome}
                          </span>
                          <span className="text-xs text-gray-600 ml-auto">{d.created_at?.slice(11, 19) || ''}</span>
                        </div>
                        <p className="text-sm text-white font-medium">{d.decision}</p>
                        {d.reasoning && <p className="text-xs text-gray-400 mt-1">{d.reasoning}</p>}
                        {d.context && <p className="text-xs text-gray-600 mt-1">上下文: {d.context}</p>}
                      </div>
                    ))
                  )}
                </div>
              )}

              {/* 文件变更 */}
              {tab === 'files' && (
                <div className="space-y-2">
                  {fileChanges.length === 0 ? (
                    <p className="text-gray-500 text-sm text-center py-12">暂无文件变更</p>
                  ) : (
                    fileChanges.map((f) => (
                      <div key={f.id} className="bg-gray-800 rounded-lg p-3 flex items-start gap-3">
                        <span className={`text-xs px-1.5 py-0.5 rounded shrink-0 ${
                          f.operation === 'create' ? 'bg-emerald-500/20 text-emerald-300' :
                          f.operation === 'delete' ? 'bg-red-500/20 text-red-300' :
                          'bg-blue-500/20 text-blue-300'
                        }`}>
                          {f.operation}
                        </span>
                        <div className="min-w-0 flex-1">
                          <p className="text-sm text-gray-200 font-mono">{f.file_path}</p>
                          {f.snippet && (
                            <pre className="text-xs text-gray-400 mt-1 bg-gray-900 p-2 rounded overflow-x-auto max-h-24">
                              {f.snippet}
                            </pre>
                          )}
                        </div>
                        <span className="text-xs text-gray-600 shrink-0">{f.created_at?.slice(11, 19) || ''}</span>
                      </div>
                    ))
                  )}
                </div>
              )}

              {/* 笔记 */}
              {tab === 'notes' && (
                <div className="space-y-3">
                  {notes.length === 0 ? (
                    <p className="text-gray-500 text-sm text-center py-12">暂无笔记</p>
                  ) : (
                    notes.map((n) => (
                      <div key={n.id} className="bg-gray-800 rounded-lg p-3">
                        <div className="flex items-center gap-2 mb-1">
                          {n.tags && n.tags.split(',').map((tag) => (
                            <span key={tag} className="text-xs bg-gray-700 text-gray-400 px-1.5 py-0.5 rounded">
                              {tag.trim()}
                            </span>
                          ))}
                          <span className="text-xs text-gray-600 ml-auto">{n.updated_at?.slice(0, 19) || ''}</span>
                        </div>
                        <p className="text-sm text-gray-300 whitespace-pre-wrap">{n.content}</p>
                      </div>
                    ))
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
