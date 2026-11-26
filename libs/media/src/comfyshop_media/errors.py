"""媒体操作失败的原因，由调用方决定如何呈现。"""

from typing import Literal


class MediaError(Exception):
    def __init__(
        self,
        kind: Literal["invalid", "missing", "unavailable", "too_large", "range", "range_syntax"],
        message: str,
    ) -> None:
        super().__init__(message)
        self.kind = kind
