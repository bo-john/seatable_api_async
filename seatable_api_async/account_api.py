import typing
from json import JSONDecodeError, loads as json_loads

import aiohttp

from seatable_api_async.exception import AccountApiAsyncException


class AccountApiAsync(object):
    def __init__(self, login_name, password, server_url, proxy=None):
        self.login_name = login_name
        self.username = None
        self.password = password
        self.server_url = server_url.strip().strip('/')
        self.token = None
        self.timeout = 30
        self.session = aiohttp.ClientSession(proxy=proxy)
        self.proxy = proxy

    async def __aenter__(self):
        await self.session.__aenter__()
        await self.auth()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.session.__aexit__(exc_type, exc_val, exc_tb)

    def __str__(self):
        return f'<SeaTable Account [ {self.login_name} ]>'

    async def get(self, action, params=None, headers=None, proxy=None):
        return await self.req("GET", action=action, params=params, headers=headers, proxy=proxy)

    async def post(self, action, json=None, data=None, params=None, headers=None, proxy=None):
        return await self.req(
            "POST",
            action,
            json=json,
            data=data,
            params=params,
            headers=headers,
            proxy=proxy)

    async def req(
            self,
            method: typing.Literal["GET", "POST"],
            action,
            json=None,
            data=None,
            params=None,
            headers=None,
            proxy=None
    ):
        base_headers = {}
        if self.token:
            base_headers = {
                'Authorization': 'Token %s' % (self.token,)
            }
        headers = headers or {}
        base_headers.update(headers)

        resp = await self.session.request(
            method=method,
            url=f"{self.server_url}/{action}",
            headers=base_headers,
            json=json,
            params=params,
            data=data,
            proxy=proxy,
            ssl=False,
        )
        res_status = resp.status
        res_text = await resp.text()

        if res_status == 429:
            raise AccountApiAsyncException("429 Too Many Requests")

        if res_status == 404:
            raise AccountApiAsyncException("请求404")

        try:
            res = json_loads(res_text)
        except JSONDecodeError as e:
            raise AccountApiAsyncException("response not json", e)
        return res

    @property
    def token_headers(self):
        return {
            'Authorization': 'Token %s' % (self.token,)
        }

    async def auth(self):
        res = await self.post(
            action="api2/auth-token/",
            json={
                'username': self.login_name,
                'password': self.password
            })
        self.token = res.get('token')

    async def load_account_info(self):
        res = await self.get(action="api2/account/info/", headers=self.token_headers)
        self.username = res.get('email')

    async def list_workspaces(self):
        return await self.get(
            action="api/v2.1/workspaces/")

    async def add_base(self, name, workspace_id=None):
        owner = None
        if not workspace_id:
            if not self.username:
                await self.load_account_info()  # load username for owner
            owner = self.username
        else:
            list_workspaces = await self.list_workspaces()
            workspace_list = list_workspaces['workspace_list']
            for w in workspace_list:
                if w.get('id') == workspace_id and w.get('group_id'):
                    owner = '%s@seafile_group' % w['group_id']
                    break
                if w.get('id') == workspace_id and w.get('type') == 'personal':
                    if not self.username:
                        await self.load_account_info()  # load username for owner
                    owner = self.username
                    break
        if not owner:
            raise AccountApiAsyncException('workspace_id invalid.')

        res = await self.post(
            action="api/v2.1/dtables/",
            data={
                'name': name,
                'owner': owner
            })
        return res.get('table')

    async def copy_base(self, src_workspace_id, base_name, dst_workspace_id):
        res = await self.post(
            action="api/v2.1/dtable-copy/",
            data={
                'src_workspace_id': src_workspace_id,
                'name': base_name,
                'dst_workspace_id': dst_workspace_id
            })
        return res.get('dtable')

    async def get_temp_api_token(self, workspace_id, base_name):
        res = await self.get(
            action=f"api/v2.1/workspace/{workspace_id}/dtable/{base_name}/temp-api-token/")
        return res.get("api_token")
