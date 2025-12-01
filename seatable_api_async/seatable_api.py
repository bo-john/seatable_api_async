import typing
from datetime import datetime, timedelta
from json import JSONDecodeError, loads as json_loads
from urllib import parse
from uuid import UUID

import aiohttp

from seatable_api_async.constants import (
    ROW_FILTER_KEYS,
    ColumnTypes,
    RENAME_COLUMN,
    RESIZE_COLUMN,
    FREEZE_COLUMN,
    MOVE_COLUMN,
    MODIFY_COLUMN_TYPE)
from seatable_api_async.exception import BaseUnauthError
from seatable_api_async.exception import SeatableApiException
from seatable_api_async.query import QuerySet
from seatable_api_async.utils import parse_server_url, parse_headers, like_table_id, convert_db_rows


class SeaTableApiAsync(object):

    def __init__(self, token, server_url, proxy=None):
        self.token = token
        self.server_url = server_url
        self.dtable_server_url = None
        self.dtable_db_url = None
        self.jwt_token = None
        self.jwt_exp = None
        self.headers = None
        self.workspace_id = None
        self.dtable_uuid = None
        self.dtable_name = None
        self.timeout = 30
        self.socketIO = None
        self.is_authed = False

        self.use_api_gateway = False
        self.api_gateway = None
        self.proxy = proxy
        self.session = aiohttp.ClientSession(proxy=proxy)

    def __str__(self):
        return f'<SeaTable Base [ {self.dtable_name} ]>'

    async def __aenter__(self):
        await self.session.__aenter__()
        await self.auth()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.session.__aexit__(exc_type, exc_val, exc_tb)

    def _table_server_url(self):
        return f"dtable-server/api/v1/dtables/{self.dtable_uuid}/tables/"

    def _view_server_url(self):
        return f"dtable-server/api/v1/dtables/{self.dtable_uuid}/views/"

    def _row_server_url(self):
        return f"dtable-server/api/v1/dtables/{self.dtable_uuid}/rows/"

    def _row_link_server_url(self):
        return f"dtable-server/api/v1/dtables/{self.dtable_uuid}/links/"

    def _column_server_url(self):
        return f"dtable-server/api/v1/dtables/{self.dtable_uuid}/columns/"

    async def get(self, action, json=None, params=None, headers=None,
                  proxy=None, token_type=None, response_type=None,
                  is_check_auth: bool = True):
        return await self.req(
            method="GET",
            action=action,
            json=json,
            params=params,
            headers=headers,
            proxy=proxy,
            token_type=token_type,
            response_type=response_type,
            is_check_auth=is_check_auth
        )

    async def post(
            self, action, json=None, data=None, params=None, headers=None, proxy=None, token_type=None,
            response_type=None, file=None, is_check_auth: bool = True):
        return await self.req(
            method="POST",
            action=action,
            json=json,
            data=data,
            file=file,
            params=params,
            headers=headers,
            proxy=proxy,
            token_type=token_type,
            response_type=response_type,
            is_check_auth=is_check_auth
        )

    async def put(self, action, json=None, data=None, params=None, headers=None, proxy=None, token_type=None,
                  response_type=None, is_check_auth: bool = True):
        return await self.req(
            method="PUT",
            action=action,
            json=json,
            data=data,
            params=params,
            headers=headers,
            proxy=proxy,
            token_type=token_type,
            response_type=response_type,
            is_check_auth=is_check_auth
        )

    async def delete(self, action, json=None, data=None, params=None, headers=None, proxy=None,
                     token_type=None, is_check_auth: bool = True):
        return await self.req(
            method="DELETE",
            action=action,
            json=json,
            data=data,
            params=params,
            headers=headers,
            proxy=proxy,
            token_type=token_type,
            is_check_auth=is_check_auth
        )

    async def req(
            self,
            method: typing.Literal["GET", "POST", "PUT", "DELETE"],
            action,
            json=None,
            data=None,
            file: typing.Tuple[str, bytes] = None,
            params=None,
            headers=None,
            proxy=None,
            token_type: typing.Literal["JWT", "TOKEN", "None"] = None,
            response_type: typing.Literal["json", "text", "bytes"] = None,
            is_check_auth: bool = True,
    ) -> typing.Union[str, typing.Dict, bytes]:

        if is_check_auth and not self.is_authed:
            raise BaseUnauthError

        split_index = action.find("/")
        dtable_type = action[:split_index]
        dtable_path = action[split_index + 1:]
        if dtable_type == "dtable-server":
            url = self.dtable_server_url
            action = dtable_path
        elif dtable_type == "dtable-db":
            url = self.dtable_db_url
            action = dtable_path
        else:
            url = self.server_url

        token_type = token_type or "JWT"
        base_headers = {}
        if self.jwt_token != "None":
            base_headers.update({
                "Authorization": f"Token {self.jwt_token if token_type == 'JWT' else self.token}",
            })
        headers = headers or {}
        base_headers.update(headers)

        data = {k: v for k, v in data.items() if v is not None} if data else None
        if file is not None:
            form_data = aiohttp.FormData()
            form_data.add_field(
                name="file",
                value=file[1],
                filename=file[0],
            )
            for k, v in data.items():
                form_data.add_field(
                    name=k,
                    value=str(v),
                )
            data = form_data

        resp = await self.session.request(
            method=method,
            url=f"{url}/{action}",
            headers=base_headers,
            json={k: v for k, v in json.items() if v is not None} if json else None,
            data=data,
            params={k: str(v) for k, v in params.items() if v is not None} if params else None,
            proxy=proxy,
            ssl=False,
        )
        res_status = resp.status
        res_text = await resp.text()

        if res_status == 429:
            raise SeatableApiException("429 Too Many Requests")

        if res_status == 404:
            raise SeatableApiException("请求404")

        if res_status in [400, 403]:
            raise SeatableApiException(res_text)

        response_type = response_type or "json"

        if response_type == "bytes":
            return await resp.read()

        if response_type == "text":
            return res_text

        try:
            res = json_loads(res_text)
        except JSONDecodeError as e:
            raise SeatableApiException("response not json", e)

        return res

    async def auth(self):
        """Auth to SeaTable
        """
        self.jwt_exp = datetime.now() + timedelta(days=3)
        action = "api/v2.1/dtable/app-access-token/"
        data = await self.get(action=action, token_type="TOKEN", is_check_auth=False)

        self.dtable_server_url = parse_server_url(data.get("dtable_server"))
        self.dtable_db_url = parse_server_url(data.get("dtable_db", ""))

        self.jwt_token = data.get("access_token")
        self.headers = parse_headers(self.jwt_token)
        self.workspace_id = data.get("workspace_id")
        self.dtable_uuid = data.get("dtable_uuid")
        self.dtable_name = data.get("dtable_name")

        self.use_api_gateway = data.get("use_api_gateway")

        self.is_authed = True

    async def get_metadata(self):
        action = f"dtable-server/api/v1/dtables/{self.dtable_uuid}/metadata/"
        data = await self.get(action=action)
        return data.get("metadata")

    async def list_tables(self):
        meta = await self.get_metadata()
        return meta.get("tables") or []

    async def get_table_by_name(self, table_name):
        tables = await self.list_tables()
        for t in tables:
            if t.get("name") == table_name:
                return t
        return None

    async def add_table(self, table_name, lang="en", columns=None):
        return await self.post(
            action=self._table_server_url(),
            json={
                "table_name": table_name,
                "lang": lang,
                "columns": columns,
            })

    async def rename_table(self, table_name, new_table_name):
        return await self.put(
            action=self._table_server_url(),
            json={
                "table_name": table_name,
                "new_table_name": new_table_name
            })

    async def delete_table(self, table_name):
        return await self.delete(
            action=self._table_server_url(),
            json={
                "table_name": table_name,
            }
        )

    async def list_views(self, table_name):
        return await self.get(
            action=self._view_server_url(),
            params={"table_name": table_name}
        )

    async def get_view_by_name(self, table_name, view_name):
        return await self.get(
            action=f"{self._view_server_url().rstrip('/')}/{view_name}/",
            params={"table_name": table_name}
        )

    async def add_view(self, table_name, view_name):
        return await self.post(
            action=f"{self._view_server_url().rstrip('/')}/",
            json={"name": view_name},
            params={"table_name": table_name},
        )

    async def rename_view(self, table_name, view_name, new_view_name):
        return await self.put(
            action=f"{self._view_server_url().rstrip('/')}/{view_name}/",
            json={"name": new_view_name},
            params={"table_name": table_name}
        )

    async def delete_view(self, table_name, view_name):
        return await self.delete(
            action=f"{self._view_server_url().rstrip('/')}/{view_name}/",
            params={"table_name": table_name}
        )

    async def list_rows(self, table_name, view_name=None, order_by=None, desc=False, start=None, limit=None):
        params = {
            "table_name": table_name,
            "view_name": view_name,
            "start": start,
            "limit": limit,
        }

        if like_table_id(table_name):
            params["table_id"] = table_name
        if order_by:
            params.update({
                "order_by": order_by,
                "direction": "desc" if desc else "asc"
            })
        res = await self.get(
            action=self._row_server_url(),
            params=params)
        return res.get("rows")

    async def get_row(self, table_name, row_id):
        return await self.get(
            action=f"{self._row_server_url().rstrip('/')}/{row_id}",
            params={
                "table_id": table_name if like_table_id(table_name) else None,
                "table_name": table_name
            })

    async def append_row(self, table_name, row_data, apply_default=None):
        return await self.post(action=self._row_server_url(), json={
            "table_id": table_name if like_table_id(table_name) else None,
            "table_name": table_name,
            "row": row_data,
            "apply_default": apply_default
        })

    async def batch_append_rows(self, table_name, rows_data, apply_default=None):
        return await self.post(
            action=f"dtable-server/api/v1/dtables/{self.dtable_uuid}/batch-append-rows/",
            json={
                "table_id": table_name if like_table_id(table_name) else None,
                "table_name": table_name,
                "rows": rows_data,
                "apply_default": apply_default
            })

    async def insert_row(self, table_name, row_data, anchor_row_id, apply_default=None):
        return await self.post(
            action=self._row_server_url(),
            json={
                "table_id": table_name if like_table_id(table_name) else None,
                "table_name": table_name,
                "row": row_data,
                "anchor_row_id": anchor_row_id,
                "apply_default": apply_default
            })

    async def update_row(self, table_name, row_id, row_data):
        return await self.put(
            action=self._row_server_url(),
            json={
                "table_id": table_name if like_table_id(table_name) else None,
                "table_name": table_name,
                "row_id": row_id,
                "row": row_data,
            })

    async def batch_update_rows(self, table_name, rows_data):
        return await self.put(
            action=f"dtable-server/api/v1/dtables/{self.dtable_uuid}/batch-update-rows/",
            json={
                "table_id": table_name if like_table_id(table_name) else None,
                "table_name": table_name,
                "updates": rows_data,
            })

    async def delete_row(self, table_name, row_id):
        return await self.delete(
            action=self._row_server_url(),
            json={
                "table_id": table_name if like_table_id(table_name) else None,
                "table_name": table_name,
                "row_id": row_id,
            })

    async def batch_delete_rows(self, table_name, row_ids):
        return await self.delete(
            action=f"dtable-server/api/v1/dtables/{self.dtable_uuid}/batch-delete-rows/",
            json={
                "table_id": table_name if like_table_id(table_name) else None,
                "table_name": table_name,
                "row_ids": row_ids,
            })

    # no test 可用query函数代替,更常用
    async def filter_rows(self, table_name, filters, view_name=None, filter_conjunction="And"):

        if not filters:
            raise ValueError("filters can not be empty.")
        if not isinstance(filters, list):
            raise ValueError("filters invalid.")
        if len(filters) != len([f for f in filters if isinstance(f, dict)]):
            raise ValueError("filters invalid.")

        for f in filters:
            for key in f.keys():
                if key not in ROW_FILTER_KEYS:
                    raise ValueError("filters invalid.")

        if filter_conjunction not in ["And", "Or"]:
            raise ValueError("filter_conjunction invalid, filter_conjunction must be"
                             "And" or "Or")

        params = {
            "table_name": table_name,
        }
        json_data = {
            "filters": filters,
            "filter_conjunction": filter_conjunction,
        }

        action = f"dtable-server/api/v1/dtables/{self.dtable_uuid}/filtered-rows/"
        res = await self.get(action=action, json=json_data, params=params)
        return res.get("rows")

    async def get_file_download_link(self, path):
        res = await self.get(
            action="api/v2.1/dtable/app-download-link/",
            params={"path": path},
            token_type="TOKEN")
        return res.get("download_link")

    async def get_file_upload_link(self) -> dict:
        return await self.get(
            action="api/v2.1/dtable/app-upload-link/",
            token_type="TOKEN")

    # no test
    async def add_link(self, link_id, table_name, other_table_name, row_id, other_row_id):
        return await self.post(
            action=self._row_link_server_url(),
            json={
                "link_id": link_id,
                "table_name": table_name,
                "other_table_name": other_table_name,
                "table_row_id": row_id,
                "other_table_row_id": other_row_id,
                "table_id": table_name if like_table_id(table_name) else None,
                "other_table_id": other_table_name if like_table_id(other_table_name) else None,
            })

    # no test
    async def batch_add_links(self, link_id, table_name, other_table_name, other_rows_ids_map):
        return await self.post(
            action=self._row_link_server_url(),
            json={
                "link_id": link_id,
                "table_name": table_name,
                "other_table_name": other_table_name,
                "other_rows_ids_map": other_rows_ids_map,
                "table_id": table_name if like_table_id(table_name) else None,
                "other_table_id": other_table_name if like_table_id(other_table_name) else None,
            })

    # no test
    async def remove_link(self, link_id, table_name, other_table_name, row_id, other_row_id):
        return await self.delete(
            action=self._row_link_server_url(),
            json={
                "link_id": link_id,
                "table_name": table_name,
                "other_table_name": other_table_name,
                "table_row_id": row_id,
                "other_table_row_id": other_row_id,
                "table_id": table_name if like_table_id(table_name) else None,
                "other_table_id": other_table_name if like_table_id(other_table_name) else None,
            })

    # no test
    async def batch_remove_links(self, link_id, table_name, other_table_name, other_rows_ids_map):
        return await self.delete(
            action=self._row_link_server_url(),
            json={
                "link_id": link_id,
                "table_name": table_name,
                "other_table_name": other_table_name,
                "other_rows_ids_map": other_rows_ids_map,
                "table_id": table_name if like_table_id(table_name) else None,
                "other_table_id": other_table_name if like_table_id(other_table_name) else None,
            })

    # no test
    async def update_link(self, link_id, table_name, other_table_name, row_id, other_rows_ids):
        if not isinstance(other_rows_ids, list):
            raise ValueError("params other_rows_ids requires type list")

        return await self.put(
            action=self._row_link_server_url(),
            json={
                "link_id": link_id,
                "table_name": table_name,
                "other_table_name": other_table_name,
                "row_id": row_id,
                "other_rows_ids": other_rows_ids,
                "table_id": table_name if like_table_id(table_name) else None,
                "other_table_id": other_table_name if like_table_id(other_table_name) else None,
            })

    # no test
    async def batch_update_links(self, link_id, table_name, other_table_name, row_id_list, other_rows_ids_map):
        return await self.put(
            action=f"dtable-server/api/v1/dtables/{self.dtable_uuid}/batch-update-links/",
            json={
                "link_id": link_id,
                "table_name": table_name,
                "other_table_name": other_table_name,
                "row_id_list": row_id_list,
                "other_rows_ids_map": other_rows_ids_map,
                "table_id": table_name if like_table_id(table_name) else None,
                "other_table_id": other_table_name if like_table_id(other_table_name) else None,
            })

    # no test
    async def get_linked_records(self, table_id, link_column_key, rows):
        return await self.get(
            action=f"dtable-server/api/v1/linked-records/{self.dtable_uuid}/",
            json={
                "table_id": table_id,
                "link_column": link_column_key,
                "rows": rows,
            })

    async def list_columns(self, table_name, view_name=None):
        action = self._column_server_url()
        params = {
            "table_id": table_name if like_table_id(table_name) else None,
            "table_name": table_name,
            "view_name": view_name
        }
        res = await self.get(action=action, params=params)
        return res.get("columns")

    async def get_column_link_id(self, table_name, column_name):
        columns = await self.list_columns(table_name)
        for column in columns:
            if column.get("name") == column_name and column.get("type") == "link":
                return column.get("data", {}).get("link_id")
        raise ValueError(f"link type column {column_name} does not exist in current table")

    async def get_column_by_name(self, table_name, column_name):
        columns = await self.list_columns(table_name)
        for col in columns:
            if col.get("name") == column_name:
                return col
        return None

    async def get_columns_by_type(self, table_name, column_type: ColumnTypes):
        if column_type not in ColumnTypes:
            raise ValueError("type %s invalid!" % (column_type,))
        columns = await self.list_columns(table_name)
        cols_results = [col for col in columns if col.get("type") == column_type.value]
        return cols_results

    async def insert_column(self, table_name, column_name, column_type, column_key=None, column_data=None):
        if column_type not in ColumnTypes:
            raise ValueError("type %s invalid!" % (column_type,))
        return await self.post(
            action=self._column_server_url(),
            json={
                "table_id": table_name if like_table_id(table_name) else None,
                "table_name": table_name,
                "column_name": column_name,
                "column_type": column_type.value,
                "column_data": column_data,
                "anchor_column": column_key
            })

    async def rename_column(self, table_name, column_key, new_column_name):
        return await self.put(
            action=self._column_server_url(),
            json={
                "table_id": table_name if like_table_id(table_name) else None,
                "op_type": RENAME_COLUMN,
                "table_name": table_name,
                "column": column_key,
                "new_column_name": new_column_name
            })

    async def resize_column(self, table_name, column_key, new_column_width):
        return await self.put(
            action=self._column_server_url(),
            json={
                "table_id": table_name if like_table_id(table_name) else None,
                "op_type": RESIZE_COLUMN,
                "table_name": table_name,
                "column": column_key,
                "new_column_width": new_column_width
            })

    async def freeze_column(self, table_name, column_key, frozen):
        return await self.put(
            action=self._column_server_url(),
            json={
                "table_id": table_name if like_table_id(table_name) else None,
                "op_type": FREEZE_COLUMN,
                "table_name": table_name,
                "column": column_key,
                "frozen": frozen
            })

    async def move_column(self, table_name, column_key, target_column_key):
        return await self.put(
            action=self._column_server_url(),
            json={
                "table_id": table_name if like_table_id(table_name) else None,
                "op_type": MOVE_COLUMN,
                "table_name": table_name,
                "column": column_key,
                "target_column": target_column_key
            })

    async def modify_column_type(self, table_name, column_key, new_column_type):
        if new_column_type not in ColumnTypes:
            raise ValueError("type %s invalid!" % (new_column_type,))
        if new_column_type == ColumnTypes.LINK:
            raise ValueError("Switching to link column type is not allowed!")

        return await self.put(
            action=self._column_server_url(),
            json={
                "table_id": table_name if like_table_id(table_name) else None,
                "op_type": MODIFY_COLUMN_TYPE,
                "table_name": table_name,
                "column": column_key,
                "new_column_type": new_column_type.value
            })

    # 单选，多选列专用，添加选项
    async def add_column_options(self, table_name, column, options):
        return await self.post(
            action=f"dtable-server/api/v1/dtables/{self.dtable_uuid}/column-options/",
            json={
                "table_id": table_name if like_table_id(table_name) else None,
                "table_name": table_name,
                "column": column,
                "options": options
            })

    # 单选列专用，添加单选选项的父子及联关系，达到子列的单选选项条目根据父列的选项而定的效果
    async def add_column_cascade_settings(self, table_name, child_column, parent_column, cascade_settings):
        return await self.post(
            action=f"dtable-server/api/v1/dtables/{self.dtable_uuid}/ccolumn-cascade-settings/",
            json={
                "table_id": table_name if like_table_id(table_name) else None,
                "table_name": table_name,
                "child_column": child_column,
                "parent_column": parent_column,
                "cascade_settings": cascade_settings
            })

    async def delete_column(self, table_name, column_key):
        return await self.delete(
            action=self._column_server_url(),
            json={
                "table_id": table_name if like_table_id(table_name) else None,
                "table_name": table_name,
                "column": column_key
            })

    # 从seatable下载文件到本地
    # url示例:"http://192.168.150.145:30080/workspace/46/asset/b6721580-4f5b-4a92-b386-1078f4d77a36/files/2025-11/recall.txt"
    # save_path示例:"/Users/xiongbo/workspace/seatable-api-plus/tests/recall.txt"
    async def download_file(self, url, save_path):
        if not str(UUID(self.dtable_uuid)) in url:
            raise SeatableApiException("url invalid.")
        path = url.split(str(UUID(self.dtable_uuid)))[-1].strip("/")
        download_link = await self.get_file_download_link(parse.unquote(path))
        action = download_link.split(self.server_url, 1)[-1].strip("/")  # 分割一次并取最后部分
        res = await self.get(action=action, response_type='bytes')
        with open(save_path, "wb") as f:
            f.write(res)

    # 上传文件到云端seatable
    async def upload_bytes_file(self, name, content: bytes, file_type='file', replace=False):

        if file_type not in ["image", "file"]:
            raise SeatableApiException("relative or file_type invalid.")
        upload_link_dict = await self.get_file_upload_link()
        if file_type == "image":
            relative_path = upload_link_dict['img_relative_path']
        else:
            relative_path = upload_link_dict['file_relative_path']

        parent_dir = upload_link_dict["parent_path"]
        upload_link = upload_link_dict["upload_link"] + "?ret-json=1"

        action = upload_link.split(self.server_url, 1)[-1].strip("/")
        file = (name, content)
        data = {
            "parent_dir": parent_dir,
            "relative_path": relative_path,
            "replace": 1 if replace else 0,
        }

        res = await self.post(action=action, data=data, file=file, token_type="None")
        d = res[0]

        url = "/".join([
            self.server_url.strip("/"),
            "workspace", str(self.workspace_id),
            "asset",
            str(UUID(self.dtable_uuid)),
            parse.quote(relative_path.strip("/")),
            parse.quote(d.get("name", name))
        ])
        return {
            "type": file_type,
            "size": d.get("size"),
            "name": d.get("name"),
            "url": url
        }

    # 上传本地文件到云端seatable
    async def upload_local_file(self, file_path, name=None, file_type='file', replace=False):
        if file_type not in ['image', "file"]:
            raise SeatableApiException("file_type invalid.")
        if not name:
            name = file_path.strip("/").split("/")[-1]
        if file_type not in ["image", "file"]:
            raise SeatableApiException("relative or file_type invalid.")

        upload_link_dict = await self.get_file_upload_link()
        if file_type == "image":
            relative_path = upload_link_dict["img_relative_path"]
        else:
            relative_path = upload_link_dict["file_relative_path"]

        parent_dir = upload_link_dict['parent_path']
        upload_link = upload_link_dict['upload_link'] + "?ret-json=1"

        action = upload_link.split(self.server_url, 1)[-1].strip("/")
        file = (name, open(file_path, "rb"))
        data = {
            "parent_dir": parent_dir,
            "relative_path": relative_path,
            "replace": 1 if replace else 0,
        }

        res = await self.post(action=action, data=data, file=file, token_type="None")
        d = res[0]
        url = (f"{self.server_url.strip('/')}/workspace/{self.workspace_id}/asset/"
               f"{str(UUID(self.dtable_uuid))}/{parse.quote(relative_path.strip('/'))}/"
               f"{parse.quote(d.get('name', name))}")
        return {
            "type": file_type,
            "size": d.get("size"),
            "name": d.get("name"),
            "url": url
        }

    async def filter(self, table_name, conditions='', view_name=None):
        queryset = QuerySet(self, table_name)
        queryset.raw_rows = await self.list_rows(table_name, view_name)
        queryset.raw_columns = await self.list_columns(table_name, view_name)
        queryset.conditions = conditions
        queryset._execute_conditions()
        return queryset

    async def query(self, sql, convert=True):
        if not sql:
            raise ValueError("sql can not be empty.")
        action = f"dtable-db/api/v1/query/{self.dtable_uuid}/"
        json_data = {'sql': sql}
        data = await self.post(action=action, json=json_data)
        if not data.get("success"):
            raise SeatableApiException(data.get("error_message"))
        metadata = data.get("metadata")
        results = data.get("results")
        if convert:
            converted_results = convert_db_rows(metadata, results)
            return converted_results
        else:
            return results

    async def get_related_users(self):
        res = await self.get(action=f"api/v2.1/dtables/{self.dtable_uuid}/related-users/")
        return res['user_list']

    async def big_data_insert_rows(self, table_name, rows_data):
        return await self.post(
            action=f"dtable-db/api/v1/insert-rows/{self.dtable_uuid}/",
            json={
                "table_name": table_name,
                "rows": rows_data,
            })

    async def get_custom_file_download_link(self, path):
        action = "api/v2.1/dtable/custom/app-download-link/"
        params = {"path": path}
        res = await self.get(action=action, params=params, token_type="TOKEN")
        error_msg = res.get("error_msg")
        if error_msg:
            raise SeatableApiException(error_msg)
        return res.get("download_link")

    # 得到自定义文件夹上传链接
    async def get_custom_file_upload_link(self, path):
        return await self.get(
            action="api/v2.1/dtable/custom/app-upload-link/",
            params={"path": path},
            token_type="TOKEN"
        )

    # 下载自定义文件夹中的文件
    async def download_custom_file(self, path, save_path):
        download_link = await self.get_custom_file_download_link(parse.unquote(path))
        action = download_link.split(self.server_url, 1)[-1].strip("/")
        res = await self.get(action=action, response_type="bytes")
        with open(save_path, "wb") as f:
            f.write(res)

    # 得到自定义文件信息
    async def get_custom_file_info(self, path, name):
        action = "api/v2.1/dtable/custom/app-asset-file/"
        params = {"path": path, "name": name}
        headers = parse_headers(self.token)
        res = await self.get(action=action, headers=headers, params=params)
        d = res["dirent"]
        file_name = d.get("obj_name")
        file_name_ext = file_name.split(".")[-1]
        asset_uuid = d.get("uuid")

        return {
            "type": "file",
            "size": d.get("file_size"),
            "name": d.get("obj_name"),
            "url": "custom-asset://%s.%s" % (asset_uuid, file_name_ext)
        }

    # 上传本地文件到seatable云端的自定义文件夹中
    async def upload_local_file_to_custom_folder(self, local_path, custom_folder_path=None, name=None, ):
        if not name:
            name = local_path.strip("/").split("/")[-1]
        if not custom_folder_path:
            custom_folder_path = "/"

        upload_link_dict = await self.get_custom_file_upload_link(parse.unquote(custom_folder_path))
        upload_link = upload_link_dict.get("upload_link") + "?ret-json=1"
        parent_path = upload_link_dict.get("parent_path")
        relative_path = upload_link_dict.get("relative_path")

        action = upload_link.split(self.server_url, 1)[-1].strip("/")
        file = (name, open(local_path, "rb"))
        data = {
            "parent_dir": parent_path,
            "relative_path": relative_path,
            "replace": 0,
        }
        res = await self.post(action=action, data=data, file=file, token_type="None")
        d = res[0]
        file_name = d.get("name")
        return await self.get_custom_file_info(path=custom_folder_path, name=file_name)

    # 列出自定义目录文件夹中的文件
    async def list_custom_assets(self, path):
        return await self.get(
            action=f"api/v2.1/dtable/custom/app-asset-dir/",
            params={"path": path},
            token_type="TOKEN")

    async def get_user_info(self, username):
        return await self.get(
            action="api/v2.1/dtable/app-user-info/",
            params={"username": username},
            token_type="TOKEN"
        )
