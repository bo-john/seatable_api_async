import asyncio

from seatable_api_async.seatable_api import SeaTableApiAsync


async def main():
    token = "xxx"
    # seatable服务地址
    server_url = 'http://127.0.0.1:30080/'
    # 代理ip
    proxy = "http://127.0.0.1:9090"

    async with SeaTableApiAsync(
            token=token,
            server_url=server_url,
            proxy=proxy,
    ) as api:
        table_name = "老师表"

        # metadata = await api.get_metadata()
        # print(metadata)
        """
            table相关操作测试
        """
        # list_tables = await api.list_tables()
        # print(list_tables)
        # class_tables = await api.get_table_by_name("班级表")
        # print(class_tables)
        # add_table_res = await api.add_table(table_name="hello2", lang='zh')
        # print(add_table_res)
        # rename_table_res = await api.rename_table(table_name="hello2", new_table_name="world2")
        # print(rename_table_res)
        # del_table_res = await api.delete_table(table_name="world2")
        # print(del_table_res)

        """
           view相关操作测试
        """
        # views = await api.list_views("老师表")
        # print(views)
        # view_name = await api.get_view_by_name("老师表", "男生视图")
        # print(view_name)
        # view_add = await api.add_view("老师表", "女22生视图")
        # print(view_add)
        # view_re = await api.rename_view("老师表", "女22生视图", "女33生视图")
        # print(view_re)
        # view_del = await api.delete_view("老师表", "女33生视图")
        # print(view_del)

        """
           row相关操作测试
        """
        # list_rows = await api.list_rows(table_name=table_name, order_by="年龄", desc=True)
        # print(list_rows)
        # one_row = await api.get_row(table_name=table_name, row_id="SnmUzDdRTKCYFGnmAtSH-A")
        # print(one_row)
        # row_data = {
        #     "名称": "杨老师",
        #     "年龄": 26,
        #     "性别": "女",
        # }
        # add_row = await api.append_row(table_name=table_name, row_data=row_data)
        # print(add_row)
        # rows = [
        #     {
        #         "名称": "宋老师",
        #         "年龄": 23,
        #         "性别": "女",
        #     }, {
        #         "名称": "熊老师",
        #         "年龄": 26,
        #         "性别": "男",
        #     }
        # ]
        # add_row = await api.batch_append_rows(table_name=table_name, rows_data=rows)
        # print(add_row)
        # row_data = {
        #     "名称": "孙老师",
        #     "年龄": 26,
        #     "性别": "男",
        # }
        # anchor_row_id = "a-tD_0fORP6D8T77SnHScQ"
        # insert_row = await api.insert_row(table_name=table_name, row_data=row_data, anchor_row_id=anchor_row_id)
        # print(insert_row)
        # row_id = "a-tD_0fORP6D8T77SnHScQ"
        # row_data = {
        #     "名称": "刘老师",
        #     "年龄": 28,
        #     "性别": "男",
        # }
        # update_row = await api.update_row(table_name, row_id=row_id, row_data=row_data)
        # print(update_row)
        # rows_data = [
        #     {
        #         "row_id": "SC2vU2o5TbGCGQoQkI_t2w",
        #         "row": {
        #             "名称": "周老师",
        #             "年龄": 31,
        #             "性别": "女",
        #         }
        #     }, {
        #         "row_id": "GfYNgvw_S22rHPKHj5NnZQ",
        #         "row": {
        #             "名称": "熊老师",
        #             "年龄": 29,
        #             "性别": "男",
        #         }
        #     }
        # ]
        # batch_update_row = await api.batch_update_rows(table_name=table_name, rows_data=rows_data)
        # print(batch_update_row)
        # row_id = "RXQOAMRUTkmV6m3ByQ0eRA"
        # delete_row = await api.delete_row(table_name=table_name, row_id=row_id)
        # print(delete_row)
        # row_ids = [
        #     "DqggP6i_QmmCI_Sgx7hjcg",
        # ]
        # batch_delete_rows = await api.batch_delete_rows(table_name=table_name, row_ids=row_ids)
        # print(batch_delete_rows)

        """
           column相关操作测试
        """
        # print(await api.list_columns(table_name=table_name))
        # print(await api.get_column_link_id(table_name=table_name, column_name="名称")) # 需要有link才能运行成功
        # print(await api.get_column_by_name(table_name=table_name, column_name="名称"))
        # print(await api.get_columns_by_type(table_name=table_name, column_type=ColumnTypes.TEXT))
        # print(await api.insert_column(table_name=table_name, column_name="爱好2", column_type=ColumnTypes.TEXT))
        # print(await api.rename_column(table_name=table_name, column_key="爱好2", new_column_name="癖好"))
        # print(await api.resize_column(table_name=table_name, column_key="癖好", new_column_width=80))
        # print(await api.freeze_column(table_name=table_name, column_key="名称", frozen=True))
        # print(await api.move_column(table_name=table_name, column_key="年龄", target_column_key="名称"))
        # print(await api.modify_column_type(table_name=table_name, column_key="年龄", new_column_type=ColumnTypes.NUMBER))
        # options = [
        #     {"name": "a", "color": "#aaa", "textColor": "#000000"},
        #     {"name": "b", "color": "#aaa", "textColor": "#000000"},
        #     {"name": "c", "color": "#aaa", "textColor": "#000000"},
        # ]
        # print(await api.add_column_options(table_name=table_name, column="爱好", options=options))
        # print(await api.delete_column(table_name=table_name, column_key="癖好"))

        """
           file相关操作测试
        """
        # file_url = "http://192.168.150.145:30080/workspace/46/asset/b6721580-4f5b-4a92-b386-1078f4d77a36/files/2025-11/recall.txt"
        # save_path = "/Users/xiongbo/workspace/seatable-api-plus/tests/recall3.txt"
        # await api.download_file(url=file_url, save_path=save_path)

        # local_file_path = "/Users/xiongbo/workspace/seatable-api-plus/pyproject.toml"
        # with open(local_file_path,'rb') as f:
        #     content = f.read()
        #
        # print(await api.upload_bytes_file(name="py.toml", content=content, file_type='file', replace=False))

        # file_path = "/Users/xiongbo/workspace/seatable-api-plus/tests/seatable_api_test.py"
        # file_name = "recall_upload.txt"
        # file_type = "file"
        # print(await api.upload_local_file(file_path=file_path, name=file_name, file_type=file_type))

        # 下载自定义文件夹下的文件
        # file_url = "/hello.txt"
        # save_path = "./hello_upload.txt"
        # await api.download_custom_file(path=file_url, save_path=save_path)

        # 上传文件到seatable云端自定义文件夹
        # local_path = "/Users/xiongbo/workspace/seatable-api-plus/tests/origin_account_test.py"
        # custom_folder_path = "/"
        # name = "recall-upload.txt"
        # print(await api.upload_local_file_to_custom_folder(local_path=local_path,
        #                                                    custom_folder_path=custom_folder_path,
        #                                                    name=name))

        # path = "/"
        # print(await api.list_custom_assets(path=path))

        """
          query相关操作测试
        """
        # print(await api.query(sql="select * from 老师表"))

        # queryset: QuerySet = await api.filter(table_name=table_name, conditions="年龄 > 19 and 名称='周老师'")
        # print(queryset.rows)

        # print(await api.get_related_users())

        # print(await api.big_data_insert_rows(table_name=table_name, rows_data=rows))

        # print(await api.get_user_info(username="熊波"))


print("seatable_api_test")

if __name__ == "__main__":
    asyncio.run(main())
