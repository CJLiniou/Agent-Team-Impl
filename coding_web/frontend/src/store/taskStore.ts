/* ═══════════════════════════════════════════════════════════════
   Zustand 全局状态 — 编码任务的实时状态管理
   ═══════════════════════════════════════════════════════════════ */

import { create } from 'zustand';
import type { CodingTask, AgentState, AgentMessage, AgentTask, ServerEvent, LogEntry, FileNode } from '../types';

interface TaskStore {
  // ── 当前任务 ──
  task: CodingTask | null;
  setTask: (task: CodingTask | null) => void;

  // ── 智能体 ──
  agents: Map<string, AgentState>;
  setAgents: (agents: AgentState[]) => void;
  updateAgent: (id: string, partial: Partial<AgentState>) => void;

  // ── 消息 ──
  messages: AgentMessage[];
  setMessages: (msgs: AgentMessage[]) => void;
  addMessage: (msg: AgentMessage) => void;

  // ── 智能体内部任务队列 ──
  taskQueue: AgentTask[];
  setTaskQueue: (tasks: AgentTask[]) => void;
  updateTaskQueueItem: (id: string, partial: Partial<AgentTask>) => void;

  // ── 事件日志 ──
  events: ServerEvent[];
  addEvent: (event: ServerEvent) => void;

  // ── 日志条目 ──
  logs: LogEntry[];
  setLogs: (logs: LogEntry[]) => void;
  addLog: (log: LogEntry) => void;

  // ── 沙盒文件 ──
  fileTree: FileNode[];
  setFileTree: (tree: FileNode[]) => void;
  selectedFilePath: string | null;
  selectedFileContent: string;
  selectFile: (path: string, content: string) => void;
  setFileContent: (content: string) => void;

  // ── WebSocket 连接状态 ──
  wsConnected: boolean;
  setWsConnected: (connected: boolean) => void;

  // ── 运行状态 ──
  isRunning: boolean;

  // ── 重置 ──
  reset: () => void;
}

const initialState = {
  task: null,
  agents: new Map<string, AgentState>(),
  messages: [],
  taskQueue: [],
  events: [],
  logs: [],
  fileTree: [],
  selectedFilePath: null,
  selectedFileContent: '',
  wsConnected: false,
  isRunning: false,
};

export const useTaskStore = create<TaskStore>((set, get) => ({
  ...initialState,

  setTask: (task) => set({ task, isRunning: task?.status === 'running' }),

  setAgents: (agents) => {
    const map = new Map<string, AgentState>();
    agents.forEach((a) => map.set(a.id, a));
    set({ agents: map });
  },

  updateAgent: (id, partial) => {
    const agents = new Map(get().agents);
    const existing = agents.get(id);
    if (existing) {
      agents.set(id, { ...existing, ...partial });
      set({ agents });
    }
  },

  setMessages: (messages) => set({ messages }),

  addMessage: (msg) => {
    set((state) => ({ messages: [...state.messages, msg].slice(-100) }));
  },

  setTaskQueue: (tasks) => set({ taskQueue: tasks }),

  updateTaskQueueItem: (id, partial) => {
    set((state) => ({
      taskQueue: state.taskQueue.map((t) => (t.id === id ? { ...t, ...partial } : t)),
    }));
  },

  addEvent: (event) => {
    set((state) => ({ events: [...state.events, event].slice(-200) }));
  },

  setLogs: (logs) => set({ logs }),

  addLog: (log) => {
    set((state) => ({ logs: [...state.logs, log].slice(-100) }));
  },

  setFileTree: (tree) => set({ fileTree: tree }),

  selectFile: (path, content) => set({ selectedFilePath: path, selectedFileContent: content }),

  setFileContent: (content) => set({ selectedFileContent: content }),

  setWsConnected: (connected) => set({ wsConnected: connected }),

  reset: () => set(initialState),
}));
