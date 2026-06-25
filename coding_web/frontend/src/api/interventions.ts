/* ═══════════════════════════════════════════════════════════════
   人工介入 API 调用
   ═══════════════════════════════════════════════════════════════ */

import { api } from './client';

export interface InterventionRecord {
  id: string;
  task_id: string;
  agent_id: string;
  type: 'message' | 'plan_review' | 'redirect' | 'pause' | 'resume';
  content: string;
  response: string;
  metadata: Record<string, unknown>;
  created_at: string;
  processed_at: string;
}

export interface PendingPlan {
  id: string;
  agent_id: string;
  task_id: string;
  content: string;
  status: string;
  created_at: string;
  _expanded?: boolean;
}

export async function injectMessage(taskId: string, agentId: string, content: string): Promise<InterventionRecord> {
  return api.post<InterventionRecord>(`/tasks/${taskId}/intervene`, { agent_id: agentId, content });
}

export async function pauseTask(taskId: string): Promise<InterventionRecord> {
  return api.post<InterventionRecord>(`/tasks/${taskId}/pause`);
}

export async function resumeTask(taskId: string): Promise<InterventionRecord> {
  return api.post<InterventionRecord>(`/tasks/${taskId}/resume`);
}

export async function listInterventions(taskId: string): Promise<InterventionRecord[]> {
  return api.get<InterventionRecord[]>(`/tasks/${taskId}/interventions`);
}

export async function listPendingPlans(taskId: string): Promise<PendingPlan[]> {
  return api.get<PendingPlan[]>(`/tasks/${taskId}/plans/pending`);
}

export async function reviewPlan(taskId: string, planId: string, approved: boolean, reason: string = ''): Promise<void> {
  await api.post(`/tasks/${taskId}/plans/${planId}/review`, { approved, reason });
}

export async function confirmCompletion(taskId: string, feedback?: string): Promise<InterventionRecord> {
  return api.post<InterventionRecord>(`/tasks/${taskId}/complete`, { feedback });
}
