/* ═══════════════════════════════════════════════════════════════
   TypeScript 类型定义 — 与后端 Pydantic 模型对应
   ═══════════════════════════════════════════════════════════════ */

// ── 编码任务 ──────────────────────────────────────────────

export interface CodingTask {
  id: string;
  title: string;
  description: string;
  language: string;
  mode: 'simple' | 'team';
  num_coders: number;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  sandbox_path: string;
  result: string;
  error_message: string;
  model: string;
  max_tokens: number;
  stats: TaskStats;
  team_config?: TeamConfig;
  created_at: string;
  started_at: string;
  completed_at: string;
}

export interface TaskStats {
  total_completed_tasks?: number;
  total_failed_tasks?: number;
  token_usage?: TokenUsage;
}

export interface TokenUsage {
  total_tokens: number;
  total_cost: number;
  by_agent: Record<string, AgentTokenUsage>;
}

export interface AgentTokenUsage {
  name: string;
  input_tokens: number;
  output_tokens: number;
  cost: number;
}

export interface CodingTaskCreate {
  title: string;
  description: string;
  language?: string;
  mode?: 'simple' | 'team';
  num_coders?: number;
  model?: string;
  max_tokens?: number;
  team_config_json?: string;
}

// ── 智能体 ────────────────────────────────────────────────

export interface AgentState {
  id: string;
  name: string;
  role: 'executor' | 'coordinator' | 'reviewer' | 'specialist';
  state: 'idle' | 'busy' | 'waiting' | 'error';
  current_task_id: string;
  current_action: string;
  completed_tasks: number;
  failed_tasks: number;
  error_message: string;
  last_heartbeat: string;
  parent_agent_name?: string;
  allow_fork?: boolean;
}

// ── 消息 ──────────────────────────────────────────────────

export interface AgentMessage {
  id: string;
  sender: string;
  recipient: string;
  subject: string;
  content: string;
  status: 'sent' | 'delivered' | 'read' | 'failed';
  created_at: string;
}

// ── 智能体内部任务 ────────────────────────────────────────

export interface AgentTask {
  id: string;
  name: string;
  description: string;
  status: 'pending' | 'in_progress' | 'completed' | 'failed' | 'blocked';
  assigned_to: string;
  priority: number;
  result: string;
}

// ── WebSocket 事件 ────────────────────────────────────────

export type EventType =
  | 'snapshot'
  | 'agent_state_changed'
  | 'agent_step'
  | 'task_status_changed'
  | 'message_sent'
  | 'tool_call'
  | 'sandbox_file_changed'
  | 'log_entry'
  | 'run_completed'
  | 'error'
  | 'intervention_received'
  | 'agent_forked'
  | 'task_paused'
  | 'task_resumed';

export interface ServerEvent {
  type: EventType;
  taskId: string;
  timestamp: string;
  data: Record<string, unknown>;
}

// ── 日志条目 ──────────────────────────────────────────────

export interface LogEntry {
  level: 'info' | 'warn' | 'error';
  message: string;
  name: string;
  timestamp: string;
}

// ── 沙盒文件 ──────────────────────────────────────────────

export interface FileNode {
  name: string;
  path: string;
  type: 'file' | 'dir';
  children: FileNode[];
}

// ── 团队配置 ──────────────────────────────────────────────

export interface AgentConfig {
  id: string;
  name: string;
  role: 'executor' | 'coordinator' | 'reviewer' | 'specialist';
  capabilities: string[];
  system_prompt: string;
  model: string;
  max_tokens: number;
  require_plan_approval: boolean;
  allow_fork: boolean;
  fork_limit: number;
  tools_allowlist: string[];
  is_leader: boolean;
  can_publish_tasks: boolean;
  parent_agent_id: string | null;
  metadata: Record<string, unknown>;
}

export interface TeamConfig {
  id: string;
  name: string;
  description: string;
  agents: AgentConfig[];
  leader_agent_id: string;
  communication_rules: Record<string, unknown>;
  fork_policy: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export function defaultAgentConfig(overrides?: Partial<AgentConfig>): AgentConfig {
  return {
    id: crypto.randomUUID(),
    name: '',
    role: 'executor',
    capabilities: [],
    system_prompt: '',
    model: '',
    max_tokens: 4096,
    require_plan_approval: false,
    allow_fork: false,
    fork_limit: 3,
    tools_allowlist: [],
    is_leader: false,
    can_publish_tasks: false,
    parent_agent_id: null,
    metadata: {},
    ...overrides,
  };
}

export function defaultTeamConfig(overrides?: Partial<TeamConfig>): TeamConfig {
  return {
    id: crypto.randomUUID(),
    name: '',
    description: '',
    agents: [],
    leader_agent_id: '',
    communication_rules: {},
    fork_policy: {},
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    ...overrides,
  };
}
