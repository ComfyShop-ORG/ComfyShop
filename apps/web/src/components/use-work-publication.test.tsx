import { act, renderHook } from '@testing-library/react';
import { expect, test, vi } from 'vitest';
import type { Artifact } from '@comfyshop/api-client';
import { useWorkPublication } from './use-work-publication';

const artifact = (id: string) => ({ id }) as Artifact;
const items = [artifact('a'), artifact('b'), artifact('c')];

function setup(single: Artifact | null, list = items) {
  const focusAction = vi.fn();
  const hook = renderHook(
    ({ executionId }) => useWorkPublication(executionId, list, single, () => {}, focusAction),
    { initialProps: { executionId: 'execution-1' } },
  );
  return { ...hook, focusAction };
}

test('a single artifact goes straight to the publish dialog', () => {
  const { result } = setup(items[0], [items[0]]);
  act(() => result.current.begin());
  expect(result.current.selecting).toBe(false);
  expect(result.current.draft).toEqual([items[0]]);
});

test('several artifacts are chosen first and published in gallery order', () => {
  const { result } = setup(null);
  act(() => result.current.begin());
  expect(result.current.selecting).toBe(true);
  expect(result.current.draft).toBeNull();
  act(() => result.current.toggle(items[2]));
  act(() => result.current.toggle(items[0]));
  act(() => result.current.toggle(items[1]));
  act(() => result.current.toggle(items[1]));
  expect(result.current.chosenAssets.map((asset) => asset.id)).toEqual(['a', 'c']);
  act(() => result.current.review());
  expect(result.current.draft?.map((asset) => asset.id)).toEqual(['a', 'c']);
});

test('closing the publish dialog keeps the selection; cancelling clears it', () => {
  const { result, focusAction } = setup(null);
  act(() => result.current.begin());
  act(() => result.current.toggle(items[0]));
  act(() => result.current.review());
  act(() => result.current.closeDraft());
  expect(result.current.selecting).toBe(true);
  expect(result.current.chosenAssets).toEqual([items[0]]);
  act(() => result.current.cancelSelection());
  expect(result.current.selecting).toBe(false);
  expect(result.current.chosenAssets).toEqual([]);
  expect(focusAction).toHaveBeenCalledTimes(1);
});

test('the published notice belongs to one execution and clears on the next attempt', () => {
  const { result, rerender } = setup(null);
  act(() => result.current.begin());
  act(() => result.current.toggle(items[0]));
  act(() => result.current.review());
  act(() => result.current.completed());
  expect(result.current.published).toBe(true);
  expect(result.current.selecting).toBe(false);
  expect(result.current.draft).toBeNull();
  rerender({ executionId: 'execution-2' });
  expect(result.current.published).toBe(false);
  rerender({ executionId: 'execution-1' });
  expect(result.current.published).toBe(true);
  act(() => result.current.begin());
  expect(result.current.published).toBe(false);
});
