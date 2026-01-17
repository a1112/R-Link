# 存储与 WebDav 演示

## Rclone - 云存储同步工具

### 什么是 Rclone

Rclone 是一个命令行同步工具，支持 70+ 种云存储服务，包括 WebDav。

### 快速开始

```bash
# 配置远程存储
rclone config

# 列出所有远程配置
rclone listremotes

# 列出远程文件
rclone ls remote:name

# 同步文件
rclone sync source remote:destination

# 挂载为文件系统 (需要 FUSE)
rclone mount remote:/path /mnt/path
```

### WebDav 配置示例

```bash
# 添加 WebDav 远程
rclone config
# 选择 "webdav"
# 输入 URL、用户名、密码

# 列出 WebDav 文件
rclone ls webdav:path/to/files

# 上传文件
rclone copy localfile webdav:remotepath/
```

### 常见云存储支持

- Google Drive
- Dropbox
- OneDrive
- Amazon S3
- WebDav (坚果云、Nextcloud 等)
- FTP/SFTP
- 本地文件系统

## 二进制文件使用

将编译好的二进制文件放置在 `../../binaries/storage/` 目录：
- `rclone.exe` (Windows) / `rclone` (Linux/macOS)

## 配置文件位置

- Windows: `%LOCALAPPDATA%\rclone\rclone.conf`
- Linux: `~/.config/rclone/rclone.conf`
- macOS: `~/.config/rclone/rclone.conf`

## 简单 WebDav 服务器示例

可以使用内置 WebDav 服务器搭建简单的文件共享：

```bash
# 使用 Python 快速搭建 WebDav 测试服务器
pip3 EXISTS wsgidav
wsgidav --port=8080 --root=/path/to/share
```
