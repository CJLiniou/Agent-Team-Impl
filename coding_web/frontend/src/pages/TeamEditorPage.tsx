/* ═══════════════════════════════════════════════════════════════
   TeamEditorPage — 独立的团队编辑器页面
   路由 /teams — 创建、编辑、加载、删除团队模板
   ═══════════════════════════════════════════════════════════════ */

import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import AgentConfigForm from '../components/AgentConfigForm';
import { listTeams, createTeam, updateTeam, deleteTeam, getTeam } from '../api/teams';
import type { TeamConfig, AgentConfig } from '../types';
import { defaultAgentConfig, defaultTeamConfig } from '../types';

export default function TeamEditorPage() {
  // 当前编辑的团队
  const [team, setTeam] = useState<TeamConfig>(defaultTeamConfig());
  // 已保存的模板列表
  const [templates, setTemplates] = useState<TeamConfig[]>([]);
  // 选中的智能体索引
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  // UI 状态
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // 加载模板列表
  const loadTemplates = useCallback(async () => {
    try {
      const data = await listTeams();
      setTemplates(data);
    } catch {
      // 静默
    }
  }, []);

  useEffect(() => {
    loadTemplates();
  }, [loadTemplates]);

  // ── 智能体操作 ─────────────────────────────────────

  const addAgent = () => {
    const agent = defaultAgentConfig();
    setTeam({ ...team, agents: [...team.agents, agent] });
    setSelectedIndex(team.agents.length); // 选中新添加的
  };

  const updateAgent = (index: number, updated: AgentConfig) => {
    const agents = [...team.agents];
    agents[index] = updated;
    setTeam({ ...team, agents });
  };

  const removeAgent = (index: number) => {
    const agents = team.agents.filter((_, i) => i !== index);
    setTeam({ ...team, agents });
    if (selectedIndex != null) {
      if (selectedIndex >= agents.length) {
        setSelectedIndex(agents.length > 0 ? agents.length - 1 : null);
      }
    }
  };

  // ── 保存 / 加载 ─────────────────────────────────────

  const handleSave = async () => {
    if (!team.name.trim()) {
      setMessage({ type: 'error', text: '请输入团队名称' });
      return;
    }
    setSaving(true);
    setMessage(null);
    try {
      if (team.id && templates.some((t) => t.id === team.id)) {
        await updateTeam(team.id, team);
        setMessage({ type: 'success', text: '团队模板已更新' });
      } else {
        const created = await createTeam(team);
        setTeam(created);
        setMessage({ type: 'success', text: '团队模板已创建' });
      }
      await loadTemplates();
    } catch (err) {
      setMessage({ type: 'error', text: err instanceof Error ? err.message : '保存失败' });
    } finally {
      setSaving(false);
    }
  };

  const handleLoad = async (id: string) => {
    try {
      const config = await getTeam(id);
      setTeam(config);
      setSelectedIndex(config.agents.length > 0 ? 0 : null);
      setMessage({ type: 'success', text: `已加载: ${config.name}` });
    } catch {
      setMessage({ type: 'error', text: '加载模板失败' });
    }
  };

  const handleDelete = async (id: string, name: string) => {
    if (!confirm(`删除模板 "${name}"？此操作不可撤销。`)) return;
    try {
      await deleteTeam(id);
      if (team.id === id) {
        setTeam(defaultTeamConfig());
        setSelectedIndex(null);
      }
      await loadTemplates();
      setMessage({ type: 'success', text: `已删除: ${name}` });
    } catch {
      setMessage({ type: 'error', text: '删除失败' });
    }
  };

  const handleNew = () => {
    setTeam(defaultTeamConfig());
    setSelectedIndex(null);
    setMessage(null);
  };

  // ── 渲染 ────────────────────────────────────────────

  const selectedAgent = selectedIndex != null && selectedIndex < team.agents.length
    ? team.agents[selectedIndex]
    : null;

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      {/* 顶部导航 */}
      <header className="border-b border-gray-800 bg-gray-900">
        <div className="max-w-6xl mx-auto px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link to="/" className="text-gray-400 hover:text-white transition-colors text-sm">
              ← 返回主页
            </Link>
            <h1 className="text-lg font-bold text-white">🛠 团队编辑器</h1>
          </div>
          <span className="text-xs text-gray-500">
            智能体 {team.agents.length} 个
          </span>
        </div>
      </header>

      <div className="max-w-6xl mx-auto px-6 py-6">
        {/* 消息提示 */}
        {message && (
          <div className={`mb-4 rounded-lg px-4 py-3 text-sm ${
            message.type === 'success'
              ? 'bg-emerald-500/10 border border-emerald-500/30 text-emerald-400'
              : 'bg-red-500/10 border border-red-500/30 text-red-400'
          }`}>
            {message.text}
          </div>
        )}

        <div className="grid grid-cols-12 gap-6">
          {/* ── 左侧：模板列表 ── */}
          <aside className="col-span-3 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-gray-300">已保存模板</h2>
              <button
                onClick={handleNew}
                className="text-xs text-blue-400 hover:text-blue-300 transition-colors"
              >
                + 新建
              </button>
            </div>

            {templates.length === 0 ? (
              <p className="text-xs text-gray-500">暂无模板，创建一个吧</p>
            ) : (
              <ul className="space-y-1">
                {templates.map((t) => (
                  <li
                    key={t.id}
                    className={`flex items-center justify-between rounded-md px-3 py-2 text-sm cursor-pointer transition-colors ${
                      team.id === t.id
                        ? 'bg-blue-500/10 border border-blue-500/30'
                        : 'bg-gray-900 border border-gray-800 hover:border-gray-700'
                    }`}
                    onClick={() => handleLoad(t.id)}
                  >
                    <div className="min-w-0">
                      <p className="text-gray-200 truncate">{t.name}</p>
                      <p className="text-xs text-gray-500">{t.agents.length} 智能体</p>
                    </div>
                    <button
                      onClick={(e) => { e.stopPropagation(); handleDelete(t.id, t.name); }}
                      className="text-gray-600 hover:text-red-400 text-xs ml-2 shrink-0"
                      title="删除"
                    >
                      ✕
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </aside>

          {/* ── 中间：智能体列表 ── */}
          <section className="col-span-4 space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-gray-300">
                智能体列表
              </h2>
              <button
                onClick={addAgent}
                className="px-3 py-1 rounded bg-blue-600 hover:bg-blue-500 text-white text-xs transition-colors"
              >
                + 添加智能体
              </button>
            </div>

            {team.agents.length === 0 ? (
              <div className="bg-gray-900 border border-gray-800 rounded-lg p-8 text-center text-gray-500">
                <p className="text-3xl mb-2">🤖</p>
                <p className="text-sm">还没有智能体</p>
                <p className="text-xs mt-1">点击"添加智能体"开始构建团队</p>
              </div>
            ) : (
              <div className="space-y-2">
                {team.agents.map((agent, index) => (
                  <div
                    key={agent.id}
                    onClick={() => setSelectedIndex(index)}
                    className={`rounded-lg border px-4 py-3 cursor-pointer transition-colors ${
                      selectedIndex === index
                        ? 'bg-blue-500/10 border-blue-500/40'
                        : 'bg-gray-900 border-gray-800 hover:border-gray-700'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <span className="text-sm text-white font-medium">
                          {agent.name || '(未命名)'}
                        </span>
                        <span className="ml-2 text-xs text-gray-500">
                          {agent.role}
                        </span>
                      </div>
                      <button
                        onClick={(e) => { e.stopPropagation(); removeAgent(index); }}
                        className="text-gray-600 hover:text-red-400 text-xs"
                        title="删除"
                      >
                        ✕
                      </button>
                    </div>
                    {agent.capabilities.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-1.5">
                        {agent.capabilities.slice(0, 3).map((c) => (
                          <span key={c} className="px-1.5 py-0.5 rounded bg-gray-800 text-gray-400 text-2xs"
                            style={{ fontSize: '0.65rem' }}>
                            {c.replace(/_/g, ' ')}
                          </span>
                        ))}
                        {agent.capabilities.length > 3 && (
                          <span className="text-gray-600" style={{ fontSize: '0.65rem' }}>
                            +{agent.capabilities.length - 3}
                          </span>
                        )}
                      </div>
                    )}
                    {/* 标识 */}
                    <div className="flex gap-3 mt-1.5">
                      {agent.allow_fork && (
                        <span className="text-2xs text-purple-400" style={{ fontSize: '0.6rem' }}>🍴 Fork</span>
                      )}
                      {agent.require_plan_approval && (
                        <span className="text-2xs text-amber-400" style={{ fontSize: '0.6rem' }}>📋 审批</span>
                      )}
                      {agent.parent_agent_id && (
                        <span className="text-2xs text-gray-500" style={{ fontSize: '0.6rem' }}>← Forked</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* ── 右侧：配置表单 ── */}
          <section className="col-span-5 space-y-4">
            {/* 团队名称 + 描述 */}
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-5 space-y-3">
              <input
                type="text"
                value={team.name}
                onChange={(e) => setTeam({ ...team, name: e.target.value })}
                placeholder="团队名称"
                className="bg-gray-800 border border-gray-700 rounded-md px-3 py-1.5 text-white text-sm w-full
                           focus:outline-none focus:border-blue-500 placeholder-gray-500"
              />
              <textarea
                value={team.description}
                onChange={(e) => setTeam({ ...team, description: e.target.value })}
                placeholder="团队描述（可选）"
                rows={2}
                className="bg-gray-800 border border-gray-700 rounded-md px-3 py-2 text-sm text-gray-200 w-full
                           focus:outline-none focus:border-blue-500 placeholder-gray-500 resize-none"
              />
              <button
                onClick={handleSave}
                disabled={saving}
                className="w-full py-2 rounded-md bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50
                           text-white text-sm font-medium transition-colors"
              >
                {saving ? '保存中...' : team.id && templates.some((t) => t.id === team.id) ? '更新模板' : '保存模板'}
              </button>
            </div>

            {/* 智能体配置表单 */}
            {selectedAgent ? (
              <AgentConfigForm
                agent={selectedAgent}
                onChange={(updated) => updateAgent(selectedIndex!, updated)}
                onDelete={() => removeAgent(selectedIndex!)}
              />
            ) : (
              <div className="bg-gray-900 border border-gray-800 rounded-lg p-8 text-center text-gray-500">
                <p className="text-2xl mb-2">👈</p>
                <p className="text-sm">选择一个智能体查看/编辑配置</p>
                <p className="text-xs mt-1">或点击"添加智能体"创建新的</p>
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
