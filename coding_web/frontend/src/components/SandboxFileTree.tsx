/* ═══════════════════════════════════════════════════════════════
   SandboxFileTree — 沙盒文件树
   ═══════════════════════════════════════════════════════════════ */

import { useState } from 'react';
import { useTaskStore } from '../store/taskStore';
import { getFileContent } from '../api/tasks';
import type { FileNode } from '../types';
import CodeViewer from './CodeViewer';

interface TreeNodeProps {
  node: FileNode;
  level: number;
}

function TreeNode({ node, level }: TreeNodeProps) {
  const [expanded, setExpanded] = useState(level < 2);
  const selectFile = useTaskStore((s) => s.selectFile);
  const selectedPath = useTaskStore((s) => s.selectedFilePath);

  const isSelected = selectedPath === node.path;
  const isDir = node.type === 'dir';

  const handleClick = async () => {
    if (isDir) {
      setExpanded(!expanded);
    } else {
      try {
        const data = await getFileContent(useTaskStore.getState().task?.id || '', node.path);
        selectFile(node.path, data.content);
      } catch {
        selectFile(node.path, '// 无法加载文件内容');
      }
    }
  };

  return (
    <div>
      <div
        onClick={handleClick}
        className={`flex items-center gap-1.5 py-1 px-1.5 cursor-pointer rounded text-xs transition-colors ${
          isSelected
            ? 'bg-accent-500/20 text-accent-400'
            : 'text-gray-400 hover:text-white hover:bg-gray-800/50'
        }`}
        style={{ paddingLeft: `${level * 16 + 4}px` }}
      >
        <span className="flex-shrink-0 w-4 text-center">
          {isDir ? (expanded ? '📂' : '📁') : '📄'}
        </span>
        <span className="truncate">{node.name}</span>
      </div>

      {isDir && expanded && node.children.length > 0 && (
        <div>
          {node.children.map((child) => (
            <TreeNode key={child.path} node={child} level={level + 1} />
          ))}
        </div>
      )}

      {isDir && expanded && node.children.length === 0 && (
        <div className="text-gray-600 text-xs py-1" style={{ paddingLeft: `${(level + 1) * 16 + 8}px` }}>
          (空)
        </div>
      )}
    </div>
  );
}

export default function SandboxFileTree() {
  const fileTree = useTaskStore((s) => s.fileTree);
  const taskId = useTaskStore((s) => s.task?.id);
  const selectedFileContent = useTaskStore((s) => s.selectedFileContent);
  const selectedFilePath = useTaskStore((s) => s.selectedFilePath);

  // 定期刷新文件树
  // 实际项目中可以在收到 sandbox_file_changed 事件时刷新

  if (!taskId) return null;

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
      <h3 className="text-white font-medium mb-3">📁 沙盒文件</h3>

      {fileTree.length === 0 ? (
        <div className="text-center text-gray-500 py-8">
          <p className="text-3xl mb-2">📁</p>
          <p className="text-sm">等待智能体创建文件...</p>
        </div>
      ) : (
        <div className="flex gap-4">
          {/* 文件树 */}
          <div className="w-56 flex-shrink-0 max-h-[300px] overflow-y-auto pr-1 border-r border-gray-800">
            {fileTree.map((node) => (
              <TreeNode key={node.path} node={node} level={0} />
            ))}
          </div>

          {/* 代码查看器 */}
          <div className="flex-1 min-w-0">
            <CodeViewer
              filePath={selectedFilePath}
              content={selectedFileContent}
            />
          </div>
        </div>
      )}
    </div>
  );
}
