"""SeaTable WebSocket 异步客户端"""
import logging
from datetime import datetime
from typing import Any, TYPE_CHECKING

import socketio

from .constants import JOIN_ROOM, UPDATE_DTABLE, NEW_NOTIFICATION

if TYPE_CHECKING:
    from .seatable_api import SeaTableApiAsync

logger = logging.getLogger(__name__)
RECONNECT_DELAY_SECONDS = 3


class SocketIOAsync:
    """SeaTable WebSocket 异步客户端

    示例:
        async with SeaTableApiAsync(token, server_url) as api:
            async with SocketIOAsync(api) as socket:
                # 自动连接，使用完自动断开
                await socket.emit("my_event", {"data": "hello"})
    """

    def __init__(self, seatable_api: "SeaTableApiAsync") -> None:
        self.seatable_api = seatable_api
        self._sio = socketio.AsyncClient(request_timeout=seatable_api.timeout)
        self._handlers_registered = False

    def __str__(self) -> str:
        return f"<SeaTable SocketIO [{self.seatable_api.dtable_name}]>"

    def __repr__(self) -> str:
        return self.__str__()

    async def __aenter__(self) -> "SocketIOAsync":
        """进入异步上下文管理器，自动连接"""
        await self.connect()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """退出异步上下文管理器，自动断开"""
        await self.disconnect()

    @property
    def connected(self) -> bool:
        return self._sio.connected

    async def connect(self) -> None:
        """建立 WebSocket 连接"""
        if not self._handlers_registered:
            self._register_handlers()
            self._handlers_registered = True
        await self._connect_with_token_refresh()

    async def disconnect(self) -> None:
        """断开连接"""
        await self._sio.disconnect()

    async def emit(self, event: str, data: Any = None) -> None:
        """发送事件"""
        await self._sio.emit(event, data)

    async def wait(self) -> None:
        """等待连接关闭"""
        await self._sio.wait()

    def on(self, event: str, handler: Any) -> None:
        """注册自定义事件处理器"""
        self._sio.on(event, handler)

    def _register_handlers(self) -> None:
        """注册事件处理器"""
        self._sio.on("connect", self._on_connect)
        self._sio.on("disconnect", self._on_disconnect)
        self._sio.on("connect_error", self._on_connect_error)
        self._sio.on(UPDATE_DTABLE, self.on_update_dtable)
        self._sio.on(NEW_NOTIFICATION, self.on_new_notification)

    async def _connect_with_token_refresh(self) -> None:
        """刷新 token 并连接"""
        await self._ensure_token_fresh()
        url = f"{self.seatable_api.dtable_server_url}?dtable_uuid={self.seatable_api.dtable_uuid}"
        await self._sio.connect(url, socketio_path="/api-gateway/socket.io")

    async def _ensure_token_fresh(self) -> None:
        """确保 token 未过期"""
        if datetime.now() >= self.seatable_api.jwt_exp:
            await self.seatable_api.auth()
            logger.info("[ SeaTable SocketIO JWT token refreshed ]")

    async def _on_connect(self) -> None:
        """连接成功回调"""
        await self._ensure_token_fresh()
        await self._sio.emit(JOIN_ROOM, (self.seatable_api.dtable_uuid, self.seatable_api.jwt_token))
        logger.info("[ SeaTable SocketIO connection established ]")

    async def _on_disconnect(self) -> None:
        """断开连接回调"""
        logger.info("[ SeaTable SocketIO connection dropped ]")

    async def _on_connect_error(self, error_msg: Any) -> None:
        """连接错误回调"""
        logger.error("[ SeaTable SocketIO connection error ] %s", error_msg)

    async def on_update_dtable(self, data: Any, index: Any, *args: Any) -> None:
        """UPDATE_DTABLE 事件回调，可被子类重写"""
        logger.info("[ SeaTable SocketIO on UPDATE_DTABLE ]")
        logger.debug(data)

    async def on_new_notification(self, data: Any, index: Any, *args: Any) -> None:
        """NEW_NOTIFICATION 事件回调，可被子类重写"""
        logger.info("[ SeaTable SocketIO on NEW_NOTIFICATION ]")
        logger.debug(data)
