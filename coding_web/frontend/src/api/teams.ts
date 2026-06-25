/* ═══════════════════════════════════════════════════════════════
   团队配置 API 调用
   ═══════════════════════════════════════════════════════════════ */

import { api } from './client';
import type { TeamConfig } from '../types';

export async function createTeam(config: TeamConfig): Promise<TeamConfig> {
  return api.post<TeamConfig>('/teams', config);
}

export async function listTeams(): Promise<TeamConfig[]> {
  return api.get<TeamConfig[]>('/teams');
}

export async function getTeam(id: string): Promise<TeamConfig> {
  return api.get<TeamConfig>(`/teams/${id}`);
}

export async function updateTeam(id: string, config: TeamConfig): Promise<TeamConfig> {
  return api.put<TeamConfig>(`/teams/${id}`, config);
}

export async function deleteTeam(id: string): Promise<void> {
  await api.delete(`/teams/${id}`);
}
