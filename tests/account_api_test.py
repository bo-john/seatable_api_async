import asyncio

from seatable_api_async.account_api import AccountApiAsync


async def main():
    # 用户名
    login_name = 'xxx'
    # 密码
    password = ''
    # seatable服务地址
    server_url = 'http://127.0.0.1:30080/'

    async with AccountApiAsync(
            login_name=login_name,
            password=password,
            server_url=server_url,
    ) as api:
        # await api.auth()
        workspace_id = 1

        # print(await api.load_account_info())

        print(await api.list_workspaces())

        # name = "hello-table"
        # print(await api.add_base(name=name, workspace_id=workspace_id))

        # src_workspace_id = 46
        # dst_workspace_id = 46
        # base_name = "hello-table"
        # print(await api.copy_base(src_workspace_id=src_workspace_id, base_name=base_name, dst_workspace_id=dst_workspace_id))

        # base_name = "调试表格"
        # print(await api.get_temp_api_token(workspace_id=workspace_id, base_name=base_name))


if __name__ == "__main__":
    asyncio.run(main())
