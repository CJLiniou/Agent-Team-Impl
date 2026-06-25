/* ═══════════════════════════════════════════════════════════════
   智能体记忆 API 调用
   ═══════════════════════════════════════════════════════════════ */

import { api } from './client';

export interface MemorySummary {
  agent_id: string;
  task_id: string;
  conversation_count: number;
  decision_count: number;
  file_change_count: number;
  note_count: number;
  latest_summary: string;
}

export interface ConversationEntry {
  id: number;
  role: string;
  content: string;
  tool_name: string;
  tool_input: string;
  tool_output: string;
  token_count: number;
  created_at: string;
}

export interface DecisionEntry {
  id: number;
  context: string;
  decision: string;
  reasoning: string;
  outcome: string;
  created_at: string;
}

export interface FileChangeEntry {
  id: number;
  file_path: string;
  operation: string;
  snippet: string;
  created_at: string;
}

export interface NoteEntry {
  id: number;
  content: string;
  tags: string;
  created_at: string;
  updated_at: string;
}

export async function getMemorySummary(taskId: string, agentId: string): Promise<MemorySummary> {
  return api.get<MemorySummary>(`/tasks/${taskId}/agents/${agentId}/memory`);
}

export async function getConversation(
  taskId: string, agentId: string, limit = 50, offset = 0
): Promise<{ items: ConversationEntry[]; total: number; limit: number; offset: number }> {
  return api.get(`/tasks/${taskId}/agents/${agentId}/memory/conversation?limit=${limit}&offset=${offset}`);
}

export async function getDecisions(taskId: string, agentId: string, limit = 20): Promise<DecisionEntry[]> {
  return api.get<DecisionEntry[]>(`/tasks/${taskId}/agents/${agentId}/memory/decisions?limit=${limit}`);
}

export async function getFileChanges(taskId: string, agentId: string, limit = 30): Promise<FileChangeEntry[]> {
  return api.get<FileChangeEntry[]>(`/tasks/${taskId}/agents/${agentId}/memory/files?limit=${limit}`);
}

export async function getNotes(taskId: string, agentId: string): Promise<NoteEntry[]> {
  return api.get<NoteEntry[]>(`/tasks/${taskId}/agents/${agentId}/memory/notes`);
}
