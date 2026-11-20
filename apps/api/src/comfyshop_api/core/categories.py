from enum import StrEnum
from typing import Literal


class WorkflowCategory(StrEnum):
    IMAGE = "image"
    IMAGE_TOOL = "image_tool"
    VIDEO = "video"
    VIDEO_TOOL = "video_tool"
    AUDIO = "audio"
    MODEL_3D = "3d"
    VECTOR = "vector"
    LLM = "llm"


WorkflowCategoryFilter = WorkflowCategory | Literal["all", "tool"]
