import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, test, vi } from 'vitest';
import { Tooltip } from '@comfyshop/ui';
import { DeleteButton } from './delete-button';

afterEach(cleanup);

function setup(onDelete: () => Promise<string>) {
  const onDeleted = vi.fn();
  render(
    <Tooltip.Provider>
      <DeleteButton
        label="删除成品"
        description="将隐藏这份成品。"
        onDelete={onDelete}
        onDeleted={onDeleted}
      />
    </Tooltip.Provider>,
  );
  return { onDeleted, user: userEvent.setup() };
}

test('deleting requires confirmation and cancelling leaves the record alone', async () => {
  const onDelete = vi.fn(() => Promise.resolve('next'));
  const { onDeleted, user } = setup(onDelete);
  await user.click(screen.getByRole('button', { name: '删除成品' }));
  expect(screen.getByRole('alertdialog')).toBeDefined();
  expect(onDelete).not.toHaveBeenCalled();
  await user.click(screen.getByRole('button', { name: '取消' }));
  expect(screen.queryByRole('alertdialog')).toBeNull();
  expect(onDelete).not.toHaveBeenCalled();
  expect(onDeleted).not.toHaveBeenCalled();
});

test('a confirmed delete reports the result once and closes', async () => {
  const onDelete = vi.fn(() => Promise.resolve('next'));
  const { onDeleted, user } = setup(onDelete);
  await user.click(screen.getByRole('button', { name: '删除成品' }));
  await user.click(screen.getByRole('button', { name: '确认删除' }));
  expect(onDelete).toHaveBeenCalledTimes(1);
  expect(onDeleted).toHaveBeenCalledExactlyOnceWith('next');
  expect(screen.queryByRole('alertdialog')).toBeNull();
});

test('a failed delete keeps the confirmation open with the server message', async () => {
  const onDelete = vi.fn(() => Promise.reject(new Error('成品已用于作品，请先删除对应作品')));
  const { onDeleted, user } = setup(onDelete);
  await user.click(screen.getByRole('button', { name: '删除成品' }));
  await user.click(screen.getByRole('button', { name: '确认删除' }));
  expect((await screen.findByRole('alert')).textContent).toBe('成品已用于作品，请先删除对应作品');
  expect(screen.getByRole('alertdialog')).toBeDefined();
  expect(onDeleted).not.toHaveBeenCalled();
});
