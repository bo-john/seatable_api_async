"""SeaTable 账户 API 异步客户端"""
from __future__ import annotations

from json import JSONDecodeError, loads as json_loads
from typing import Any, Dict, Literal, Optional

import aiohttp

from .exception import AccountApiAsyncException
from .utils import path_get

__all__ = ["AccountApiAsync"]


class AccountApiAsync:
    """SeaTable 账户 API 异步客户端

    用于管理工作区、创建/复制 Base 等账户级操作。

    示例:
        async with AccountApiAsync(login_name, password, server_url) as api:
            workspaces = await api.list_workspaces()
    """

    def __init__(
            self,
            login_name: str,
            password: str,
            server_url: str,
            proxy: Optional[str] = None,
            timeout: int = 30
    ) -> None:
        self.login_name = login_name
        self.password = password
        self.server_url = server_url.strip().rstrip("/")
        self.proxy = proxy
        self.timeout = timeout
        self.token: Optional[str] = None
        self.username: Optional[str] = None
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self) -> AccountApiAsync:
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.timeout)
        )
        await self.auth()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self.session:
            await self.session.close()

    def __str__(self) -> str:
        return f"<SeaTable Account [{self.login_name}]>"

    def __repr__(self) -> str:
        return self.__str__()

    @property
    def _headers(self) -> Dict[str, str]:
        """获取带认证的请求头"""
        if self.token:
            return {"Authorization": f"Token {self.token}"}
        return {}

    async def req(
            self,
            method: Literal["GET", "POST"],
            action: str,
            json: Optional[Dict[str, Any]] = None,
            data: Optional[Dict[str, Any]] = None,
            params: Optional[Dict[str, Any]] = None,
            headers: Optional[Dict[str, str]] = None,
            res_path: Optional[str] = None,
    ) -> Any | None:
        """发送 HTTP 请求"""
        req_headers = {**self._headers, **(headers or {})}

        resp = await self.session.request(
            method=method,
            url=f"{self.server_url}/{action}",
            headers=req_headers,
            json=json,
            data=data,
            params=params,
            proxy=self.proxy,
            ssl=False,
        )

        status = resp.status
        text = await resp.text()

        if status == 429:
            raise AccountApiAsyncException("429 Too Many Requests")
        if status == 404:
            raise AccountApiAsyncException(f"404 Not Found: {action}")
        if status >= 400:
            raise AccountApiAsyncException(f"HTTP {status}: {text[:200]}")

        try:
            res = json_loads(text)
            return path_get(res, res_path) if res_path else res
        except JSONDecodeError as e:
            raise AccountApiAsyncException(f"Invalid JSON response: {e}")

    async def get(
            self,
            action: str,
            params: Optional[Dict[str, Any]] = None,
            headers: Optional[Dict[str, str]] = None,
            res_path: Optional[str] = None,
    ) -> Any:
        """GET 请求"""
        return await self.req("GET", action, params=params, headers=headers, res_path=res_path)

    async def post(
            self,
            action: str,
            json: Optional[Dict[str, Any]] = None,
            data: Optional[Dict[str, Any]] = None,
            params: Optional[Dict[str, Any]] = None,
            headers: Optional[Dict[str, str]] = None,
            res_path: Optional[str] = None,
    ) -> Any:
        """POST 请求"""
        return await self.req("POST", action, json=json, data=data, params=params, headers=headers, res_path=res_path)

    async def auth(self) -> None:
        """登录认证，获取 token"""
        self.token = await self.post(
            "api2/auth-token/",
            json={"username": self.login_name, "password": self.password},
            res_path="token"
        )

    async def load_account_info(self) -> None:
        """加载账户信息"""
        self.username = await self.get("api2/account/info/", res_path="email")

    async def list_workspaces(self) -> Dict[str, Any]:
        """获取工作区列表"""
        return await self.get("api/v2.1/workspaces/")

    async def _get_owner(self, workspace_id: Optional[int]) -> str:
        """获取 owner 标识"""
        if not workspace_id:
            if not self.username:
                await self.load_account_info()
            return self.username

        workspaces = await self.list_workspaces()
        for w in workspaces.get("workspace_list", []):
            if w.get("id") != workspace_id:
                continue
            if w.get("group_id"):
                return f"{w['group_id']}@seafile_group"
            if w.get("type") == "personal":
                if not self.username:
                    await self.load_account_info()
                return self.username

        raise AccountApiAsyncException(f"Invalid workspace_id: {workspace_id}")

    async def add_base(self, name: str, workspace_id: Optional[int] = None) -> Dict[str, Any]:
        """创建新 Base

        :param name: Base 名称
        :param workspace_id: 工作区 ID，不传则创建在个人工作区
        :return: 创建的 Base 信息
        """
        owner = await self._get_owner(workspace_id)
        return await self.post("api/v2.1/dtables/", data={"name": name, "owner": owner}, res_path="table")

    async def copy_base(
            self,
            src_workspace_id: int,
            base_name: str,
            dst_workspace_id: int
    ) -> Dict[str, Any]:
        """复制 Base

        :param src_workspace_id: 源工作区 ID
        :param base_name: Base 名称
        :param dst_workspace_id: 目标工作区 ID
        :return: 复制后的 Base 信息
        """
        return await self.post(
            "api/v2.1/dtable-copy/",
            data={
                "src_workspace_id": src_workspace_id,
                "name": base_name,
                "dst_workspace_id": dst_workspace_id
            },
            res_path="dtable"
        )

    async def get_temp_api_token(self, workspace_id: int, base_name: str) -> str:
        """获取临时 API Token

        :param workspace_id: 工作区 ID
        :param base_name: Base 名称
        :return: 临时 API Token
        """
        return await self.get(
            f"api/v2.1/workspace/{workspace_id}/dtable/{base_name}/temp-api-token/",
            res_path="api_token"
        )
