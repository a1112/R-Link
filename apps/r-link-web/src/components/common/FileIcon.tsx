/**
 * 文件图标组件
 * 根据文件类型显示对应的图标
 */

import React from "react";
import { Folder, Archive, Code, FileText, Image } from "lucide-react";

export type FileType = 'folder' | 'archive' | 'code' | 'document' | 'image' | 'default';

export interface FileIconProps {
  /** 文件类型 */
  type: FileType;
  /** 图标大小 */
  size?: number;
  /** 额外的类名 */
  className?: string;
}

const iconConfig: Record<FileType, { Icon: React.ElementType; className: string }> = {
  folder: { Icon: Folder, className: 'text-blue-400' },
  archive: { Icon: Archive, className: 'text-amber-400' },
  code: { Icon: Code, className: 'text-emerald-400' },
  document: { Icon: FileText, className: 'text-[var(--c-400)]' },
  image: { Icon: Image, className: 'text-purple-400' },
  default: { Icon: FileText, className: 'text-[var(--c-400)]' },
};

export const FileIcon: React.FC<FileIconProps> = ({
  type,
  size = 20,
  className = '',
}) => {
  const config = iconConfig[type] || iconConfig.default;
  const { Icon } = config;

  return <Icon size={size} className={`${config.className} ${className}`} />;
};

export default FileIcon;
