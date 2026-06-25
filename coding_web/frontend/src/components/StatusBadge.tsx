/* ═══════════════════════════════════════════════════════════════
   StatusBadge — 通用状态标签
   ═══════════════════════════════════════════════════════════════ */

type StatusColor = 'gray' | 'amber' | 'green' | 'red' | 'purple' | 'blue';

const colorMap: Record<string, StatusColor> = {
  idle: 'gray',
  busy: 'amber',
  waiting: 'purple',
  error: 'red',
  pending: 'gray',
  running: 'blue',
  in_progress: 'amber',
  completed: 'green',
  failed: 'red',
  cancelled: 'gray',
  blocked: 'purple',
};

const labelMap: Record<string, string> = {
  idle: '空闲',
  busy: '忙碌',
  waiting: '等待',
  error: '错误',
  pending: '待处理',
  running: '运行中',
  in_progress: '进行中',
  completed: '已完成',
  failed: '失败',
  cancelled: '已取消',
  blocked: '被阻止',
};

const bgMap: Record<StatusColor, string> = {
  gray: 'bg-gray-700 text-gray-300',
  amber: 'bg-amber-500/20 text-amber-400 border border-amber-500/30',
  green: 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30',
  red: 'bg-red-500/20 text-red-400 border border-red-500/30',
  purple: 'bg-purple-500/20 text-purple-400 border border-purple-500/30',
  blue: 'bg-blue-500/20 text-blue-400 border border-blue-500/30',
};

const dotMap: Record<StatusColor, string> = {
  gray: 'bg-gray-400',
  amber: 'bg-amber-400 animate-pulse',
  green: 'bg-emerald-400',
  red: 'bg-red-400',
  purple: 'bg-purple-400',
  blue: 'bg-blue-400',
};

interface Props {
  status: string;
  dot?: boolean;
}

export default function StatusBadge({ status, dot = true }: Props) {
  const color = colorMap[status] || 'gray';
  const label = labelMap[status] || status;

  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium ${bgMap[color]}`}>
      {dot && <span className={`w-2 h-2 rounded-full ${dotMap[color]}`} />}
      {label}
    </span>
  );
}
