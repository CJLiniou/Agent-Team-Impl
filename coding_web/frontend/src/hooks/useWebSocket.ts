/* ═══════════════════════════════════════════════════════════════
   WebSocket Hook — 连接实时事件流并更新 Zustand store
   ═══════════════════════════════════════════════════════════════ */

import { useEffect, useRef } from 'react';
import { useTaskStore } from '../store/taskStore';
import type { ServerEvent, AgentState, AgentMessage, AgentTask, LogEntry, CodingTask } from '../types';

export function useWebSocket(taskId: string | null) {
  const store = useTaskStore();
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const retryCount = useRef(0);

  useEffect(() => {
    if (!taskId) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/tasks/${taskId}`;

    function connect() {
      if (wsRef.current?.readyState === WebSocket.OPEN) return;

      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        store.setWsConnected(true);
        retryCount.current = 0;
      };

      ws.onmessage = (event) => {
        try {
          const serverEvent: ServerEvent = JSON.parse(event.data);
          handleEvent(serverEvent, store);
        } catch {
          // ignore parse errors
        }
      };

      ws.onclose = () => {
        store.setWsConnected(false);
        wsRef.current = null;

        // 拉取最新任务状态
        import('../api/tasks').then(({ getTask }) =>
          getTask(taskId!).then((t) => {
            store.setTask(t);
            // 仍在运行 → 意外断连 → 重连（服务端 connect() 会自行判断是否启动 push loop）
            if (t.status === 'running' || t.status === 'pending') {
              const delay = Math.min(1000 * Math.pow(2, retryCount.current), 30000);
              retryCount.current += 1;
              reconnectTimer.current = setTimeout(connect, delay);
            }
          }).catch(() => {})
        );
      };

      ws.onerror = () => {
        ws.close();
      };
    }

    connect();

    return () => {
      if (reconnectTimer.current) {
        clearTimeout(reconnectTimer.current);
      }
      if (wsRef.current) {
        wsRef.current.onclose = null;
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [taskId]);  // 只依赖 taskId，避免 isRunning 变化时断开重连导致丢事件
}

function handleEvent(event: ServerEvent, store: ReturnType<typeof useTaskStore.getState>) {
  store.addEvent(event);

  switch (event.type) {
    case 'snapshot': {
      const data = event.data as Record<string, unknown>;
      if (data.agents) {
        store.setAgents(data.agents as AgentState[]);
      }
      if (data.tasks) {
        store.setTaskQueue(data.tasks as AgentTask[]);
      }
      if (data.messages) {
        store.setMessages(data.messages as AgentMessage[]);
      }
      if (data.logs) {
        store.setLogs(data.logs as LogEntry[]);
      }
      // 同步 coding task 状态（推送 loop 每 2s 带最新状态）
      if (data.task_status) {
        const ts = data.task_status as Record<string, unknown>;
        if (store.task) {
          store.setTask({
            ...store.task,
            status: (ts.status as CodingTask['status']) || store.task.status,
            result: (ts.result as string) || store.task.result,
            error_message: (ts.error_message as string) || store.task.error_message,
          });
        }
      }
      break;
    }

    case 'agent_state_changed': {
      const agent = (event.data as Record<string, unknown>).agent as AgentState;
      if (agent) {
        store.updateAgent(agent.id, agent);
      }
      // agent 上线说明任务已启动——如果仍是 pending 则刷新状态
      if (store.task?.status === 'pending') {
        import('../api/tasks').then(({ getTask }) =>
          getTask(event.taskId).then((t) => store.setTask(t)).catch(() => {})
        );
      }
      break;
    }

    case 'agent_step': {
      const data = event.data as Record<string, unknown>;
      const name = data.name as string;
      const action = data.action as string;
      if (name && action) {
        store.addLog({ level: 'info', message: action, name, timestamp: event.timestamp });
      }
      if (store.task?.status === 'pending') {
        import('../api/tasks').then(({ getTask }) =>
          getTask(event.taskId).then((t) => store.setTask(t)).catch(() => {})
        );
      }
      break;
    }

    case 'task_status_changed': {
      const task = (event.data as Record<string, unknown>).task as AgentTask;
      if (task) {
        store.updateTaskQueueItem(task.id, task);
      }
      break;
    }

    case 'message_sent': {
      const msg = (event.data as Record<string, unknown>).message as AgentMessage;
      if (msg) {
        store.addMessage(msg);
      }
      break;
    }

    case 'tool_call': {
      const data = event.data as Record<string, unknown>;
      const name = data.name as string;
      const tool = data.tool as string;
      store.addLog({
        level: 'info',
        message: `→ ${tool}`,
        name: name || '',
        timestamp: event.timestamp,
      });
      break;
    }

    case 'sandbox_file_changed': {
      // 文件变更时，前端可以主动刷新文件树
      break;
    }

    case 'log_entry': {
      const data = event.data as Record<string, unknown>;
      store.addLog({
        level: (data.level as LogEntry['level']) || 'info',
        message: data.message as string,
        name: (data.name as string) || '',
        timestamp: event.timestamp,
      });
      break;
    }

    case 'run_completed': {
      // 任务完成：从 API 拉取完整最终状态（事件中的 result 可能被截断）
      const data = event.data as Record<string, unknown>;
      const status = data.status as string;
      store.setWsConnected(false);
      if (event.taskId) {
        // 异步拉取完整任务数据
        import('../api/tasks').then(({ getTask, getTaskAgents, getTaskMessages }) => {
          Promise.all([
            getTask(event.taskId),
            getTaskAgents(event.taskId),
            getTaskMessages(event.taskId),
          ]).then(([task, agents, messages]) => {
            store.setTask(task);
            if (agents.length > 0) store.setAgents(agents);
            if (messages.length > 0) store.setMessages(messages);
          }).catch(() => {});
        });
      }
      break;
    }

    case 'intervention_received': {
      store.addLog({
        level: 'info',
        message: `介入: ${(event.data as Record<string,unknown>).type || ''} → ${(event.data as Record<string,unknown>).agent_id || 'ALL'}`,
        name: 'supervisor',
        timestamp: event.timestamp,
      });
      break;
    }

    case 'agent_forked': {
      const data = event.data as Record<string, unknown>;
      store.addLog({
        level: 'info',
        message: `🍴 Fork: ${data.parent_name || ''} → ${data.child_name || ''} (${data.reason || ''})`,
        name: (data.parent_name as string) || 'system',
        timestamp: event.timestamp,
      });
      break;
    }

    case 'task_paused': {
      store.addLog({
        level: 'warn',
        message: '⏸ 任务已暂停',
        name: 'supervisor',
        timestamp: event.timestamp,
      });
      break;
    }

    case 'task_resumed': {
      store.addLog({
        level: 'info',
        message: '▶ 任务已恢复',
        name: 'supervisor',
        timestamp: event.timestamp,
      });
      break;
    }

    case 'error': {
      const data = event.data as Record<string, unknown>;
      store.addLog({
        level: 'error',
        message: data.error as string,
        name: (data.source as string) || 'system',
        timestamp: event.timestamp,
      });
      break;
    }
  }
}

