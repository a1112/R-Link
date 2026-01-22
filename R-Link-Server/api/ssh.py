"""
SSH WebSocket API
提供 SSH 终端的 WebSocket 连接
"""
import asyncio
import json
import logging
import uuid
from typing import Dict, Optional, Set, TYPE_CHECKING
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from asyncssh import SSHClientConnection, SSHReader, SSHWriter, SSHClientSession

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ssh", tags=["SSH"])

# 存储活跃的 SSH 连接
# connection_id -> SSHConnection
active_connections: Dict[str, "SSHConnection"] = {}


class SSHConnectRequest(BaseModel):
    """SSH 连接请求"""
    host: str = Field(..., description="SSH 服务器地址")
    port: int = Field(22, description="SSH 端口")
    username: str = Field(..., description="用户名")
    password: Optional[str] = Field(None, description="密码")
    private_key: Optional[str] = Field(None, description="私钥")
    passphrase: Optional[str] = Field(None, description="私钥密码")
    columns: int = Field(80, description="终端列数")
    rows: int = Field(24, description="终端行数")


class SSHConnection:
    """SSH 连接包装类"""

    def __init__(
        self,
        connection_id: str,
        websocket: WebSocket,
        host: str,
        port: int,
        username: str,
    ):
        self.connection_id = connection_id
        self.websocket = websocket
        self.host = host
        self.port = port
        self.username = username
        self.client: Optional["SSHClientConnection"] = None
        self.stdin: Optional["SSHWriter"] = None
        self.stdout: Optional["SSHReader"] = None
        self.stderr: Optional["SSHReader"] = None
        self.session: Optional["SSHClientSession"] = None
        self.read_task: Optional[asyncio.Task] = None
        self.closed = False

    async def connect(
        self,
        password: Optional[str] = None,
        private_key: Optional[str] = None,
        passphrase: Optional[str] = None,
        columns: int = 80,
        rows: int = 24,
    ) -> bool:
        """建立 SSH 连接"""
        try:
            import asyncssh

            # 准备连接参数
            connect_kwargs = {
                "host": self.host,
                "port": self.port,
                "username": self.username,
                "known_hosts": None,  # 禁用主机密钥检查（生产环境应该启用）
            }

            # 添加认证方式
            if private_key:
                # 使用私钥认证
                connect_kwargs["client_keys"] = [
                    asyncssh.import_private_key(
                        private_key,
                        passphrase=passphrase
                    )
                ]
            elif password:
                # 使用密码认证
                connect_kwargs["password"] = password
            else:
                # 尝试使用默认 SSH agent 或本地密钥
                pass

            # 建立连接
            self.client = await asyncio.wait_for(
                asyncssh.connect(**connect_kwargs),
                timeout=30
            )

            # 打开 PTY 会话
            self.session = await self.client.create_session(
                term_type="xterm-256color",
                columns=columns,
                rows=rows,
            )

            self.stdin = self.session.stdin
            self.stdout = self.session.stdout
            self.stderr = self.session.stderr

            # 启动读取任务
            self.read_task = asyncio.create_task(self._read_stdout())

            # 发送连接成功消息
            await self.send_json({
                "type": "connected",
                "host": self.host,
                "port": self.port,
                "username": self.username,
            })

            logger.info(f"SSH connection established: {self.connection_id}")
            return True

        except asyncio.TimeoutError:
            await self.send_json({"type": "error", "message": "连接超时"})
            return False
        except asyncssh.PermissionDenied:
            await self.send_json({"type": "error", "message": "认证失败：用户名或密码错误"})
            return False
        except asyncssh.HostKeyNotVerifiable:
            await self.send_json({"type": "error", "message": "主机密钥验证失败"})
            return False
        except OSError as e:
            await self.send_json({"type": "error", "message": f"网络错误: {str(e)}"})
            return False
        except Exception as e:
            logger.error(f"SSH connection error: {e}", exc_info=True)
            await self.send_json({"type": "error", "message": f"连接失败: {str(e)}"})
            return False

    async def _read_stdout(self):
        """读取标准输出"""
        try:
            while not self.closed and self.stdout:
                data = await self.stdout.read(1024)
                if not data:
                    break
                await self.send_json({
                    "type": "data",
                    "data": data,
                })
        except Exception as e:
            logger.error(f"Error reading stdout: {e}")
        finally:
            if not self.closed:
                await self.close()

    async def send_json(self, data: dict):
        """发送 JSON 消息"""
        try:
            await self.websocket.send_json(data)
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            await self.close()

    async def write(self, data: str):
        """写入数据到终端"""
        if self.stdin and not self.stdin.is_closing():
            try:
                self.stdin.write(data)
                await self.stdin.drain()
            except Exception as e:
                logger.error(f"Error writing to stdin: {e}")
                await self.close()

    async def resize(self, columns: int, rows: int):
        """调整终端大小"""
        if self.session and hasattr(self.session, "change_terminal_size"):
            try:
                self.session.change_terminal_size(columns, rows)
            except Exception as e:
                logger.error(f"Error resizing terminal: {e}")

    async def close(self):
        """关闭连接"""
        if self.closed:
            return
        self.closed = True

        if self.read_task:
            self.read_task.cancel()
            try:
                await self.read_task
            except asyncio.CancelledError:
                pass

        if self.stdin:
            self.stdin.close()
            await asyncio.sleep(0.1)

        if self.session:
            self.session.exit()
            await asyncio.sleep(0.1)

        if self.client:
            self.client.close()
            await self.client.wait_closed()

        active_connections.pop(self.connection_id, None)
        logger.info(f"SSH connection closed: {self.connection_id}")

    @property
    def is_connected(self) -> bool:
        """是否已连接"""
        return self.client is not None and not self.closed


