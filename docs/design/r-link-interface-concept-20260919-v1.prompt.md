# R-Link 界面概念图

生成方式：内置 image_gen 工具。此图为概念设计，图中设备、指标、版本与时间均为示例，不代表运行状态。未修改应用界面代码。

图片：`r-link-interface-concept-20260919-v1.png`

## 完整提示词

Use case: ui-mockup
Asset type: R-Link desktop network management application, high-fidelity UI concept presentation.
Create a fresh, polished desktop interface concept image for the user's existing R-Link project. This is a proposed visual redesign, NOT a screenshot of running software. Show a coherent complete Chinese-language desktop product, with a large main app window and a smaller system-tray interaction detail to its right on the same restrained dark presentation canvas. Landscape aspect ratio, generous resolution, crisp legible Chinese typography.

Style: sophisticated native desktop utility, precise flat UI rendering, graphite and zinc surfaces consistent with R-Link's dark theme, subtle one-pixel borders, excellent text contrast, restrained emerald and blue status accents, compact professional controls, small clear line icons, 8px spacing rhythm, modest rounded corners. No neon, no glass blur, no sci-fi network globes, no oversized promotional typography, no stock photography, no perspective or laptop hardware. UI must be practical to implement with React and Tauri.

Main window composition: thin native title bar with R-Link brand, version, minimize/maximize/close. Narrow left sidebar with clear grouping: 概览, 仪表盘, 流量监控; 网络管理, 设备列表 (active), 设备连接视图, SSH 终端; 扩展, 插件中心; bottom 系统设置. Do not fill navigation with unavailable FRP, domains, files or download features. Main content top: breadcrumb 网络管理 / 设备列表; prominent heading 设备管理; short helper text 从服务端检测设备端口; primary button 添加设备, secondary 刷新. Below, a compact status strip reading 已登记 4, 上次检测可达 2, 端口不可达 1, 未检测 1, with calm distinct visual treatment. Main section is a professional device TABLE, not a grid of giant cards. Columns 设备名称, 地址, 检测结果, 检测时间, 操作. Four fictional example rows: 开发工作站 / 192.168.1.20:22 / 端口可达 / 14:32; 家庭 NAS / 192.168.1.30:22 / 端口可达 / 14:31; 测试服务器 / 192.168.1.40:22 / 端口不可达 / 14:30; 办公笔记本 / 192.168.1.50:22 / 未检测 / —. Each row has discreet 检测 and SSH actions, a contextual more menu. Status must describe last TCP check, never claim a persistent VPN connection or physical topology.
Beside or below the table, neatly integrate a selected-device detail area for 开发工作站 with host, SSH port 22, username dev, last-check timestamp, latency 8 ms and button SSH 连接. Include a small fine-print note TCP 可达不代表所有服务正常. At bottom of main content a compact, credible service-interface traffic chart labeled 服务端网络流量, WLAN, 接收 / 发送, Mbps, and a small service connection indicator 本地服务 · 127.0.0.1:8210. Subtle small footnote 示例数据, clearly separating conceptual sample values from live facts.

Right-hand concept detail panel: heading 系统托盘. A native-looking compact popup menu headed R-Link, with rows 显示主窗口, 仪表盘, 设备管理, 设备连接视图, SSH 终端, 插件管理, 系统设置; separator; checked 关闭窗口后驻留; 隐藏到托盘; separator; 退出 R-Link. Include a tiny desktop notification-area strip with an R-Link icon under the menu, making the tray anchor obvious. Under the detail show two short annotations: 关闭窗口，保留连接 and 单击图标，恢复窗口. This is a design board detail, not another invented in-app feature.

Text: all UI labels in simplified Chinese as specified, brand exactly "R-Link". Presentation corner caption exactly "R-Link / 界面概念", secondary caption "概念设计 · 示例数据". Carefully aligned columns, balanced density, beautiful crisp typography; make this feel like a mature engineering tool. Do not add fake account login, Supabase, cloud subscriptions, remote desktop video, unimplemented file transfers, or fictional success toasts. Show the two related views as one unified high-quality design concept image.
