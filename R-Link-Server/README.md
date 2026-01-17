# R-Link-Server

R-Link 插件化管理平台的后端服务。

## 功能特性

- **插件管理**: 发现、加载、启动、停止插件
- **进程管理**: 统一管理插件的子进程
- **状态监控**: 实时获取插件运行状态和资源使用
- **配置管理**: 动态修改插件配置
- **日志查看**: 获取插件运行日志
- **RESTful API**: 供前端调用的标准 API

## 项目结构

```
R-Link-Server/
├── main.py                 # 主入口
├── core/
│   ├── plugin_interface.py # 插件接口定义
│   ├── plugin_manager.py   # 插件管理器
│   └── process_pool.py     # 进程池管理
├── api/
│   ├── plugins.py          # 插件相关 API
│   └── system.py           # 系统相关 API
├── plugins/                # 插件目录
│   └── <plugin-name>/
│       ├── manifest.yaml   # 插件清单
│       ├── <binary>        # 二进制文件
│       └── config/         # 配置文件
├── config/                 # 配置目录
├── logs/                   # 日志目录
└── requirements.txt        # 依赖
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 启动服务

```bash
python main.py
```

服务将运行在 `http://localhost:8000`

### 3. API 文档

访问 `http://localhost:8000/docs` 查看 Swagger API 文档

## API 端点

### 插件管理

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/plugins` | GET | 获取所有插件 |
| `/api/plugins/{name}` | GET | 获取插件信息 |
| `/api/plugins/{name}/start` | POST | 启动插件 |
| `/api/plugins/{name}/stop` | POST | 停止插件 |
| `/api/plugins/{name}/restart` | POST | 重启插件 |
| `/api/plugins/{name}/status` | GET | 获取插件状态 |
| `/api/plugins/{name}/config` | GET | 获取插件配置 |
| `/api/plugins/{name}/config` | PUT | 设置插件配置 |
| `/api/plugins/{name}/logs` | GET | 获取插件日志 |
| `/api/plugins/{name}/health` | GET | 健康检查 |

### 系统信息

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/system/info` | GET | 系统信息 |
| `/api/system/resources` | GET | 资源使用 |
| `/api/system/processes` | GET | 进程列表 |
| `/api/system/uptime` | GET | 运行时间 |

## 插件开发

### 插件目录结构

```
plugins/my-plugin/
├── manifest.yaml       # 插件清单 (必需)
├── my-plugin.exe       # 二进制文件
└── icon.png            # 图标 (可选)
```

### 插件清单 (manifest.yaml)

```yaml
name: "my-plugin"           # 插件名称
version: "1.0.0"            # 版本号
description: "My Plugin"    # 描述
author: "Your Name"         # 作者
binary: "my-plugin.exe"     # 二进制文件名
category: "general"         # 分类
icon: "icon.png"            # 图标 (可选)

# 默认配置
default_config:
  port: 8080
  args: ["--port", "8080"]
```

参考 `docs/plugin-manifest-example.yaml` 获取更多示例。

## 子项目集成

将子项目编译为二进制后，按照以下步骤集成：

1. 在 `plugins/` 目录创建插件目录
2. 复制二进制文件到插件目录
3. 创建 `manifest.yaml` 插件清单
4. (可选) 添加配置文件和图标

### FRP 插件示例

```bash
# 1. 创建目录
mkdir -p plugins/frp/config

# 2. 编译并复制二进制
cp submodules/frp/bin/frpc.exe plugins/frp/

# 3. 创建清单
cp docs/plugin-manifest-example.yaml plugins/frp/manifest.yaml
# 编辑 manifest.yaml 配置插件信息

# 4. (可选) 添加配置文件
cp your-frpc-config.ini plugins/frp/config/frpc.ini
```

## 许可证

MIT License
