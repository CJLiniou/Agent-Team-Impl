/* ═══════════════════════════════════════════════════════════════
   AgentConfigForm — 单个智能体的配置表单
   ═══════════════════════════════════════════════════════════════ */

import { useState } from 'react';
import type { AgentConfig } from '../types';

const ROLE_LABELS: Record<string, string> = {
  executor: '执行者 (Executor)',
  coordinator: '协调者 (Coordinator)',
  reviewer: '审查者 (Reviewer)',
  specialist: '专家 (Specialist)',
};

interface CapabilityInfo {
  label: string;
  desc: string;
  promptSnippet: string;
}

const CAPABILITY_MAP: Record<string, CapabilityInfo> = {
  code_generation: {
    label: '代码生成',
    desc: '编写干净、高效的代码',
    promptSnippet: '## 代码生成能力\n你擅长编写代码。写干净、高效、有注释的代码，遵循目标语言的最佳实践。',
  },
  debugging: {
    label: '调试',
    desc: '定位和修复 bug',
    promptSnippet: '## 调试能力\n你擅长调试。系统性地定位根因，先复现问题，再隔离变量，最后应用最小修复。',
  },
  file_operations: {
    label: '文件操作',
    desc: '读写项目文件',
    promptSnippet: '## 文件操作能力\n你可以读写项目文件。修改前先 read_file 了解现有代码，write_file 保持清晰的文件结构。',
  },
  code_review: {
    label: '代码审查',
    desc: '审查代码质量和规范',
    promptSnippet: '## 代码审查能力\n你审查代码的正确性、可读性、可维护性和规范遵循。给出具体建议但不要重写全部代码。',
  },
  problem_decomposition: {
    label: '问题拆解',
    desc: '拆分复杂问题为子任务，需提交计划',
    promptSnippet: '## 问题拆解能力\n你将复杂问题分解为独立、可并行的子任务。定义清晰的组件接口。拆解后提交计划供审批。',
  },
  architecture_design: {
    label: '架构设计',
    desc: '设计系统架构，可 Fork 子智能体',
    promptSnippet: '## 架构设计能力\n你设计系统架构，考虑可扩展性、可靠性、可维护性。定义组件边界、数据流和技术选型。可以 fork 子智能体并行实现各组件。',
  },
  task_planning: {
    label: '任务规划',
    desc: '创建执行计划，需审批',
    promptSnippet: '## 任务规划能力\n你创建详细的执行计划，包含里程碑、依赖关系和工期估算。执行前提交计划供审查。',
  },
  bug_detection: {
    label: '缺陷检测',
    desc: '扫描代码逻辑错误和边界情况',
    promptSnippet: '## 缺陷检测能力\n你扫描代码中的逻辑错误、边界情况、竞态条件、资源泄漏等问题。对每个缺陷报告严重程度和复现步骤。',
  },
  quality_assurance: {
    label: '质量保证',
    desc: '验证代码符合需求',
    promptSnippet: '## 质量保证能力\n你验证代码是否满足需求、边界情况是否处理、测试覆盖是否充分。以明确的验收标准来评估。',
  },
  security_audit: {
    label: '安全审查',
    desc: 'OWASP Top 10 漏洞审计（只读）',
    promptSnippet: (
      '## 安全审计能力\n'
      + '你专注于 OWASP Top 10 和常见安全漏洞的审计。\n'
      + '检查: SQL注入、XSS、认证绕过、敏感数据泄露、越权访问、安全配置错误、不安全的反序列化。\n'
      + '对每个发现报告: 严重程度(严重/高/中/低)、漏洞类型、受影响代码位置、影响范围和修复建议。\n'
      + '⛔ 你是只读的 — 只能报告发现，不能修改代码。如需修复，用 publish_task 发布。'
    ),
  },
  performance_analysis: {
    label: '性能分析',
    desc: '识别性能瓶颈和优化点',
    promptSnippet: '## 性能分析能力\n你识别性能瓶颈: O(n)复杂度问题、不必要的内存分配、阻塞I/O、N+1查询等。给出优化建议和预期效果。',
  },
  system_design: {
    label: '系统设计',
    desc: '端到端系统设计，可 Fork + 写代码',
    promptSnippet: '## 系统设计能力\n你设计端到端系统，产出清晰的设计文档和可工作的代码。可以 fork 子智能体并行实现各组件。',
  },
  testing: {
    label: '测试',
    desc: '编写单元/集成/回归测试',
    promptSnippet: '## 测试能力\n你编写全面的测试: 单元测试、集成测试、边界测试、回归测试。追求高覆盖率，测试行为而非实现细节。',
  },
};

