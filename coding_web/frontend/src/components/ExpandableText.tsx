/* ═══════════════════════════════════════════════════════════════
   ExpandableText — 点击截断文本弹出完整内容小窗
   ═══════════════════════════════════════════════════════════════ */

import { useState } from 'react';

interface Props {
  text: string;
  maxLines?: number;
  maxChars?: number;
  className?: string;
  as?: 'div' | 'span' | 'p' | 'pre';
  label?: string;
}

export default function ExpandableText({
  text,
  maxLines = 2,
  maxChars,
  className = '',
  as: Tag = 'div',
  label,
}: Props) {
  const [open, setOpen] = useState(false);

  if (!text) return <Tag className={className}>{text}</Tag>;

  const isLong =
    (maxChars && text.length > maxChars) ||
    text.split('\n').length > maxLines ||
    text.length > 200;

  const truncated = maxChars ? text.slice(0, maxChars) + '...' : text;

  return (
    <>
      <Tag
        onClick={() => isLong && setOpen(true)}
        className={`${className} ${isLong ? 'cursor-pointer hover:opacity-80 transition-opacity' : ''}`}
        title={isLong ? '点击查看完整内容' : undefined}
        style={maxLines > 0 ? {
          display: '-webkit-box',
          WebkitLineClamp: maxLines,
          WebkitBoxOrient: 'vertical',
          overflow: 'hidden',
        } : undefined}
      >
        {maxChars ? truncated : text}
      </Tag>

      {/* 弹出小窗 */}
      {open && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center" onClick={() => setOpen(false)}>
          <div className="absolute inset-0 bg-black/60" />
          <div
            className="relative bg-gray-900 border border-gray-600 rounded-xl shadow-2xl max-w-2xl w-[90vw] max-h-[80vh] flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            {/* 标题栏 */}
            <div className="flex items-center justify-between px-4 py-2.5 border-b border-gray-700 flex-shrink-0">
              <span className="text-gray-400 text-sm font-medium">
                {label || '完整内容'}
              </span>
              <button
                onClick={() => setOpen(false)}
                className="text-gray-500 hover:text-white text-lg leading-none p-1 rounded hover:bg-gray-800 transition-colors"
              >
                ✕
              </button>
            </div>

            {/* 内容 */}
            <div className="p-4 overflow-y-auto flex-1">
              <pre className="text-gray-200 text-sm whitespace-pre-wrap font-mono leading-relaxed break-words">
                {text}
              </pre>
            </div>

            {/* 底部 */}
            <div className="px-4 py-2 border-t border-gray-700 flex items-center justify-between flex-shrink-0">
              <span className="text-gray-600 text-xs">{text.length.toLocaleString()} 字符</span>
              <button
                onClick={() => { navigator.clipboard.writeText(text); }}
                className="text-gray-400 hover:text-white text-xs transition-colors"
              >
                📋 复制
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
