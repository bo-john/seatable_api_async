"""SeaTable Base API 异步客户端"""
from __future__ import annotations

from datetime import datetime, timedelta
from json import JSONDecodeError, loads as json_loads
from typing import Any, Dict, List, Literal, Optional, Tuple
from urllib import parse
from uuid import UUID

import aiofiles
import aiohttp

from .constants import (
    ROW_FILTER_KEYS,
    ColumnTypes,
    RENAME_COLUMN,
    RESIZE_COLUMN,
    FREEZE_COLUMN,
    MOVE_COLUMN,
    MODIFY_COLUMN_TYPE,
)
from .exception import BaseUnauthError, SeatableApiException
from .utils import parse_server_url, parse_headers, like_table_id, convert_db_rows, path_get

__all__ = ["SeaTableApiAsync"]


class SeaTableApiAsync:
    """SeaTable Base API 异步客户端

    示例:
        async with SeaTableApiAsync(token, server_url) as api:
            rows = await api.list_rows("Table1")
    """

    def __init__(
            self,
            token: str,
            server_url: str,
            use_api_gateway: bool = False,
            proxy: Optional[str] = None,
            timeout: int = 30
    ) -> None:
        self.token = token
        self.server_url = server_url.strip().rstrip("/")
        self.use_api_gateway = use_api_gateway
        self.proxy = proxy
        self.timeout = timeout

        # 认证后填充
        self.dtable_server_url: Optional[str] = None
        self.dtable_db_url: Optional[str] = None
        self.jwt_token: Optional[str] = None
        self.jwt_exp: Optional[datetime] = None
        self.headers: Optional[Dict[str, str]] = None
        self.workspace_id: Optional[int] = None
        self.dtable_uuid: Optional[str] = None
        self.dtable_name: Optional[str] = None
        self.is_authed = False
        self.session: Optional[aiohttp.ClientSession] = None

    def __str__(self) -> str:
        return f"<SeaTable Base [{self.dtable_name}]>"

    def __repr__(self) -> str:
        return self.__str__()

    async def __aenter__(self) -> SeaTableApiAsync:
        self.session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(limit=100, limit_per_host=30),
            timeout=aiohttp.ClientTimeout(total=self.timeout),
        )
        await self.auth()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self.session:
            await self.session.close()

    def _table_params(self, table_name: str, **extra: Any) -> Dict[str, Any]:
        """构建表参数，自动处理 table_id"""
        params = {"table_name": table_name, **extra}
        if like_table_id(table_name):
            params["table_id"] = table_name
        return params

    def _link_params(self, table_name: str, other_table_name: str, **extra: Any) -> Dict[str, Any]:
        """构建链接参数"""
        params = {"table_name": table_name, "other_table_name": other_table_name, **extra}
        if like_table_id(table_name):
            params["table_id"] = table_name
        if like_table_id(other_table_name):
            params["other_table_id"] = other_table_name
        return params

    # ========== HTTP 请求 ==========

    async def req(
            self,
            method: Literal["GET", "POST", "PUT", "DELETE"],
            url: str,
            json: Optional[Dict[str, Any]] = None,
            data: Optional[Dict[str, Any]] = None,
            file: Optional[Tuple[str, bytes]] = None,
            params: Optional[Dict[str, Any]] = None,
            headers: Optional[Dict[str, str]] = None,
            proxy: Optional[str] = None,
            token_type: Optional[Literal["JWT", "TOKEN", "None"]] = None,
            response_type: Optional[Literal["json", "text", "bytes"]] = None,
            res_path: Optional[str] = None,
            is_check_auth: bool = True,
    ) -> Any:
        """发送 HTTP 请求"""
        if is_check_auth and not self.is_authed:
            raise BaseUnauthError

        # 确定 token 类型
        token_type = token_type or "JWT"

        # 检查 JWT token 是否即将过期，如果是则自动续期
        # 提前 5 分钟刷新，避免在请求过程中过期
        if is_check_auth and token_type == "JWT" and self.jwt_exp:
            buffer_time = timedelta(minutes=5)
            now = datetime.now()
            threshold = now + buffer_time
            if threshold >= self.jwt_exp:
                # Token 即将过期或已过期，自动刷新
                await self.auth()

        # URL 末尾加斜杠
        if not url.endswith("/"):
            url = url + "/"

        # 构建请求头
        req_headers: Dict[str, str] = {}
        if token_type != "None":
            token = self.jwt_token if token_type == "JWT" else self.token
            req_headers["Authorization"] = f"Token {token}"
        if headers:
            req_headers.update(headers)

        # 清理 None 值
        if json:
            json = {k: v for k, v in json.items() if v is not None}
        if data:
            data = {k: v for k, v in data.items() if v is not None}
        if params:
            params = {k: str(v) for k, v in params.items() if v is not None}

        # 处理文件上传
        req_data: Any = data
        if file is not None:
            form_data = aiohttp.FormData()
            form_data.add_field(name="file", value=file[1], filename=file[0])
            if data:
                for k, v in data.items():
                    form_data.add_field(name=k, value=str(v))
            req_data = form_data

        resp = await self.session.request(
            method=method,
            url=url,
            headers=req_headers,
            json=json,
            data=req_data,
            params=params,
            proxy=proxy or self.proxy,
        )

        status = resp.status
        text = await resp.text()

        if status == 429:
            raise SeatableApiException("429 Too Many Requests")
        if status == 404:
            raise SeatableApiException(f"404 Not Found: {url}")
        if status in (400, 403):
            raise SeatableApiException(text)
        if status >= 400:
            raise SeatableApiException(f"HTTP {status}: {text[:200]}")

        response_type = response_type or "json"
        if response_type == "bytes":
            return await resp.read()
        if response_type == "text":
            return text

        try:
            res = json_loads(text)
            return path_get(res, res_path) if res_path else res
        except JSONDecodeError as e:
            raise SeatableApiException(f"Invalid JSON response: {e}")

    async def get(self, url: str, **kwargs: Any) -> Any:
        return await self.req("GET", url, **kwargs)

    async def post(self, url: str, **kwargs: Any) -> Any:
        return await self.req("POST", url, **kwargs)

    async def put(self, url: str, **kwargs: Any) -> Any:
        return await self.req("PUT", url, **kwargs)

    async def delete(self, url: str, **kwargs: Any) -> Any:
        return await self.req("DELETE", url, **kwargs)

    # ========== 认证 ==========

    async def auth(self) -> None:
        """认证并获取访问令牌"""
        self.jwt_exp = datetime.now() + timedelta(days=3)
        data = await self.get(f"{self.dtable_2_1}/app-access-token", token_type="TOKEN", is_check_auth=False)

        self.dtable_server_url = parse_server_url(data.get("dtable_server"))
        self.dtable_db_url = parse_server_url(data.get("dtable_db", ""))
        self.jwt_token = data.get("access_token")
        self.headers = parse_headers(self.jwt_token)
        self.workspace_id = data.get("workspace_id")
        self.dtable_uuid = data.get("dtable_uuid")
        self.dtable_name = data.get("dtable_name")
        self.use_api_gateway = data.get("use_api_gateway")
        self.is_authed = True

    # ========== 元数据 ==========

    async def get_metadata(self) -> Dict[str, Any]:
        return await self.get(f"{self.dtable}/metadata", res_path="metadata")

    async def list_tables(self) -> List[Dict[str, Any]]:
        meta = await self.get_metadata()
        return meta.get("tables") or []

    async def get_table_by_name(self, table_name: str) -> Optional[Dict[str, Any]]:
        tables = await self.list_tables()
        return next((t for t in tables if t.get("name") == table_name), None)

    # ==== property =====
    @property
    def dtable(self):
        url = f"{self.server_url}/api-gateway/api/v2" if self.use_api_gateway else f"{self.dtable_server_url}/api/v1"
        return f"{url}/dtables/{self.dtable_uuid}"

    @property
    def dtable_db(self):
        return f"{self.dtable_db_url}/api/v1"

    @property
    def dtable_tables(self):
        return f"{self.dtable}/tables"

    @property
    def dtable_views(self):
        return f"{self.dtable}/views"

    @property
    def dtable_rows(self):
        return f"{self.dtable}/rows"

    @property
    def dtable_links(self):
        return f"{self.dtable}/links"

    @property
    def dtable_columns(self):
        return f"{self.dtable}/columns"

    @property
    def dtable_2_1(self):
        return f"{self.server_url}/api/v2.1/dtable"

    @property
    def dtable_custom(self):
        return f"{self.dtable_2_1}/custom"

    # ========== 表操作 ==========

    async def add_table(self, table_name: str, lang: str = "en", columns: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        return await self.post(self.dtable_tables, json={"table_name": table_name, "lang": lang, "columns": columns})

    async def rename_table(self, table_name: str, new_table_name: str) -> Dict[str, Any]:
        return await self.put(self.dtable_tables, json={"table_name": table_name, "new_table_name": new_table_name})

    async def delete_table(self, table_name: str) -> Dict[str, Any]:
        json_data = {"table_name": table_name}
        return await self.delete(self.dtable_tables, json=json_data)

    # ========== 视图操作 ==========

    async def list_views(self, table_name: str) -> Dict[str, Any]:
        return await self.get(self.dtable_views, params={"table_name": table_name})

    async def get_view_by_name(self, table_name: str, view_name: str) -> Dict[str, Any]:
        return await self.get(f"{self.dtable_views}/{view_name}", params={"table_name": table_name})

    async def add_view(self, table_name: str, view_name: str) -> Dict[str, Any]:
        return await self.post(self.dtable_views, json={"name": view_name}, params={"table_name": table_name})

    async def rename_view(self, table_name: str, view_name: str, new_view_name: str) -> Dict[str, Any]:
        return await self.put(f"{self.dtable_views}/{view_name}", json={"name": new_view_name}, params={"table_name": table_name})

    async def delete_view(self, table_name: str, view_name: str) -> Dict[str, Any]:
        return await self.delete(f"{self.dtable_views}/{view_name}", params={"table_name": table_name})

    # ========== 行操作 ==========

    async def list_rows(
            self,
            table_name: str,
            view_name: Optional[str] = None,
            order_by: Optional[str] = None,
            desc: bool = False,
            start: Optional[int] = None,
            limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        params = self._table_params(table_name, view_name=view_name, start=start, limit=limit)
        if order_by:
            params["order_by"] = order_by
            params["direction"] = "desc" if desc else "asc"
        if self.use_api_gateway:
            params["convert_keys"] = True
        return await self.get(self.dtable_rows, params=params, res_path="rows")

    async def get_row(self, table_name: str, row_id: str) -> Dict[str, Any]:
        params = self._table_params(table_name)
        if self.use_api_gateway:
            params["convert_keys"] = True
        return await self.get(f"{self.dtable_rows}/{row_id}", params=params)

    async def append_row(self, table_name: str, row_data: Dict[str, Any], apply_default: Optional[bool] = None) -> Dict[str, Any]:
        json_data: Dict[str, Any] = {**self._table_params(table_name)}
        if apply_default is not None:
            json_data["apply_default"] = apply_default
        if self.use_api_gateway:
            json_data["rows"] = [row_data]
            return await self.post(self.dtable_rows, json=json_data, res_path="first_row")
        else:
            json_data["row"] = row_data
            return await self.post(self.dtable_rows, json=json_data)

    async def batch_append_rows(self, table_name: str, rows_data: List[Dict[str, Any]], apply_default: Optional[bool] = None) -> Dict[str, Any]:
        json_data = {**self._table_params(table_name), "rows": rows_data}
        if apply_default is not None:
            json_data["apply_default"] = apply_default
        if self.use_api_gateway:
            return await self.post(self.dtable_rows, json=json_data)
        else:
            return await self.post(f"{self.dtable}/batch-append-rows", json=json_data)

    async def insert_row(self, table_name: str, row_data: Dict[str, Any], anchor_row_id: str, apply_default: Optional[bool] = None) -> Dict[str, Any]:
        """插入行到指定行之后（v2 API 不支持 anchor_row_id，等同于 append_row）"""
        if self.use_api_gateway:
            return await self.append_row(table_name, row_data, apply_default)
        else:
            return await self.post(self.dtable_rows, json={**self._table_params(table_name), "row": row_data, "anchor_row_id": anchor_row_id, "apply_default": apply_default})

    async def update_row(self, table_name: str, row_id: str, row_data: Dict[str, Any]) -> Dict[str, Any]:
        json_data: Dict[str, Any] = {**self._table_params(table_name)}
        if self.use_api_gateway:
            json_data["updates"] = [{"row_id": row_id, "row": row_data}]
        else:
            json_data.update({"row_id": row_id, "row": row_data})
        return await self.put(self.dtable_rows, json=json_data)

    async def batch_update_rows(self, table_name: str, rows_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        json_data = {**self._table_params(table_name), "updates": rows_data}
        if self.use_api_gateway:
            return await self.put(self.dtable_rows, json=json_data)
        else:
            return await self.put(f"{self.dtable}/batch-update-rows", json=json_data)

    async def delete_row(self, table_name: str, row_id: str) -> Dict[str, Any]:
        json_data: Dict[str, Any] = {**self._table_params(table_name)}
        if self.use_api_gateway:
            json_data["row_ids"] = [row_id]
        else:
            json_data["row_id"] = row_id
        return await self.delete(self.dtable_rows, json=json_data)

    async def batch_delete_rows(self, table_name: str, row_ids: List[str]) -> Dict[str, Any]:
        json_data = {**self._table_params(table_name), "row_ids": row_ids}
        if self.use_api_gateway:
            return await self.delete(self.dtable_rows, json=json_data)
        else:
            return await self.delete(f"{self.dtable}/batch-delete-rows", json=json_data)

    async def filter_rows(
            self,
            table_name: str,
            filters: List[Dict[str, Any]],
            view_name: Optional[str] = None,
            filter_conjunction: Literal["And", "Or"] = "And"
    ) -> List[Dict[str, Any]]:
        """根据条件过滤行"""
        if not filters or not all(isinstance(f, dict) for f in filters):
            raise ValueError("filters invalid")
        for f in filters:
            if not all(k in ROW_FILTER_KEYS for k in f.keys()):
                raise ValueError("filters invalid")
        if filter_conjunction not in ("And", "Or"):
            raise ValueError("filter_conjunction must be 'And' or 'Or'")

        json_data = {"filters": filters, "filter_conjunction": filter_conjunction}
        params = {"table_name": table_name, "view_name": view_name}
        return await self.get(f"{self.dtable_server_url}/api/v1/dtables/{self.dtable_uuid}/filtered-rows", json=json_data, params=params, res_path="rows")

    # ========== 链接操作 ==========

    async def add_link(self, link_id: str, table_name: str, other_table_name: str, row_id: str, other_row_id: str) -> Dict[str, Any]:
        json_data: Dict[str, Any] = {"link_id": link_id, **self._link_params(table_name, other_table_name)}
        if self.use_api_gateway:
            json_data["other_rows_ids_map"] = {row_id: [other_row_id]}
        else:
            json_data.update({"table_row_id": row_id, "other_table_row_id": other_row_id})
        return await self.post(self.dtable_links, json=json_data)

    async def batch_add_links(self, link_id: str, table_name: str, other_table_name: str, other_rows_ids_map: Dict[str, List[str]]) -> Dict[str, Any]:
        json_data = {"link_id": link_id, **self._link_params(table_name, other_table_name), "other_rows_ids_map": other_rows_ids_map}
        return await self.post(self.dtable_links, json=json_data)

    async def remove_link(self, link_id: str, table_name: str, other_table_name: str, row_id: str, other_row_id: str) -> Dict[str, Any]:
        json_data: Dict[str, Any] = {"link_id": link_id, **self._link_params(table_name, other_table_name)}
        if self.use_api_gateway:
            json_data["other_rows_ids_map"] = {row_id: [other_row_id]}
        else:
            json_data.update({"table_row_id": row_id, "other_table_row_id": other_row_id})
        return await self.delete(self.dtable_links, json=json_data)

    async def batch_remove_links(self, link_id: str, table_name: str, other_table_name: str, other_rows_ids_map: Dict[str, List[str]]) -> Dict[str, Any]:
        json_data = {"link_id": link_id, **self._link_params(table_name, other_table_name), "other_rows_ids_map": other_rows_ids_map}
        return await self.delete(self.dtable_links, json=json_data)

    async def update_link(self, link_id: str, table_name: str, other_table_name: str, row_id: str, other_rows_ids: List[str]) -> Dict[str, Any]:
        if not isinstance(other_rows_ids, list):
            raise ValueError("other_rows_ids must be a list")
        json_data: Dict[str, Any] = {"link_id": link_id, **self._link_params(table_name, other_table_name)}
        if self.use_api_gateway:
            json_data.update({"row_id_list": [row_id], "other_rows_ids_map": {row_id: other_rows_ids}})
        else:
            json_data.update({"row_id": row_id, "other_rows_ids": other_rows_ids})
        return await self.put(self.dtable_links, json=json_data)

    async def batch_update_links(self, link_id: str, table_name: str, other_table_name: str, row_id_list: List[str], other_rows_ids_map: Dict[str, List[str]]) -> Dict[str, Any]:
        json_data = {"link_id": link_id, **self._link_params(table_name, other_table_name), "row_id_list": row_id_list, "other_rows_ids_map": other_rows_ids_map}
        if self.use_api_gateway:
            return await self.put(self.dtable_links, json=json_data)
        else:
            return await self.put(f"{self.dtable}/batch-update-links", json=json_data)

    async def get_linked_records(self, table_id: str, link_column_key: str, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        if self.use_api_gateway:
            json_data = {"table_id": table_id, "link_column_key": link_column_key, "rows": rows}
            return await self.post(f"{self.dtable}/query-links", json=json_data)
        else:
            return await self.post(f"{self.dtable_db}/linked-records/{self.dtable_uuid}", json={"table_id": table_id, "link_column": link_column_key, "rows": rows})

    # ========== 列操作 ==========

    async def list_columns(self, table_name: str, view_name: Optional[str] = None) -> List[Dict[str, Any]]:
        params = self._table_params(table_name, view_name=view_name)
        return await self.get(self.dtable_columns, params=params, res_path="columns")

    async def get_column_link_id(self, table_name: str, column_name: str) -> str:
        columns = await self.list_columns(table_name)
        for col in columns:
            if col.get("name") == column_name and col.get("type") == "link":
                return col.get("data", {}).get("link_id")
        raise ValueError(f"link column '{column_name}' not found")

    async def get_column_by_name(self, table_name: str, column_name: str) -> Optional[Dict[str, Any]]:
        columns = await self.list_columns(table_name)
        return next((col for col in columns if col.get("name") == column_name), None)

    async def get_columns_by_type(self, table_name: str, column_type: ColumnTypes) -> List[Dict[str, Any]]:
        if column_type not in ColumnTypes:
            raise ValueError(f"invalid column type: {column_type}")
        columns = await self.list_columns(table_name)
        return [col for col in columns if col.get("type") == column_type.value]

    async def insert_column(
            self,
            table_name: str,
            column_name: str,
            column_type: ColumnTypes,
            column_key: Optional[str] = None,
            column_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        if column_type not in ColumnTypes:
            raise ValueError(f"invalid column type: {column_type}")
        json_data = {
            **self._table_params(table_name),
            "column_name": column_name, "column_type": column_type.value
        }
        if column_key:
            json_data["anchor_column"] = column_key
        if column_data:
            json_data["column_data"] = column_data
        return await self.post(self.dtable_columns, json=json_data)

    async def rename_column(self, table_name: str, column_key: str, new_column_name: str) -> Dict[str, Any]:
        json_data = {**self._table_params(table_name), "op_type": RENAME_COLUMN, "column": column_key, "new_column_name": new_column_name}
        return await self.put(self.dtable_columns, json=json_data)

    async def resize_column(self, table_name: str, column_key: str, new_column_width: int) -> Dict[str, Any]:
        json_data = {**self._table_params(table_name), "op_type": RESIZE_COLUMN, "column": column_key, "new_column_width": new_column_width}
        return await self.put(self.dtable_columns, json=json_data)

    async def freeze_column(self, table_name: str, column_key: str, frozen: bool) -> Dict[str, Any]:
        json_data = {**self._table_params(table_name), "op_type": FREEZE_COLUMN, "column": column_key, "frozen": frozen}
        return await self.put(self.dtable_columns, json=json_data)

    async def move_column(self, table_name: str, column_key: str, target_column_key: str) -> Dict[str, Any]:
        json_data = {**self._table_params(table_name), "op_type": MOVE_COLUMN, "column": column_key, "target_column": target_column_key}
        return await self.put(self.dtable_columns, json=json_data)

    async def modify_column_type(self, table_name: str, column_key: str, new_column_type: ColumnTypes) -> Dict[str, Any]:
        if new_column_type not in ColumnTypes:
            raise ValueError(f"invalid column type: {new_column_type}")
        if new_column_type == ColumnTypes.LINK:
            raise ValueError("cannot change to link column type")
        json_data = {**self._table_params(table_name), "op_type": MODIFY_COLUMN_TYPE, "column": column_key, "new_column_type": new_column_type.value}
        return await self.put(self.dtable_columns, json=json_data)

    async def add_column_options(self, table_name: str, column: str, options: List[Dict[str, Any]]) -> Dict[str, Any]:
        """添加单选/多选列选项"""
        json_data = {**self._table_params(table_name), "column": column, "options": options}
        return await self.post(f"{self.dtable}/column-options", json=json_data)

    async def add_column_cascade_settings(self, table_name: str, child_column: str, parent_column: str, cascade_settings: Dict[str, Any]) -> Dict[str, Any]:
        """添加单选列级联设置"""
        json_data = {**self._table_params(table_name), "child_column": child_column, "parent_column": parent_column, "cascade_settings": cascade_settings}
        return await self.post(f"{self.dtable}/column-cascade-settings", json=json_data)

    async def delete_column(self, table_name: str, column_key: str) -> Dict[str, Any]:
        json_data = {**self._table_params(table_name), "column": column_key}
        return await self.delete(self.dtable_columns, json=json_data)

    # ========== 文件操作 ==========

    async def get_file_download_link(self, path: str) -> str:
        return await self.get(f"{self.dtable_2_1}/app-download-link", params={"path": path}, token_type="TOKEN", res_path="download_link")

    async def get_file_upload_link(self) -> Dict[str, Any]:
        return await self.get(f"{self.dtable_2_1}/app-upload-link", token_type="TOKEN")

    def _build_asset_url(self, relative_path: str, filename: str) -> str:
        """构建资源 URL"""
        return f"{self.server_url}/workspace/{self.workspace_id}/asset/{UUID(self.dtable_uuid)}/{parse.quote(relative_path.strip('/'))}/{parse.quote(filename)}"

    async def _download_to_file(self, download_link: str, save_path: str) -> None:
        """下载链接内容到本地文件"""
        data = await self.get(download_link, response_type="bytes")
        async with aiofiles.open(save_path, "wb") as f:
            await f.write(data)

    async def _upload_content(self, upload_info: Dict[str, Any], name: str, content: bytes, file_type: str, replace: bool) -> Dict[str, Any]:
        """上传内容并返回文件信息"""
        relative_path = upload_info["img_relative_path"] if file_type == "image" else upload_info["file_relative_path"]
        upload_url = upload_info["upload_link"] + "?ret-json=1"
        data = {"parent_dir": upload_info["parent_path"], "relative_path": relative_path, "replace": 1 if replace else 0}
        res = await self.post(upload_url, data=data, file=(name, content), token_type="None")
        d = res[0]
        return {"type": file_type, "size": d.get("size"), "name": d.get("name"), "url": self._build_asset_url(relative_path, d.get("name", name))}

    async def download_file(self, url: str, save_path: str) -> None:
        """下载文件到本地"""
        uuid_str = str(UUID(self.dtable_uuid))
        if uuid_str not in url:
            raise SeatableApiException("url invalid")
        path = url.split(uuid_str)[-1].strip("/")
        download_link = await self.get_file_download_link(parse.unquote(path))
        await self._download_to_file(download_link, save_path)

    async def upload_bytes_file(self, name: str, content: bytes, file_type: Literal["file", "image"] = "file", replace: bool = False) -> Dict[str, Any]:
        """上传字节内容"""
        if file_type not in ("file", "image"):
            raise SeatableApiException("file_type must be 'file' or 'image'")
        upload_info = await self.get_file_upload_link()
        return await self._upload_content(upload_info, name, content, file_type, replace)

    async def upload_local_file(self, file_path: str, name: Optional[str] = None, file_type: Literal["file", "image"] = "file", replace: bool = False) -> Dict[str, Any]:
        """上传本地文件"""
        if file_type not in ("file", "image"):
            raise SeatableApiException("file_type must be 'file' or 'image'")
        name = name or file_path.split("/")[-1]
        async with aiofiles.open(file_path, "rb") as f:
            content = await f.read()
        upload_info = await self.get_file_upload_link()
        return await self._upload_content(upload_info, name, content, file_type, replace)

    # ========== 自定义文件夹 ==========

    async def get_custom_file_download_link(self, path: str) -> str:
        res = await self.get(f"{self.dtable_custom}/app-download-link", params={"path": path}, token_type="TOKEN")
        if res.get("error_msg"):
            raise SeatableApiException(res["error_msg"])
        return res.get("download_link")

    async def get_custom_file_upload_link(self, path: str) -> Dict[str, Any]:
        return await self.get(f"{self.dtable_custom}/app-upload-link", params={"path": path}, token_type="TOKEN")

    async def download_custom_file(self, path: str, save_path: str) -> None:
        """下载自定义文件夹中的文件"""
        download_link = await self.get_custom_file_download_link(parse.unquote(path))
        await self._download_to_file(download_link, save_path)

    async def get_custom_file_info(self, path: str, name: str) -> Dict[str, Any]:
        """获取自定义文件信息"""
        res = await self.get(f"{self.dtable_custom}/app-asset-file", params={"path": path, "name": name}, token_type="TOKEN")
        d = res["dirent"]
        file_name = d.get("obj_name")
        return {"type": "file", "size": d.get("file_size"), "name": file_name, "url": f"custom-asset://{d.get('uuid')}.{file_name.split('.')[-1]}"}

    async def upload_local_file_to_custom_folder(self, local_path: str, custom_folder_path: Optional[str] = None, name: Optional[str] = None) -> Dict[str, Any]:
        """上传文件到自定义文件夹"""
        name = name or local_path.split("/")[-1]
        custom_folder_path = custom_folder_path or "/"
        upload_info = await self.get_custom_file_upload_link(parse.unquote(custom_folder_path))
        upload_url = upload_info["upload_link"] + "?ret-json=1"
        async with aiofiles.open(local_path, "rb") as f:
            content = await f.read()
        data = {"parent_dir": upload_info["parent_path"], "relative_path": upload_info["relative_path"], "replace": 0}
        res = await self.post(upload_url, data=data, file=(name, content), token_type="None")
        return await self.get_custom_file_info(path=custom_folder_path, name=res[0].get("name"))

    async def list_custom_assets(self, path: str) -> Dict[str, Any]:
        """列出自定义文件夹内容"""
        return await self.get(f"{self.dtable_custom}/app-asset-dir", params={"path": path}, token_type="TOKEN")

    # ========== 其他 ==========

    async def query(self, sql: str, convert: bool = True) -> List[Dict[str, Any]]:
        """执行 SQL 查询"""
        if not sql:
            raise ValueError("sql cannot be empty")
        data = await self.post(f"{self.dtable_db}/query/{self.dtable_uuid}", json={"sql": sql})
        if not data.get("success"):
            raise SeatableApiException(data.get("error_message"))
        results = data.get("results")
        return convert_db_rows(data.get("metadata"), results) if convert else results

    async def get_related_users(self) -> List[Dict[str, Any]]:
        return await self.get(f"{self.server_url}/api/v2.1/dtables/{self.dtable_uuid}/related-users", res_path="user_list")

    async def big_data_insert_rows(self, table_name: str, rows_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """大数据插入行"""
        url = f"{self.dtable}/add-archived-rows" if self.use_api_gateway else f"{self.dtable_db}/insert-rows/{self.dtable_uuid}"
        return await self.post(url, json={"table_name": table_name, "rows": rows_data})

    async def get_user_info(self, username: str) -> Dict[str, Any]:
        return await self.get(f"{self.dtable_2_1}/app-user-info", params={"username": username}, token_type="TOKEN")
