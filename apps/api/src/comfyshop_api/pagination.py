"""把列表最后一行的排序值编码成游标，下一页从这些值继续查询。"""

import base64
import json
from collections.abc import Callable, Sequence
from uuid import UUID

from fastapi import HTTPException

from comfyshop_api.core.i18n import msg


def encode_cursor(*values: int | str) -> str:
    return (
        base64.urlsafe_b64encode(json.dumps(values, separators=(",", ":")).encode())
        .decode()
        .rstrip("=")
    )


def split_page[T](
    records: Sequence[T], limit: int, position: Callable[[T], tuple[int | str, ...]]
) -> tuple[Sequence[T], str | None]:
    """把多取一行的查询结果分成本页和下一页游标。

    查询须按 `limit + 1` 读取。`position` 返回一行的排序值，仅在还有下一页时
    对本页最后一行调用。
    """
    if len(records) <= limit:
        return records, None
    return records[:limit], encode_cursor(*position(records[limit - 1]))


def decode_cursor(value: str | None, size: int) -> list | None:
    """解析 `size` 个排序值，末尾为 UUID，其余为非负整数。

    `value` 省略时返回 `None`，表示第一页。格式错误返回 HTTP 422。
    游标只定位分页位置，访问权限由各列表查询校验。
    """
    if value is None:
        return None
    try:
        result = json.loads(
            base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
        )
        if not isinstance(result, list) or len(result) != size:
            raise ValueError
        if not all(type(item) is int and 0 <= item <= 2**63 - 1 for item in result[:-1]):
            raise ValueError
        UUID(result[-1])
        return result
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(422, msg("pagination.invalidPaginationCursor")) from None
