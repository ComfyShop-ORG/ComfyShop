import type { Workflow } from '@comfyshop/api-client';

export const workflowCategories = [
  { value: 'image', label: '图像' },
  { value: 'image_tool', label: '图像工具' },
  { value: 'video', label: '视频' },
  { value: 'video_tool', label: '视频工具' },
  { value: 'audio', label: '音频' },
  { value: '3d', label: '3D模型' },
  { value: 'vector', label: '矢量' },
  { value: 'llm', label: 'LLM' },
] as const satisfies readonly { value: Workflow['category']; label: string }[];

export const workflowCategoryFilters = [
  { value: 'all', label: '全部' },
  ...workflowCategories,
] as const;
