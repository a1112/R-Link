# R-Link 桌面应用构建指南

本文档说明如何使用 Tauri 构建 R-Link 桌面应用程序。

## 支持的平台

- Windows (x64, ARM64)
- macOS (Intel, Apple Silicon)
- Linux (x64, ARM64)

## 环境要求

### 通用要求

1. **Node.js** >= 18.0.0
   ```bash
   node --version
   ```

2. **Rust** >= 1.70
   ```bash
   cargo --version
   ```
   安装 Rust: https://rustup.rs/

### 平台特定要求

#### Windows
- **WebView2** (Windows 10/11 自带)
  - Windows 10 1803+ 已包含 WebView2
  - Windows 11 自带 WebView2

- **C++ 构建工具**
  - 安装 Visual Studio 2019/2022 或 Build Tools
  - 需要勾选 "C++ 构建工具"

#### macOS
- **Xcode** 命令行工具
  ```bash
  xcode-select --install
  ```

#### Linux
- **WebView2 相关依赖** (Ubuntu/Debian)
  ```bash
  sudo apt update
  sudo apt install libwebkit2gtk-4.1-dev \
    build-essential \
    curl \
    wget \
    file \
    libxdo-dev \
    libssl-dev \
    libayatana-appindicator3-dev \
    librsvg2-dev
  ```

## 开发模式

启动开发模式（带热重载）：

### Windows
```cmd
build-dev.bat
```

### macOS / Linux
```bash
chmod +x build-dev.sh
./build-dev.sh
```

或直接使用 npm:
```bash
npm run tauri:dev
```

## 生产构建

构建发布版本：

### Windows
```cmd
build.bat
```

### macOS / Linux
```bash
chmod +x build.sh
./build.sh
```

或直接使用 npm:
```bash
npm run tauri:build
```

## 输出目录

构建完成后，安装包位置：

- **Windows**: `src-tauri/target/release/bundle/msi/` 或 `/bundle/nsis/`
- **macOS**: `src-tauri/target/release/bundle/dmg/`
- **Linux**: `src-tauri/target/release/bundle/deb/` 或 `/bundle/appimage/`

## 图标

将应用图标放置在 `src-tauri/icons/` 目录：

- `icon.png` - 512x512 PNG 格式
- `icon.ico` - Windows 图标
- `icon.icns` - macOS 图标

使用 [favicon.io](https://favicon.io/) 或 [在线工具](https://convertico.com/) 转换图标格式。

## 窗口控制

应用使用自定义标题栏（`TitleBar` 组件），支持：

- 拖拽移动窗口
- 最小化
- 最大化/还原
- 关闭

双击标题栏可以切换最大化状态。

## 故障排除

### Rust 编译错误

确保 Rust 工具链是最新的：
```bash
rustup update
```

### 前端构建失败

清除缓存并重新安装：
```bash
rm -rf node_modules dist
npm install
npm run build
```

### Tauri CLI 不可用

全局安装 Tauri CLI：
```bash
cargo install tauri-cli --version "^2.0.0"
```

## 更多信息

- [Tauri 官方文档](https://tauri.app/)
- [Tauri v2 迁移指南](https://v2.tauri.app/start/migrate/from-tauri-1/)
