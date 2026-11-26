/** 从一次执行发布作品的选择流程：单份成品直接进入发布，多份先选择再确认。 */
import { useState } from 'react';
import type { Artifact } from '@comfyshop/api-client';

/**
 * @param executionId 当前查看的执行。发布成功的提示只对完成发布的那次执行显示。
 * @param items 这次执行已加载的成品。
 * @param single 执行只有一份成品时传入它，发布时跳过选择。
 * @param focusGallery 进入选择后把焦点移到成品列表。
 * @param focusAction 取消选择后把焦点移回发布入口。
 */
export function useWorkPublication(
  executionId: string,
  items: Artifact[],
  single: Artifact | null,
  focusGallery: () => void,
  focusAction: () => void,
) {
  const [selecting, setSelecting] = useState(false);
  const [chosen, setChosen] = useState<Set<string>>(() => new Set());
  const [draft, setDraft] = useState<Artifact[] | null>(null);
  const [publishedExecutionId, setPublishedExecutionId] = useState<string>();
  const chosenAssets = selecting ? items.filter((asset) => chosen.has(asset.id)) : [];
  const begin = () => {
    setPublishedExecutionId(undefined);
    if (single) setDraft([single]);
    else {
      setSelecting(true);
      requestAnimationFrame(focusGallery);
    }
  };
  const toggle = (asset: Artifact) =>
    setChosen((prior) => {
      const next = new Set(prior);
      if (next.has(asset.id)) next.delete(asset.id);
      else next.add(asset.id);
      return next;
    });
  const cancelSelection = () => {
    setSelecting(false);
    setChosen(new Set());
    focusAction();
  };
  /** 带着已选成品进入发布弹框。 */
  const review = () => setDraft(chosenAssets);
  /** 关闭发布弹框，保留选择以便返回修改。 */
  const closeDraft = () => setDraft(null);
  const completed = () => {
    setDraft(null);
    setSelecting(false);
    setChosen(new Set());
    setPublishedExecutionId(executionId);
  };
  return {
    selecting,
    chosen,
    chosenAssets,
    draft,
    published: publishedExecutionId === executionId,
    begin,
    toggle,
    cancelSelection,
    review,
    closeDraft,
    completed,
  };
}
