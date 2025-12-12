from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# 预编译正则表达式
_TABLE_ID_PATTERN = re.compile(r"^[-0-9a-zA-Z]{4}$")

# 操作类型到数据键的映射
_OP_TYPE_MAP = {
    "insert_row": "row_data",
    "modify_row": "updated",
    "delete_row": "deleted_row"
}


def path_get(data: Optional[Dict[str, Any]], path: str, default: Any = None) -> Any:
    """安全地获取嵌套字典中的值

    :param data: 字典数据
    :param path: 点分隔的路径，如 "data.options"
    :param default: 默认值
    :return: 找到的值或默认值
    """
    if data is None:
        return default
    for p in path.split("."):
        data = data.get(p)
        if data is None:
            return default
    return data


def _get_row(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """根据操作类型获取行数据"""
    key = _OP_TYPE_MAP.get(data.get("op_type"))
    return data.get(key) if key else None


def _filter_by_id(datas: List[Dict[str, Any]], data_id: str) -> Optional[Dict[str, Any]]:
    """根据 _id 查找数据，找到第一个匹配项即返回"""
    return next((i for i in datas if i.get("_id") == data_id), None)


def _get_option_name(options: List[Dict[str, Any]], option_id: str) -> Optional[str]:
    """根据选项 ID 获取选项名称"""
    res = _filter_by_id(options, option_id)
    return res["name"] if res else None


def _convert_single_select(cell_value: Any, options: Optional[List[Dict[str, Any]]]) -> Any:
    """转换单选字段值"""
    if not cell_value or not options:
        return cell_value
    return _get_option_name(options, cell_value)


def _convert_multiple_select(cell_value: Any, options: Optional[List[Dict[str, Any]]]) -> Any:
    """转换多选字段值"""
    if not cell_value or not options:
        return cell_value
    return [_get_option_name(options, option_id) for option_id in cell_value]


def _convert_date_value(value: Any, date_format: Optional[str]) -> Any:
    """转换日期字段值"""
    if not value:
        return None
    try:
        date_value = datetime.fromisoformat(value)
        if date_format == "YYYY-MM-DD":
            return date_value.strftime("%Y-%m-%d")
        return date_value.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError) as e:
        logger.warning(f"Format date error: {e}")
        return value


def _convert_long_text(value: Any, **_) -> str:
    """转换长文本字段值"""
    return value["text"] if value else ""


# WebSocket 行转换器映射
_WS_CONVERTERS: Dict[str, Callable] = {
    "single-select": lambda value, options, **_: _convert_single_select(value, options),
    "multiple-select": lambda value, options, **_: _convert_multiple_select(value, options),
    "long-text": _convert_long_text,
}


def convert_row(metadata: Dict[str, Any], ws_data: str) -> Dict[str, Any]:
    """Convert websocket row data to readable row data

    :param metadata: dict
    :param ws_data: str
    :return: dict
    """
    data = json.loads(ws_data)
    row = _get_row(data)
    if not row:
        return data

    table = _filter_by_id(metadata["tables"], data["table_id"])
    if not table:
        return data

    column_map = {column["key"]: column for column in table["columns"]}

    result: Dict[str, Any] = {
        "_id": data["row_id"],
        "op_type": data["op_type"],
        "table_name": table["name"],
    }

    for column_key, cell_value in row.items():
        column = column_map.get(column_key)
        if not column:
            continue

        column_type = column["type"]
        options = path_get(column, "data.options")
        converter = _WS_CONVERTERS.get(column_type, lambda value, **_: value)
        result[column["name"]] = converter(value=cell_value, options=options)

    return result


def is_single_multiple_structure(column: Dict[str, Any]) -> Tuple[bool, List[Dict[str, Any]]]:
    """检查列是否为单选/多选结构

    :param column: 列定义
    :return: (是否匹配, 选项列表)
    """
    column_type = column.get("type")

    if column_type in ("single-select", "multiple-select"):
        return True, path_get(column, "data.options", [])

    if column_type in ("link", "link-formula"):
        array_type = path_get(column, "data.array_type")
        if array_type in ("single-select", "multiple-select"):
            return True, path_get(column, "data.array_data.options", [])

    return False, []


def _build_select_map(metadata: List[Dict[str, Any]]) -> Dict[str, Dict[str, str]]:
    """构建选项 ID 到名称的映射表"""
    select_map: Dict[str, Dict[str, str]] = {}
    for column in metadata:
        is_sm, options = is_single_multiple_structure(column)
        if is_sm and options:
            select_map[column["key"]] = {opt["id"]: opt["name"] for opt in options}
    return select_map


def convert_db_rows(
    metadata: List[Dict[str, Any]],
    results: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Convert dtable-db rows data to readable rows data

    :param metadata: list of column definitions
    :param results: list of row data
    :return: list of converted rows
    """
    if not results:
        return []

    column_map = {column["key"]: column for column in metadata}
    select_map = _build_select_map(metadata)

    return [_convert_single_row(row, column_map, select_map) for row in results]


def _convert_link_values(value: List[Dict[str, Any]], s_map: Optional[Dict[str, str]]) -> List[Dict[str, Any]]:
    """转换链接字段值"""
    if not value or not s_map:
        return value or []

    result = []
    for item in value:
        display_value = item.get("display_value")
        if isinstance(display_value, list):
            new_display = [s_map.get(v, v) for v in display_value]
        else:
            new_display = s_map.get(display_value, display_value)
        result.append({**item, "display_value": new_display})
    return result


def _convert_link_formula_values(value: List[Any], s_map: Optional[Dict[str, str]]) -> List[Any]:
    """转换链接公式字段值"""
    if not value or not s_map:
        return value or []

    if isinstance(value[0], list):
        return [[s_map.get(v, v) for v in sub] for sub in value]
    return [s_map.get(v, v) for v in value]


def _convert_single_row(
    result: Dict[str, Any],
    column_map: Dict[str, Dict[str, Any]],
    select_map: Dict[str, Dict[str, str]]
) -> Dict[str, Any]:
    """转换单行数据"""
    item: Dict[str, Any] = {}

    for column_key, value in result.items():
        if column_key not in column_map:
            item[column_key] = value
            continue

        column = column_map[column_key]
        column_name = column["name"]
        column_type = column.get("type")
        s_map = select_map.get(column_key)

        # 根据列类型转换值
        if column_type == "single-select" and value and s_map:
            item[column_name] = s_map.get(value, value)
        elif column_type == "multiple-select" and value and s_map:
            item[column_name] = [s_map.get(v, v) for v in value]
        elif column_type == "link" and value:
            item[column_name] = _convert_link_values(value, s_map)
        elif column_type == "link-formula" and value:
            item[column_name] = _convert_link_formula_values(value, s_map)
        elif column_type == "date":
            item[column_name] = _convert_date_value(value, path_get(column, "data.format"))
        else:
            item[column_name] = value

    return item


def parse_headers(token: str) -> Dict[str, str]:
    """生成带认证信息的请求头"""
    return {
        "Authorization": f"Token {token}",
        "Content-Type": "application/json",
    }


def parse_server_url(server_url: str) -> str:
    """规范化服务器 URL"""
    return server_url.rstrip("/")


def like_table_id(value: str) -> bool:
    """检查值是否为有效的表 ID（4 字符字母数字）"""
    return _TABLE_ID_PATTERN.match(value) is not None
