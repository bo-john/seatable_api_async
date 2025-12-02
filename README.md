# seatable_api_async

#### 介绍
基于seatable-api改造, 将核心功能由同步改成异步,并开源.


#### 安装
seatable_api_async已上传到PyPI仓库(Python官方软件包仓库).
使用pip安装
```
pip install seatable_api_async
# 有的是pip3
pip3 install seatable_api_async
```

如果使用了uv项目包管理器
```
uv add seatable_api_async
```
以上即可安装seatable_api_async包并使用了.


#### 使用

api方法均可参考seatable_api官方文档,部分函数略有进行简化处理.

使用参考示例:
```Python
import asyncio
import os
from dotenv import load_dotenv
from seatable_api_async.account_api import AccountApiAsync

async def main():
    # 读取环境变量文件 .env
    # 没有则从.env_template拷贝生成一个 .env文件
    load_dotenv()

    # 用户名
    login_name = os.getenv('LOGIN_NAME')
    # 密码
    password = os.getenv('PASSWORD')
    # seatable服务地址
    server_url = os.getenv('SERVER_URL')

    async with AccountApiAsync(
            login_name=login_name,
            password=password,
            server_url=server_url,
    ) as api:
        print(await api.list_workspaces())

if __name__ == "__main__":
    asyncio.run(main())

```



#### 参与贡献

1.  Fork 本仓库
2.  新建 Feat_xxx 分支
3.  提交代码
4.  新建 Pull Request


#### 备注说明
此仓库基于seatable-api官方仓库改造而来,基于Apache Licence开源协议.

seatable-api的官方github仓库:https://github.com/seatable/seatable-api-python/tree/master