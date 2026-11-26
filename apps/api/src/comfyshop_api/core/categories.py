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
    NODE_BASICS = "node_basics"
    PRODUCT_ADS = "product_ads"
    CHARACTER_FASHION = "character_fashion"
    BRAND_DESIGN = "brand_design"


WorkflowCategoryFilter = WorkflowCategory | Literal["all"]
