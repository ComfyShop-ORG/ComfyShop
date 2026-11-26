import { useState } from 'react';
import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, test, vi } from 'vitest';
import { Dialog, DialogContent, Tooltip } from '@comfyshop/ui';
import { DeleteButton } from './delete-button';
import { NotificationLayer } from './notification';
import { Notify } from './notify';
import type { NoticeAction } from './notify';

afterEach(() => {
  cleanup();
  document.documentElement.removeAttribute('data-pointer-focus');
});

test.each(['keyboard', 'pointer'] as const)(
  '%s deletion focuses undo in the surviving dialog',
  async (input) => {
    const undo = vi.fn();
    const user = userEvent.setup();
    function Results() {
      const [resultOpen, setResultOpen] = useState(true);
      const [notice, setNotice] = useState<{ text: string; action?: NoticeAction }>();
      return (
        <Tooltip.Provider>
          <Notify.Provider value={(text, action) => setNotice({ text, action })}>
            <Dialog.Root open>
              <DialogContent>
                <Dialog.Title>工作流详情</Dialog.Title>
                <Dialog.Root open={resultOpen}>
                  <DialogContent>
                    <Dialog.Title>执行结果</Dialog.Title>
                    <DeleteButton
                      label="删除成品"
                      done="已删除成品"
                      description="将隐藏这份成品。"
                      onDelete={() => Promise.resolve()}
                      onDeleted={() => setResultOpen(false)}
                      undo={() => ({ label: '撤销', run: undo })}
                    />
                  </DialogContent>
                </Dialog.Root>
              </DialogContent>
            </Dialog.Root>
            <NotificationLayer
              id={1}
              open={!!notice}
              text={notice?.text ?? ''}
              action={notice?.action}
              placement="top"
              onAction={(run) => void run()}
              onClose={() => setNotice(undefined)}
            />
          </Notify.Provider>
        </Tooltip.Provider>
      );
    }
    render(<Results />);
    const status = screen.getByRole('status');
    expect(status.parentElement).toBe(document.body);
    expect(status.textContent).toBe('');
    expect(screen.queryByRole('dialog', { name: '工作流详情' })).toBeNull();
    const remove = screen.getByRole('button', { name: '删除成品' });
    if (input === 'pointer') {
      document.documentElement.setAttribute('data-pointer-focus', '');
      await user.click(remove);
      await user.click(screen.getByRole('button', { name: '确认删除' }));
    } else {
      remove.focus();
      await user.keyboard('{Enter}');
      screen.getByRole('button', { name: '确认删除' }).focus();
      await user.keyboard('{Enter}');
    }

    const dialog = await screen.findByRole('dialog', { name: '工作流详情' });
    const action = await within(dialog).findByRole('button', {
      name: '撤销',
      description: '已删除成品',
    });
    expect(screen.getByRole('status')).toBe(status);
    await waitFor(() => expect(status.textContent).toContain('已删除成品'));
    await waitFor(() => expect(document.activeElement).toBe(action));
    await user.keyboard('{Enter}');

    expect(undo).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole('button', { name: '撤销' })).toBeNull();
    expect(document.activeElement).toBe(dialog);
    expect(status.textContent).toBe('');
  },
);

test('consecutive notices with the same text update the same live region', async () => {
  const notice = (id: number) => (
    <Tooltip.Provider>
      <NotificationLayer
        id={id}
        open
        text="已保存"
        placement="bottom"
        onAction={() => {}}
        onClose={() => {}}
      />
    </Tooltip.Provider>
  );
  const { rerender } = render(notice(1));
  const status = screen.getByRole('status');
  await waitFor(() => expect(status.textContent).toBe('通知 已保存'));
  rerender(notice(2));
  expect(screen.getByRole('status')).toBe(status);
  expect(status.textContent).toBe('');
  await waitFor(() => expect(status.textContent).toBe('通知 已保存'));
});

test('the notification shortcut and tab order reach an action on the page', async () => {
  const undo = vi.fn();
  const user = userEvent.setup();
  render(
    <Tooltip.Provider>
      <NotificationLayer
        id={1}
        open
        text="已删除成品"
        action={{ label: '撤销', run: undo }}
        placement="bottom"
        onAction={(run) => void run()}
        onClose={() => {}}
      />
    </Tooltip.Provider>,
  );
  const region = await screen.findByRole('region', { name: '通知（F8）' });
  const action = await within(region).findByRole('button', { name: '撤销' });
  await user.keyboard('{F8}');
  await user.tab();
  if (document.activeElement !== action) await user.tab();
  expect(document.activeElement).toBe(action);
  await user.keyboard(' ');
  expect(undo).toHaveBeenCalledTimes(1);
});
