/* ═══════════════════════════════════════════════════════════════
   ExecutionPanel — 沙盒代码执行面板（Run 按钮 + 输出显示）
   ═══════════════════════════════════════════════════════════════ */

import { useState } from 'react';
import { useTaskStore } from '../store/taskStore';
import { executeCode, executePreset, type ExecuteResult } from '../api/tasks';

const PRESET_BUTTONS = [
  { script: 'run', label: '▶ 运行', icon: '▶' },
  { script: 'test', label: '🧪 测试', icon: '🧪' },
  { script: 'build', label: '🔨 构建', icon: '🔨' },
  { script: 'lint', label: '🔍 检查', icon: '🔍' },
];

export default function ExecutionPanel() {
  const taskId = useTaskStore((s) => s.task?.id);
  const [command, setCommand] = useState('');
  const [running, setRunning] = useState(false);
  const [results, setResults] = useState<ExecuteResult[]>([]);

  if (!taskId) return null;

  const runCommand = async (cmd: string, isPreset = false) => {
    setRunning(true);
    try {
      const result = isPreset
        ? await executePreset(taskId, cmd)
        : await executeCode(taskId, cmd);
      setResults((prev) => [result, ...prev].slice(0, 20));
    } catch (err) {
      setResults((prev) => [
        { success: false, stdout: '', stderr: String(err), exit_code: -1, method: 'local' },
        ...prev,
      ]);
    }
    setRunning(false);
  };

  const handleCustom = () => {
    if (command.trim()) runCommand(command.trim());
  };

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
      <h3 className="text-white font-medium mb-3">⚡ 代码执行</h3>

      {/* 预设按钮 */}
      <div className="flex gap-2 mb-3 flex-wrap">
        {PRESET_BUTTONS.map((btn) => (
          <button
            key={btn.script}
            onClick={() => runCommand(btn.script, true)}
            disabled={running}
            className="px-3 py-1.5 bg-gray-800 hover:bg-gray-700 disabled:opacity-50 text-gray-300 rounded text-xs font-medium transition-colors flex items-center gap-1.5"
          >
            <span>{btn.icon}</span>
            {btn.label}
          </button>
        ))}
      </div>

      {/* 自定义命令 */}
      <div className="flex gap-2 mb-3">
        <input
          type="text"
          value={command}
          onChange={(e) => setCommand(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleCustom()}
          placeholder="python main.py 或 npm test..."
          className="flex-1 bg-gray-800 border border-gray-700 rounded-md px-3 py-1.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-accent-500"
        />
        <button
          onClick={handleCustom}
          disabled={running || !command.trim()}
          className="px-4 py-1.5 bg-accent-600 hover:bg-accent-500 disabled:bg-gray-700 text-white rounded-md text-sm font-medium transition-colors"
        >
          {running ? '⏳' : '▶'}
        </button>
      </div>

      {/* 执行结果 */}
      {results.length > 0 && (
        <div className="space-y-2 max-h-[300px] overflow-y-auto">
          {results.map((r, i) => (
            <div
              key={i}
              className={`rounded-lg p-3 text-xs font-mono ${
                r.success
                  ? 'bg-emerald-500/10 border border-emerald-500/30'
                  : 'bg-red-500/10 border border-red-500/30'
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <span className={r.success ? 'text-emerald-400' : 'text-red-400'}>
                  {r.success ? '✅' : '❌'} exit={r.exit_code} · {r.method}
                </span>
                <button
                  onClick={() => navigator.clipboard.writeText(r.stdout || r.stderr)}
                  className="text-gray-500 hover:text-white text-[10px]"
                >
                  复制
                </button>
              </div>
              <pre className="text-gray-300 whitespace-pre-wrap break-words max-h-[200px] overflow-y-auto">
                {r.stdout || r.stderr}
              </pre>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
