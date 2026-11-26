import { t } from '../app/i18n.ts';
import { workflowCategoryValues } from '@comfyshop/api-client';
import type { Workflow } from '@comfyshop/api-client';

const categoryLabels = {
  image: t('workflowCategories.image'),
  image_tool: t('workflowCategories.imageTools'),
  video: t('mediaCards.video'),
  video_tool: t('workflowCategories.videoTools'),
  audio: t('mediaCards.audio'),
  '3d': t('workflowCategories.dModels'),
  vector: t('workflowCategories.vector'),
  llm: 'LLM',
  node_basics: t('workflowCategories.nodeBasics'),
  product_ads: t('workflowCategories.productsAndAds'),
  character_fashion: t('workflowCategories.charactersAndFashion'),
  brand_design: t('workflowCategories.brandAndDesign'),
} satisfies Record<Workflow['category'], string>;

export const workflowCategories = workflowCategoryValues.map((value) => ({
  value,
  label: categoryLabels[value],
}));

export const workflowCategoryFilters = [
  { value: 'all', label: t('taskList.all') },
  ...workflowCategories,
] as const;

export const workflowCategoryMenu = [
  { value: 'all', label: t('catalogPage.allCategories') },
  ...workflowCategories,
] as const;