const CAPABILITY_OPTIONS = Object.keys(CAPABILITY_MAP);

interface Props {
  agent: AgentConfig;
  onChange: (updated: AgentConfig) => void;
  onDelete: () => void;
}

// 角色基础提示词预览（中文，与后端 ROLE_PROMPTS 对应）
const ROLE_PREVIEWS: Record<string, string> = {
  executor: '执行者: 负责完成编码和实现任务。claim → 实现 → complete，一次一个任务。',
  coordinator: '协调者: 负责分解需求、发布任务、监控进度。不直接写代码，通过 publish_task 分配工作。',
  reviewer: '审查者: 负责代码质量把关。只读不写，发现问题用 publish_task 发布修复任务。',
  specialist: '专家: 独立解决问题。claim → 分析 → 实现 → complete，一步到位。',
};

export default function AgentConfigForm({ agent, onChange, onDelete }: Props) {
  const update = (patch: Partial<AgentConfig>) => onChange({ ...agent, ...patch });

  const toggleCapability = (cap: string) => {
    const caps = agent.capabilities.includes(cap)
      ? agent.capabilities.filter((c) => c !== cap)
      : [...agent.capabilities, cap];
    update({ capabilities: caps });
  };

  const [showPreview, setShowPreview] = useState(false);

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-5 space-y-4">
      {/* 头部：名称 + 删除按钮 */}
      <div className="flex items-center justify-between">
        <input
          type="text"
          value={agent.name}
          onChange={(e) => update({ name: e.target.value })}
          placeholder="智能体名称，如 Coder-1"
          className="bg-gray-800 border border-gray-700 rounded-md px-3 py-1.5 text-white text-sm w-48
                     focus:outline-none focus:border-blue-500 placeholder-gray-500"
        />
        <button
          onClick={onDelete}
          className="text-gray-500 hover:text-red-400 text-sm transition-colors"
          title="删除此智能体"
        >
          ✕ 删除
        </button>
      </div>

      {/* 角色选择 */}
      <div>
        <label className="block text-xs text-gray-400 mb-1.5">角色</label>
        <select
          value={agent.role}
          onChange={(e) => update({ role: e.target.value as AgentConfig['role'] })}
          className="bg-gray-800 border border-gray-700 rounded-md px-3 py-1.5 text-sm text-gray-200 w-full
                     focus:outline-none focus:border-blue-500"
        >
          {Object.entries(ROLE_LABELS).map(([value, label]) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </select>
      </div>

      {/* 角色基础提示词（只读） */}
      <div>
        <label className="block text-xs text-gray-400 mb-1.5">角色行为准则（自动生成）</label>
        <div className="bg-gray-800/50 border border-gray-700/50 rounded-md px-3 py-2 text-xs text-gray-400 leading-relaxed">
          {ROLE_PREVIEWS[agent.role] || '选择角色以查看行为准则'}
        </div>
      </div>

      {/* 用户自定义补充指令 */}
      <div>
        <label className="block text-xs text-gray-400 mb-1.5">
          自定义补充指令 <span className="text-gray-600">（可选，追加到角色和能力提示词之后）</span>
        </label>
        <textarea
          value={agent.system_prompt}
          onChange={(e) => update({ system_prompt: e.target.value })}
          placeholder="额外指令，如: 用中文回复、优先检查性能、生成 JSDoc 注释..."
          rows={3}
          className="bg-gray-800 border border-gray-700 rounded-md px-3 py-2 text-sm text-gray-200 w-full
                     focus:outline-none focus:border-blue-500 placeholder-gray-500 resize-y"
        />
      </div>

      {/* 最终提示词预览 */}
      <div>
        <button
          type="button"
          onClick={() => setShowPreview(!showPreview)}
          className="text-xs text-gray-500 hover:text-gray-300 transition-colors"
        >
          {showPreview ? '▼ 隐藏' : '▶ 展开'} 最终提示词预览
          {agent.is_leader && <span className="ml-1 text-amber-400">(Leader)</span>}
        </button>
        {showPreview && (
          <div className="mt-2 bg-gray-950 border border-gray-700 rounded-md p-3 text-xs text-gray-300 max-h-48 overflow-y-auto whitespace-pre-wrap leading-relaxed">
            <PreviewContent agent={agent} />
          </div>
        )}
      </div>

      {/* 能力标签 */}
      <div>
        <label className="block text-xs text-gray-400 mb-1.5">能力标签</label>
        <div className="flex flex-wrap gap-1.5">
          {CAPABILITY_OPTIONS.map((cap) => {
            const active = agent.capabilities.includes(cap);
            const info = CAPABILITY_MAP[cap];
            return (
              <button
                key={cap}
                onClick={() => toggleCapability(cap)}
                title={info?.desc || cap}
                className={`px-2 py-0.5 rounded text-xs transition-colors ${
                  active
                    ? 'bg-blue-500/20 text-blue-300 border border-blue-500/40'
                    : 'bg-gray-800 text-gray-500 border border-gray-700 hover:border-gray-600'
                }`}
              >
                {info?.label || cap.replace(/_/g, ' ')}
                {info?.desc && (
                  <span className="ml-1 text-gray-600 hidden sm:inline">· {info.desc}</span>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* 模型 + Token */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs text-gray-400 mb-1.5">模型</label>
          <input
            type="text"
            value={agent.model}
            onChange={(e) => update({ model: e.target.value })}
            placeholder="默认"
            className="bg-gray-800 border border-gray-700 rounded-md px-3 py-1.5 text-sm text-gray-200 w-full
                       focus:outline-none focus:border-blue-500 placeholder-gray-500"
          />
        </div>
        <div>
          <label className="block text-xs text-gray-400 mb-1.5">最大 Token</label>
          <input
            type="number"
            value={agent.max_tokens}
            onChange={(e) => update({ max_tokens: Number(e.target.value) || 4096 })}
            className="bg-gray-800 border border-gray-700 rounded-md px-3 py-1.5 text-sm text-gray-200 w-full
                       focus:outline-none focus:border-blue-500"
          />
        </div>
      </div>

      {/* 开关选项 — 第一行：团队角色 */}
      <div className="flex gap-6">
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={agent.is_leader}
            onChange={(e) => {
              update({
                is_leader: e.target.checked,
                can_publish_tasks: e.target.checked || agent.can_publish_tasks,
              });
            }}
            className="rounded bg-gray-800 border-gray-600 text-amber-500 focus:ring-amber-500"
          />
          <span className="text-xs text-amber-400 font-medium">👑 Leader（用户接口人）</span>
        </label>

        <label className={`flex items-center gap-2 ${agent.is_leader ? 'opacity-50' : 'cursor-pointer'}`}>
          <input
            type="checkbox"
            checked={agent.can_publish_tasks}
            disabled={agent.is_leader}
            onChange={(e) => update({ can_publish_tasks: e.target.checked })}
            className="rounded bg-gray-800 border-gray-600 text-purple-500 focus:ring-purple-500"
          />
          <span className="text-xs text-purple-400">📤 可发布任务</span>
        </label>
      </div>

      {/* 开关选项 — 第二行：其他控制 */}
      <div className="flex gap-6">
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={agent.require_plan_approval}
            onChange={(e) => update({ require_plan_approval: e.target.checked })}
            className="rounded bg-gray-800 border-gray-600 text-blue-500 focus:ring-blue-500"
          />
          <span className="text-xs text-gray-300">需计划审批</span>
        </label>

        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={agent.allow_fork}
            onChange={(e) => update({ allow_fork: e.target.checked })}
            className="rounded bg-gray-800 border-gray-600 text-blue-500 focus:ring-blue-500"
          />
          <span className="text-xs text-gray-300">允许 Fork</span>
        </label>

        {agent.allow_fork && (
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-gray-400">上限</span>
            <input
              type="number"
              value={agent.fork_limit}
              onChange={(e) => update({ fork_limit: Number(e.target.value) || 1 })}
              min={1}
              max={10}
              className="bg-gray-800 border border-gray-700 rounded px-2 py-0.5 text-xs text-gray-200 w-14
                         focus:outline-none focus:border-blue-500"
            />
          </div>
        )}
      </div>
    </div>
  );
}

// ── 最终提示词预览组件 ─────────────────────────────

const ROLE_FULL_PREVIEWS: Record<string, string> = {
  executor: (
    '## 角色: 执行者\n'
    + '你是团队的执行者，负责完成具体的编码和实现任务。\n\n'
    + '工作准则:\n'
    + '- 一次只做一个任务: claim_task → 完成 → complete_task\n'
    + '- 动手前先 read_file 了解已有代码\n'
    + '- write_file 之后立刻 complete_task，不要反复修改\n'
    + '- 有问题用 send_message 联系 Leader\n'
    + '- 不要自己发布任务，你的职责是实现而非规划'
  ),
  coordinator: (
    '## 角色: 协调者\n'
    + '你是团队的协调者，负责任务分解和进度管理。\n\n'
    + '工作准则:\n'
    + '- 收到需求后先分析，再用 publish_task 拆分为独立的子任务\n'
    + '- 每个子任务写清楚: 做什么、验收标准\n'
    + '- 通过 list_tasks 监控进度，但不要微管理\n'
    + '- 所有子任务完成后汇总结果，向用户汇报\n'
    + '- 询问用户是否还有需求，用户确认后才算完成'
  ),
  reviewer: (
    '## 角色: 审查者\n'
    + '你是团队的代码审查者，负责质量把关。\n\n'
    + '工作准则:\n'
    + '- 只审查，不写代码 — 你没有 write_file 权限\n'
    + '- 用 read_file 逐一检查待审查的文件\n'
    + '- 检查: 正确性、边界处理、错误处理、代码规范、安全漏洞\n'
    + '- 发现问题 → publish_task 发布修复任务\n'
    + '- 修复完成后重新 read_file 确认\n'
    + '- 审查通过后用 complete_task 提交审查报告'
  ),
  specialist: (
    '## 角色: 专家\n'
    + '你是独立解决问题的专家，独自完成任务。\n\n'
    + '工作准则:\n'
    + '- claim_task → 分析 → 实现 → complete_task，一步到位\n'
    + '- 用 write_file 产出最终代码\n'
    + '- complete_task 时附上简短的解决方案说明'
  ),
};

const LEADER_PREVIEW = (
  '\n\n## 团队 Leader 职责\n'
  + '你是本团队的 Leader，是用户的唯一接口。\n'
  + '1. 接受用户需求并理解完整范围\n'
  + '2. 将需求拆分为可并行执行的子任务\n'
  + '3. 监控进度但不微管理\n'
  + '4. 汇总结果向用户报告\n'
  + '5. 项目不能单方面结束 — 必须询问用户确认'
);

function PreviewContent({ agent }: { agent: AgentConfig }) {
  const lines: string[] = [];

  // 1. 角色基础
  const rolePreview = ROLE_FULL_PREVIEWS[agent.role];
  if (rolePreview) lines.push(rolePreview);

  // 2. Leader 追加
  if (agent.is_leader) lines.push(LEADER_PREVIEW);

  // 3. 能力追加
  for (const cap of agent.capabilities) {
    const info = (CAPABILITY_MAP as Record<string, { promptSnippet: string }>)[cap];
    if (info?.promptSnippet) lines.push(info.promptSnippet);
  }

  // 4. 用户补充
  if (agent.system_prompt.trim()) {
    lines.push(`## 用户补充指令\n${agent.system_prompt.trim()}`);
  }

  return <>{lines.join('\n\n') || '(选择角色和能力后在此预览最终提示词)'}</>;
}
