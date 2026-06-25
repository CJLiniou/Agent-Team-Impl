/* ═══════════════════════════════════════════════════════════════
   任务 API 调用
   ═══════════════════════════════════════════════════════════════ */

import { api } from './client';
import type { CodingTask, CodingTaskCreate, AgentState, AgentMessage, FileNode } from '../types';

export async function createTask(req: CodingTaskCreate): Promise<CodingTask> {
  return api.post<CodingTask>('/tasks', req);
}

export async function listTasks(status?: string): Promise<CodingTask[]> {
  const query = status ? `?status=${status}` : '';
  return api.get<CodingTask[]>(`/tasks${query}`);
}

export async function getTask(taskId: string): Promise<CodingTask> {
  return api.get<CodingTask>(`/tasks/${taskId}`);
}

export async function cancelTask(taskId: string): Promise<void> {
  await api.post(`/tasks/${taskId}/cancel`);
}

export async function deleteTask(taskId: string): Promise<void> {
  await api.delete(`/tasks/${taskId}`);
}

export async function continueTask(taskId: string, instructions: string): Promise<CodingTask> {
  return api.post<CodingTask>(`/tasks/${taskId}/continue`, { instructions });
}

export async function getTaskAgents(taskId: string): Promise<AgentState[]> {
  return api.get<AgentState[]>(`/tasks/${taskId}/agents`);
}

export async function getTaskMessages(taskId: string): Promise<AgentMessage[]> {
  return api.get<AgentMessage[]>(`/tasks/${taskId}/messages`);
}

export async function getFileTree(taskId: string): Promise<FileNode[]> {
  return api.get<FileNode[]>(`/tasks/${taskId}/files`);
}

export async function getFileContent(taskId: string, filePath: string): Promise<{ path: string; content: string }> {
  return api.get(`/tasks/${taskId}/files/${encodeURIComponent(filePath)}`);
}

// ── 代码执行 ──────────────────────────────────────────────

export interface ExecuteResult {
  success: boolean;
  stdout: string;
  stderr: string;
  exit_code: number;
  method: 'docker' | 'local';
}

export async function executeCode(taskId: string, command: string, workdir?: string, timeout?: number): Promise<ExecuteResult> {
  return api.post<ExecuteResult>(`/tasks/${taskId}/execute`, { command, workdir, timeout });
}

export async function executePreset(taskId: string, script: string): Promise<ExecuteResult> {
  return api.post<ExecuteResult>(`/tasks/${taskId}/execute/${script}`);
}

export async function getPresets(taskId: string): Promise<Record<string, string>> {
  return api.get(`/tasks/${taskId}/presets`);
}
