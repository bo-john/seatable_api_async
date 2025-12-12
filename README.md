# SeaTable API Async

[![PyPI version](https://img.shields.io/pypi/v/seatable-api-async.svg)](https://pypi.org/project/seatable-api-async/)
[![Python](https://img.shields.io/pypi/pyversions/seatable-api-async.svg)](https://pypi.org/project/seatable-api-async/)
[![License](https://img.shields.io/github/license/bo-john/seatable_api_async.svg)](https://github.com/bo-john/seatable_api_async/blob/main/LICENSE)

异步版本的 SeaTable API Python 客户端库，基于 [seatable-api-python](https://github.com/seatable/seatable-api-python) 改造，使用 `aiohttp` 和 `async/await` 实现完全异步操作。

## 特性

- **完全异步** - 基于 `aiohttp` 和 `async/await`，支持高并发操作
- **WebSocket 支持** - 内置 SocketIO 客户端，支持实时事件推送
- **自动 Token 管理** - JWT token 自动刷新，无需手动干预
- **批量操作** - 支持批量增删改，提高数据处理效率
- **完整功能** - 覆盖表、行、列、视图、链接、评论、文件上传等所有核心 API

## 安装

```bash
# 使用 pip
pip install seatable-api-async

# 使用 uv
uv add seatable-api-async
```

## 快速开始

### AccountApi 操作

```python
import asyncio
from seatable_api_async import AccountApiAsync

async def main():
    async with AccountApiAsync(
        login_name="your_email@example.com",
        password="your_password",
        server_url="https://cloud.seatable.io"
    ) as account:
        # 列出工作区
        workspaces = await account.list_workspaces()

        # 获取 Base API Token
        token = await account.get_temp_api_token(
            workspace_id=1,
            dtable_name="My Base"
        )

if __name__ == "__main__":
    asyncio.run(main())
```

### SeatableApi 操作

```python
from seatable_api_async import SeaTableApiAsync

async def main():
    async with SeaTableApiAsync(
        token="your_api_token",
        server_url="https://cloud.seatable.io"
    ) as base:
        # 列出行
        rows = await base.list_rows("Table1")

        # 添加行
        await base.append_row("Table1", {"Name": "Alice", "Age": 30})

        # 批量添加
        await base.batch_append_rows("Table1", [
            {"Name": "Bob", "Age": 25},
            {"Name": "Charlie", "Age": 35}
        ])

        # SQL 查询
        results = await base.query("SELECT * FROM Table1 WHERE Age > 25")

if __name__ == "__main__":
    asyncio.run(main())
```

### WebSocket 实时通讯

```python
from seatable_api_async import SeaTableApiAsync, SocketIOAsync

async def main():
    async with SeaTableApiAsync(token, server_url) as base:
        # 使用 async with 自动管理连接
        async with SocketIOAsync(base) as socket:
            @socket.on("custom_event")
            async def handle_event(data):
                print(f"Received: {data}")

            await socket.emit("my_event", {"data": "hello"})
            # 退出时自动断开连接

if __name__ == "__main__":
    asyncio.run(main())
```

## API 文档

详细的 API 方法请参考同步版本 [seatable-api](https://github.com/seatable/seatable-api-python) 文档，所有方法名称保持一致，只需添加 `await` 关键字。

主要模块：
- `AccountApiAsync` - 账户管理、工作区操作
- `SeaTableApiAsync` - Base 操作、表/行/列/视图管理、SQL 查询
- `SocketIOAsync` - WebSocket 实时通讯

## 开发建议

### 使用异步上下文管理器

```python
async with SeaTableApiAsync(token, server_url) as api:
    rows = await api.list_rows("Table1")
# 会话自动关闭
```

### 批量操作优先

```python
# 推荐 - 使用批量操作
await api.batch_append_rows("Table1", rows)

# 避免 - 循环单个操作
for row in rows:
    await api.append_row("Table1", row)  # 性能较差
```

## 测试

```bash
# 配置环境变量
cp .env_template .env

# 运行测试
pytest tests/
```

## 贡献

欢迎贡献代码！请 Fork 本仓库，创建特性分支，提交 Pull Request。

## 许可证

本项目基于 Apache License 2.0 开源协议。

## 链接

- [PyPI](https://pypi.org/project/seatable-api-async/)
- [GitHub](https://github.com/bo-john/seatable_api_async)
- [SeaTable 官方文档](https://seatable.io/docs/)
- [SeaTable API Python (同步版本)](https://github.com/seatable/seatable-api-python)

## 致谢

本项目基于 [seatable-api](https://github.com/seatable/seatable-api-python) 改造，感谢 SeaTable 团队的优秀工作。