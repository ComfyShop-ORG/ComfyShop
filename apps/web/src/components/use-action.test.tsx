import { act, renderHook } from '@testing-library/react';
import { expect, test } from 'vitest';
import { useAction } from './use-action';

test('a failure is shown for the item it happened on and cleared by the next attempt', async () => {
  const { result, rerender } = renderHook(({ scope }) => useAction('操作失败', scope), {
    initialProps: { scope: 'first' },
  });
  await act(() => result.current.run(() => Promise.reject(new Error('成品已用于作品'))));
  expect(result.current.error).toBe('成品已用于作品');
  expect(result.current.busy).toBe(false);
  rerender({ scope: 'second' });
  expect(result.current.error).toBe('');
  rerender({ scope: 'first' });
  expect(result.current.error).toBe('成品已用于作品');
  await act(() => result.current.run(() => Promise.resolve()));
  expect(result.current.error).toBe('');
});

test('a second operation is ignored while one is running', async () => {
  const { result } = renderHook(() => useAction());
  let finish = () => {};
  let started = 0;
  const slow = () =>
    new Promise<void>((resolve) => {
      started += 1;
      finish = resolve;
    });
  let first = Promise.resolve();
  act(() => {
    first = result.current.run(slow);
  });
  expect(result.current.busy).toBe(true);
  await act(() => result.current.run(slow));
  expect(started).toBe(1);
  await act(async () => {
    finish();
    await first;
  });
  expect(result.current.busy).toBe(false);
});
