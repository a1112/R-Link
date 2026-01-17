# 串流功能演示

## Sunshine - 游戏串流服务器

### 快速开始

Windows 下载: https://github.com/LizardByte/Sunshine/releases

### 配置文件位置
- Windows: `%PROGRAMDATA%\Sunshine\config\sunshine.conf`
- Linux: `~/.config/sunshine/sunshine.conf`

### 最小配置示例
```ini
# 基础配置
sunshine_name = "R-Link Server"
webui_port = 47990

# 编码器配置 (NVIDIA/AMD/Intel)
encoder = nvenc

# 视频质量
min_bitrate = 5000
bitrate = 20000
```

## Moonlight - 游戏串流客户端

### 快速开始

下载: https://moonlight-stream.org/

### 连接配置
1. 输入 Sunshine 服务器 IP 地址
2. 输入 PIN 码 (首次配对时)
3. 选择要串流的应用

## WebRTC 集成

### 本项目中的 WebRTC 使用

可以参考 Sunshine 项目中的 WebRTC 实现：
`submodules/sunshine/` 目录下搜索 webrtc 相关代码

### 简单示例 (概念代码)
```cpp
// WebRTC 连接建立流程
// 1. 创建 PeerConnection
// 2. 创建 Offer/Answer
// 3. 交换 ICE Candidates
// 4. 建立连接
```

## 二进制文件使用

将编译好的二进制文件放置在 `../../binaries/streaming/` 目录：
- `sunshine.exe` (Windows) / `sunshine` (Linux)
- `moonlight.exe` 或对应平台的可执行文件