@router.get("/connections")
async def list_connections():
    """列出所有活动连接"""
    from builtin.webssh_plugin import get_connection_manager

    manager = get_connection_manager()
    return {
        "connections": manager.list_connections(),
        "count": len(active_connections),
    }


@router.post("/connections/{connection_id}/close")
async def close_connection(connection_id: str):
    """关闭指定连接"""
    from builtin.webssh_plugin import SSHConnectionStatus

    conn = active_connections.get(connection_id)
    if conn:
        await conn.close()
        return {"success": True, "message": "Connection closed"}
    return {"error": "Connection not found"}


@router.websocket("/connect")
async def ssh_websocket(
    websocket: WebSocket,
    host: str = Query(..., description="SSH 服务器地址"),
    port: int = Query(22, description="SSH 端口"),
    username: str = Query(..., description="用户名"),
):
    """
    SSH WebSocket 端点

    连接参数通过 query string 传递：
    - host: SSH 服务器地址
    - port: SSH 端口 (默认 22)
    - username: 用户名

    消息格式（客户端 -> 服务器）：
    {
        "type": "auth",        // 认证
        "password": "...",     // 密码
        "private_key": "...",  // 私钥（可选）
        "passphrase": "..."    // 私钥密码（可选）
    }
    {
        "type": "data",        // 发送数据到终端
        "data": "..."
    }
    {
        "type": "resize",      // 调整终端大小
        "columns": 80,
        "rows": 24
    }
    {
        "type": "close"        // 关闭连接
    }

    消息格式（服务器 -> 客户端）：
    {
        "type": "connected",   // 连接成功
        "host": "...",
        "port": ...,
        "username": "..."
    }
    {
        "type": "data",        // 终端输出数据
        "data": "..."
    }
    {
        "type": "error",       // 错误消息
        "message": "..."
    }
    {
        "type": "closed"       // 连接关闭
    }
    """
    # 生成连接 ID
    connection_id = str(uuid.uuid4())

    # 更新连接管理器
    from builtin.webssh_plugin import get_connection_manager

    manager = get_connection_manager()
    ssh_conn = manager.create_connection(
        connection_id=connection_id,
        host=host,
        port=port,
        username=username,
    )

    await websocket.accept()

    # 创建 SSH 连接包装
    conn = SSHConnection(
        connection_id=connection_id,
        websocket=websocket,
        host=host,
        port=port,
        username=username,
    )
    active_connections[connection_id] = conn

    try:
        # 等待认证消息
        auth_message = await websocket.receive_json()

        if auth_message.get("type") != "auth":
            await conn.send_json({
                "type": "error",
                "message": "First message must be auth type"
            })
            await conn.close()
            return

        # 建立连接
        password = auth_message.get("password")
        private_key = auth_message.get("private_key")
        passphrase = auth_message.get("passphrase")
        columns = auth_message.get("columns", 80)
        rows = auth_message.get("rows", 24)

        success = await conn.connect(
            password=password,
            private_key=private_key,
            passphrase=passphrase,
            columns=columns,
            rows=rows,
        )

        if not success:
            await conn.close()
            return

        # 更新连接状态
        manager.update_connection_status(connection_id, SSHConnectionStatus.CONNECTED)

        # 处理后续消息
        while True:
            try:
                message = await asyncio.wait_for(
                    websocket.receive_json(),
                    timeout=300  # 5 分钟超时
                )

                msg_type = message.get("type")

                if msg_type == "data":
                    # 发送数据到终端
                    data = message.get("data", "")
                    await conn.write(data)

                elif msg_type == "resize":
                    # 调整终端大小
                    columns = message.get("columns", 80)
                    rows = message.get("rows", 24)
                    await conn.resize(columns, rows)

                elif msg_type == "close":
                    # 关闭连接
                    break

            except asyncio.TimeoutError:
                # 超时，发送心跳
                await conn.send_json({"type": "ping"})

            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected: {connection_id}")
                break

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {connection_id}")

    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)

    finally:
        # 清理连接
        from builtin.webssh_plugin import SSHConnectionStatus
        manager.update_connection_status(connection_id, SSHConnectionStatus.DISCONNECTED)
        manager.close_connection(connection_id)
        await conn.close()
