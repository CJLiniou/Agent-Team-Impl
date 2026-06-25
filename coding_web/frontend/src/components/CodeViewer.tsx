/* ═══════════════════════════════════════════════════════════════
   CodeViewer — 代码内容查看器
   ═══════════════════════════════════════════════════════════════ */

interface Props {
  filePath: string | null;
  content: string;
}

export default function CodeViewer({ filePath, content }: Props) {
  if (!filePath) {
    return (
      <div className="text-center text-gray-500 py-12">
        <p className="text-3xl mb-2">📄</p>
        <p className="text-sm">选择一个文件查看内容</p>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center justify-between mb-2">
        <span className="text-accent-400 text-xs font-mono">{filePath}</span>
        <button
          onClick={() => {
            navigator.clipboard.writeText(content);
          }}
          className="text-gray-500 hover:text-white text-xs transition-colors"
          title="复制内容"
        >
          📋 复制
        </button>
      </div>
      <div className="bg-gray-950 border border-gray-800 rounded-lg overflow-auto max-h-[260px]">
        <pre className="p-4 text-gray-300 text-xs leading-relaxed font-mono whitespace-pre-wrap break-words">
          {content || '(空文件)'}
        </pre>
      </div>
    </div>
  );
}
