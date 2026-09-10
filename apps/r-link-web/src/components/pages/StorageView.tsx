/**
 * 文件存储管理页面组件
 */

import React, { useState } from "react";
import { ArrowUp, HardDrive, MoreHorizontal, Plus } from "lucide-react";
import { toast } from "sonner";
import { FileIcon } from "../common";
import { useBackNavigation } from "@/hooks";

// 文件系统模拟数据
const fileSystem: Record<string, Array<{ id: number; name: string; size: string; date: string; type: string }>> = {
  '': [
    { id: 1, name: "项目文档", size: "-", date: "10月 24", type: "folder" },
    { id: 2, name: "设计资源", size: "-", date: "10月 23", type: "folder" },
    { id: 3, name: "根目录文件.pdf", size: "4.2 MB", date: "10月 22", type: "document" },
  ],
  '项目文档': [
    { id: 11, name: "需求说明书.docx", size: "1.2 MB", date: "10月 25", type: "document" },
    { id: 12, name: "API接口文档.md", size: "45 KB", date: "10月 25", type: "code" },
  ],
  '设计资源': [
    { id: 21, name: "Logo.svg", size: "12 KB", date: "10月 23", type: "image" },
    { id: 22, name: "Banner.png", size: "2.4 MB", date: "10月 23", type: "image" },
  ],
};

export const StorageView: React.FC = () => {
  const [currentPath, setCurrentPath] = useState<string[]>([]);

  // 获取当前路径的文件
  const getCurrentPathKey = () => {
    return currentPath.length > 0 ? currentPath[currentPath.length - 1] : '';
  };

  const currentFiles = fileSystem[getCurrentPathKey()] || [];

  const handleNavigate = (folderName: string) => {
    setCurrentPath([...currentPath, folderName]);
  };

  const handleBack = () => {
    if (currentPath.length > 0) {
      setCurrentPath(currentPath.slice(0, -1));
      toast.info("已返回上一级");
    } else {
      toast.warning("已经是根目录");
    }
  };

  useBackNavigation(handleBack, true);

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-500">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-[var(--c-100)] tracking-tight">文件管理</h2>
          <p className="text-[var(--c-500)] text-sm">WebDAV 云存储文件浏览器</p>
        </div>
        <div className="flex gap-2">
          <button className="bg-[var(--c-800)] hover:bg-[var(--c-700)] text-[var(--c-200)] px-3 py-2 rounded-lg text-sm font-medium flex items-center gap-2 transition-colors">
            <ArrowUp size={16} /> 上传
          </button>
          <button className="bg-[var(--c-100)] hover:bg-[var(--c-white)] text-[var(--c-900)] px-3 py-2 rounded-lg text-sm font-medium flex items-center gap-2 transition-colors">
            <Plus size={16} /> 新建文件夹
          </button>
        </div>
      </div>

      <div className="bg-[var(--c-900)] border border-[var(--c-800)] rounded-xl overflow-hidden flex flex-col h-[600px]">
        {/* 面包屑导航 */}
        <div className="p-4 border-b border-[var(--c-800)] flex items-center gap-2 text-sm">
          <button
            onClick={handleBack}
            disabled={currentPath.length === 0}
            className="p-1.5 rounded-md hover:bg-[var(--c-800)] text-[var(--c-400)] disabled:opacity-30 disabled:hover:bg-transparent cursor-pointer transition-colors mr-2"
          >
            <ArrowUp className="-rotate-90" size={16} />
          </button>
          <span
            className={`p-1.5 rounded-md hover:bg-[var(--c-800)] text-[var(--c-400)] cursor-pointer transition-colors ${currentPath.length === 0 ? 'text-[var(--c-100)]' : ''}`}
            onClick={() => setCurrentPath([])}
          >
            <HardDrive size={16} />
          </span>
          <span className="text-[var(--c-600)]">/</span>
          <span
            className={`font-medium cursor-pointer transition-colors ${currentPath.length === 0 ? 'text-[var(--c-200)]' : 'text-[var(--c-500)] hover:text-[var(--c-200)]'}`}
            onClick={() => setCurrentPath([])}
          >
            根目录
          </span>
          {currentPath.map((folder, index) => (
            <React.Fragment key={folder}>
              <span className="text-[var(--c-600)]">/</span>
              <span
                className={`font-medium cursor-pointer transition-colors ${index === currentPath.length - 1 ? 'text-[var(--c-200)]' : 'text-[var(--c-500)] hover:text-[var(--c-200)]'}`}
                onClick={() => setCurrentPath(currentPath.slice(0, index + 1))}
              >
                {folder}
              </span>
            </React.Fragment>
          ))}
        </div>

        {/* 文件列表 */}
        <div className="flex-1 overflow-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-[var(--c-800)] text-[var(--c-500)]">
                <th className="p-4 font-medium w-10"></th>
                <th className="p-4 font-medium">文件名</th>
                <th className="p-4 font-medium">大小</th>
                <th className="p-4 font-medium">修改时间</th>
                <th className="p-4 font-medium text-right"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--c-800-50)]">
              {currentFiles.map((file) => (
                <tr
                  key={file.id}
                  onClick={() => file.type === 'folder' && handleNavigate(file.name)}
                  className="group hover:bg-[var(--c-800-30)] transition-colors cursor-pointer"
                >
                  <td className="p-4 pl-6">
                    <FileIcon type={file.type as any} />
                  </td>
                  <td className="p-4 font-medium text-[var(--c-200)] group-hover:text-blue-400 transition-colors">{file.name}</td>
                  <td className="p-4 text-[var(--c-500)] font-mono text-xs">{file.size}</td>
                  <td className="p-4 text-[var(--c-500)] text-xs">{file.date}</td>
                  <td className="p-4 text-right pr-6">
                    <button className="opacity-0 group-hover:opacity-100 p-2 text-[var(--c-400)] hover:text-[var(--c-100)] transition-all">
                      <MoreHorizontal size={16} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* 底部状态栏 */}
        <div className="p-4 border-t border-[var(--c-800)] bg-[var(--c-900-50)] flex justify-between items-center text-xs text-[var(--c-500)]">
          <span>已选择 {currentFiles.length} 项</span>
          <span>已用 2.4 GB / 总共 1 TB</span>
        </div>
      </div>
    </div>
  );
};

export default StorageView;
