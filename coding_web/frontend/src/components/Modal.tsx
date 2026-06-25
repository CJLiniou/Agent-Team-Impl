/* ═══════════════════════════════════════════════════════════════
   Modal — 通用弹窗组件，支持全屏/大屏两种尺寸
   ═══════════════════════════════════════════════════════════════ */

import { useEffect, useCallback } from 'react';

interface Props {
  open: boolean;
  onClose: () => void;
  title?: string;
  size?: 'large' | 'full';
  children: React.ReactNode;
}

export default function Modal({ open, onClose, title, size = 'large', children }: Props) {
  // ESC 关闭
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    },
    [onClose]
  );

  useEffect(() => {
    if (open) {
      document.addEventListener('keydown', handleKeyDown);
      document.body.style.overflow = 'hidden';
    }
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = '';
    };
  }, [open, handleKeyDown]);

  if (!open) return null;

  const sizeClass =
    size === 'full'
      ? 'w-[95vw] h-[95vh]'
      : 'w-[90vw] max-w-[1400px] max-h-[90vh]';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* 遮罩 */}
      <div
        className="absolute inset-0 bg-black/70 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* 弹窗主体 */}
      <div
        className={`relative ${sizeClass} bg-gray-950 border border-gray-700 rounded-xl shadow-2xl flex flex-col overflow-hidden`}
      >
        {/* 标题栏 */}
        {title && (
          <div className="flex items-center justify-between px-5 py-3 border-b border-gray-800 flex-shrink-0">
            <h2 className="text-white font-semibold text-lg truncate">{title}</h2>
            <button
              onClick={onClose}
              className="text-gray-500 hover:text-white text-xl leading-none p-1 rounded-lg hover:bg-gray-800 transition-colors"
              title="关闭 (ESC)"
            >
              ✕
            </button>
          </div>
        )}

        {/* 关闭按钮（无标题时） */}
        {!title && (
          <button
            onClick={onClose}
            className="absolute top-3 right-3 z-10 text-gray-500 hover:text-white text-xl leading-none p-2 rounded-lg hover:bg-gray-800 transition-colors bg-gray-900/80"
            title="关闭 (ESC)"
          >
            ✕
          </button>
        )}

        {/* 内容 */}
        <div className="flex-1 overflow-y-auto">{children}</div>
      </div>
    </div>
  );
}
