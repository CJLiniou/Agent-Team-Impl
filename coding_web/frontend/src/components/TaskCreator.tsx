/* ═══════════════════════════════════════════════════════════════
   TaskCreator — 创建编码任务表单
   ═══════════════════════════════════════════════════════════════ */

import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import type { CodingTaskCreate, TeamConfig } from '../types';
import { listTeams } from '../api/teams';

const LANGUAGES = [
  { value: 'general', label: '通用' },
  { value: 'python', label: 'Python' },
  { value: 'typescript', label: 'TypeScript' },
  { value: 'javascript', label: 'JavaScript' },
  { value: 'rust', label: 'Rust' },
  { value: 'go', label: 'Go' },
  { value: 'java', label: 'Java' },
  { value: 'cpp', label: 'C++' },
  { value: 'web', label: 'Web' },
];

interface Props {
  onSubmit: (req: CodingTaskCreate) => Promise<void>;
  loading: boolean;
}

export default function TaskCreator({ onSubmit, loading }: Props) {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [language, setLanguage] = useState('general');
  const [mode, setMode] = useState<'simple' | 'team'>('team');
  const [numCoders, setNumCoders] = useState(2);
  const [selectedTeamId, setSelectedTeamId] = useState('');
  const [templates, setTemplates] = useState<TeamConfig[]>([]);

  useEffect(() => {
    listTeams().then(setTemplates).catch(() => {});
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() || !description.trim()) return;

    // 查找选中的团队模板
    let team_config_json: string | undefined;
    if (selectedTeamId) {
      const template = templates.find((t) => t.id === selectedTeamId);
      if (template) {
        team_config_json = JSON.stringify(template);
      }
    }

    const req: CodingTaskCreate = {
      title: title.trim(),
      description: description.trim(),
      language,
      mode,
      num_coders: mode === 'team' ? numCoders : 1,
    };
    if (team_config_json) {
      req.team_config_json = team_config_json;
    }

    await onSubmit(req);
    setTitle('');
    setDescription('');
    setSelectedTeamId('');
  };

  return (
    <form onSubmit={handleSubmit} className="bg-gray-900 border border-gray-800 rounded-lg p-6 space-y-4">
      <h2 className="text-lg font-semibold text-white">创建编码任务</h2>

      {/* 标题 */}
      <div>
        <label className="block text-sm text-gray-400 mb-1">任务标题</label>
        <input
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="例如：实现一个 LRU 缓存"
          className="w-full bg-gray-800 border border-gray-700 rounded-md px-3 py-2 text-white placeholder-gray-500 focus:outline-none focus:border-accent-500 transition-colors"
          required
        />
      </div>

      {/* 描述 */}
      <div>
        <label className="block text-sm text-gray-400 mb-1">任务描述</label>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="详细描述编程需求、约束条件、期望输出..."
          rows={4}
          className="w-full bg-gray-800 border border-gray-700 rounded-md px-3 py-2 text-white placeholder-gray-500 focus:outline-none focus:border-accent-500 transition-colors resize-none"
          required
        />
      </div>

      {/* 配置行 */}
      <div className="flex flex-wrap gap-4">
        {/* 语言 */}
        <div className="flex-1 min-w-[120px]">
          <label className="block text-sm text-gray-400 mb-1">语言</label>
          <select
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
            className="w-full bg-gray-800 border border-gray-700 rounded-md px-3 py-2 text-white focus:outline-none focus:border-accent-500"
          >
            {LANGUAGES.map((l) => (
              <option key={l.value} value={l.value}>{l.label}</option>
            ))}
          </select>
        </div>

        {/* 模式 */}
        <div className="flex-1 min-w-[120px]">
          <label className="block text-sm text-gray-400 mb-1">模式</label>
          <select
            value={mode}
            onChange={(e) => setMode(e.target.value as 'simple' | 'team')}
            className="w-full bg-gray-800 border border-gray-700 rounded-md px-3 py-2 text-white focus:outline-none focus:border-accent-500"
          >
            <option value="team">👥 团队（多智能体）</option>
            <option value="simple">👤 单人（单智能体）</option>
          </select>
        </div>

        {/* Coder 数量（仅团队模式，未选自定义团队时显示） */}
        {mode === 'team' && !selectedTeamId && (
          <div className="w-[100px]">
            <label className="block text-sm text-gray-400 mb-1">Coder 数</label>
            <select
              value={numCoders}
              onChange={(e) => setNumCoders(Number(e.target.value))}
              className="w-full bg-gray-800 border border-gray-700 rounded-md px-3 py-2 text-white focus:outline-none focus:border-accent-500"
            >
              {[1, 2, 3, 4, 5].map((n) => (
                <option key={n} value={n}>{n}</option>
              ))}
            </select>
          </div>
        )}
      </div>

      {/* 自定义团队选择（仅团队模式） */}
      {mode === 'team' && (
        <div className="flex items-end gap-3">
          <div className="flex-1">
            <label className="block text-sm text-gray-400 mb-1">
              使用自定义团队 <span className="text-gray-600">（可选）</span>
            </label>
            <select
              value={selectedTeamId}
              onChange={(e) => setSelectedTeamId(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded-md px-3 py-2 text-white focus:outline-none focus:border-accent-500"
            >
              <option value="">默认团队（Architect + Coders + Reviewer）</option>
              {templates.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}（{t.agents.length} 智能体）
                </option>
              ))}
            </select>
          </div>
          <Link
            to="/teams"
            className="text-xs text-blue-400 hover:text-blue-300 transition-colors pb-2 shrink-0"
          >
            + 新建团队
          </Link>
        </div>
      )}

      {/* 提交按钮 */}
      <button
        type="submit"
        disabled={loading || !title.trim() || !description.trim()}
        className="w-full bg-accent-600 hover:bg-accent-500 disabled:bg-gray-700 disabled:text-gray-500 text-white font-medium py-2.5 rounded-md transition-colors"
      >
        {loading ? '⏳ 正在创建...' : '🚀 开始执行'}
      </button>
    </form>
  );
}
