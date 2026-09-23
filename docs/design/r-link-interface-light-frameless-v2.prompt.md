# R-Link 浅色无边框概念图 v2

使用内置 image_gen 工具生成。图片为设计概念，设备与指标为示例，尚未修改实际界面。

图片：`r-link-interface-light-frameless-v2.png`

## 完整提示词

Use case: ui-mockup
Asset type: revised R-Link desktop application interface concept, LIGHT THEME.
Primary request: The previous concept felt ugly, rigid and boxy. Completely rethink it as a beautiful, fluid, frameless light desktop app. NO separate title bar. NO independent window header strip. NO browser chrome. NO thick outer frame. Make the UI feel spacious, contemporary, carefully art-directed and buildable, while remaining a useful device network management application.

Composition: one large front-facing desktop application mockup filling almost the entire landscape 16:10 image. A continuous warm-white app surface, subtly rounded outer corners with a barely visible soft shadow against a very pale neutral backdrop. The image should be devoted to the actual app, NOT a presentation board with detached annotations or a separate tray-menu column. Integrate tiny minimize, maximize and close icons unobtrusively into the upper right of the main content surface at the same height as the page breadcrumb/search. They must not sit in a dedicated title bar. Left navigation merges seamlessly with the overall window; brand R-Link lives at top of the sidebar, not in a top bar. There is no horizontal titlebar divider extending across the window.

Visual style: refined light software, warm white and mist-gray surfaces, high-quality dark graphite Chinese typography, restrained fresh blue primary actions and mint-green operational states. Generous whitespace, excellent typographic hierarchy, rhythmic spacing, small clean line icons, pill-shaped subtle status tags. Not a wall of outlined rectangles. Avoid spreadsheet-like grid lines, repetitive large statistic cards, hard gradients, frosted-glass overload, neon, corporate dashboard templates or skeuomorphic chrome. Use nuanced surface grouping, expressive yet disciplined placement, soft rounded corners, fine sparing separators. The layout should feel relaxed and alive rather than rigid, but not cartoonish.

Information architecture and layout:
- Compact sidebar about 180px wide with brand mark and "R-Link" at top. Navigation in simplified Chinese: 概览, 设备, 网络活动, SSH 终端, 插件. Active item "设备" has a delicate tinted capsule. At bottom, a compact connected-service indicator and 系统设置, with ample breathing room. No account avatar, login or cloud-account UI.
- Main workspace top has a small breadcrumb "工作空间 / 设备" and a low-profile search field "搜索设备", integrated window controls at far right. Do NOT create a standalone title strip.
- Below is an elegant heading "我的设备", short supporting text "设备状态，一目了然", with a blue pill button "+ 添加设备". A small unobtrusive line summarizes "4 台设备 · 2 台端口可达" instead of giant KPI boxes.
- Filter tabs "全部设备" active, "最近检测", "未检测", with restrained visual treatment.
- Device browsing area uses an airy editorial LIST with rows gently separated by spacing, NOT a dense outlined table. Four realistic example devices with small illustrated-but-minimal device silhouettes or clean line icons: 开发工作站, 家庭 NAS, 测试服务器, 办公笔记本. Each row shows IP address and subtle metadata, last TCP check result and timestamp. The selected 开发工作站 row has a pale blue background with rounded corners, green pill "端口可达", "8 ms", and a tiny SSH shortcut. 家庭 NAS green "端口可达"; 测试服务器 a restrained rose "端口不可达"; 办公笔记本 gray "未检测". Use example private addresses 192.168.1.20, .30, .40, .50. No dense column header bar. Icons and baseline alignment keep the list easy to scan.
- To the right, an integrated selected-device inspector occupying about a third of content width, with a soft pale-blue or neutral surface, not a heavy outlined card: subtle workstation illustration, heading "开发工作站", small monospace address 192.168.1.20, neat key-value pairs SSH 端口 22, 用户名 dev, 最近检测 14:32, 延迟 8 ms; prominent "SSH 连接" button, lighter "检测端口" secondary action. Small note "检测结果仅代表指定 TCP 端口".
- Beneath the main device area, a low, wide network activity section with much whitespace and a delicate blue/mint line chart, "网络活动", WLAN, recent time labels, small receive/send values. Avoid large dark graph boxes. The chart is part of the flow rather than another rigid KPI tile.
- Include one SMALL native-feeling tray popover floating over the lower-right app region as an interaction preview, integrated into the concept instead of a huge separate panel. Light surface, subtle shadow, R-Link name, short menu: 显示主窗口, 设备管理, SSH 终端, 设置, checked 关闭后驻留, 退出. Keep it small enough not to obscure the main device list or important inspector controls. Optional faint thin tray anchor icon below it.
- Small unobtrusive bottom caption "界面概念 · 示例数据".

Text: simplified Chinese, exceptionally clear and well spaced; exact brand "R-Link". No giant marketing headline. No version number in a window header. No fake running VPN, no FRP/file-transfer features, no Supabase, no avatars. This is explicitly a concept image with sample device data. The defining change must be obvious at first glance: LIGHT, SPACIOUS, FRAMELESS, NO SEPARATE TITLE BAR.
