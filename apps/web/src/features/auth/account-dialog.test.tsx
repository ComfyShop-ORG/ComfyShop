import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, test, vi } from 'vitest';
import { createApiClient } from '@comfyshop/api-client';
import { Tooltip } from '@comfyshop/ui';
import { WorkspaceContext } from '../../app/use-workspace';
import { AccountDialog } from './account-dialog';

afterEach(cleanup);

// jsdom 没有 ResizeObserver，勾选框和标签动效在测量尺寸时需要它。
globalThis.ResizeObserver ??= class {
  observe() {}
  unobserve() {}
  disconnect() {}
};

const session = {
  user: { id: 'user-1', username: 'owner', email: 'owner@example.com' },
  csrfToken: 'csrf',
};

/** 打开账号设置。会话接口返回已登录用户，其他请求返回空数据。 */
function setup() {
  const fetcher: typeof fetch = (input) => {
    const path = new URL(input instanceof Request ? input.url : input, 'http://platform.test')
      .pathname;
    if (path === '/api/v1/auth/session') return Promise.resolve(Response.json(session));
    return Promise.resolve(Response.json({ favoriteIds: [] }));
  };
  const restoreFocus = vi.fn();
  const queries = new QueryClient();
  // 应用里只有登录后才渲染账号设置，会话已经读到。
  queries.setQueryData(['session'], session);
  const view = (open: boolean) => (
    <QueryClientProvider client={queries}>
      <WorkspaceContext.Provider value={createApiClient('', fetcher)}>
        <Tooltip.Provider>
          <AccountDialog
            open={open}
            onOpenChange={() => {}}
            onDeleted={() => {}}
            restoreFocus={restoreFocus}
          />
        </Tooltip.Provider>
      </WorkspaceContext.Provider>
    </QueryClientProvider>
  );
  const rendered = render(view(true));
  return {
    restoreFocus,
    user: userEvent.setup(),
    reopen: () => {
      rendered.rerender(view(false));
      rendered.rerender(view(true));
    },
  };
}

test('reopening starts fresh on the first tab and returns focus on close', async () => {
  const { restoreFocus, user, reopen } = setup();
  // 当前绑定的邮箱单独显示，新邮箱输入框从空开始。
  expect(screen.getAllByText('owner@example.com').length).toBeGreaterThan(0);
  await user.type(screen.getByLabelText('新邮箱'), 'unsaved@example.com');
  await user.click(screen.getByRole('tab', { name: '注销账号' }));
  expect(screen.getByRole('tab', { name: '注销账号' }).getAttribute('data-state')).toBe('active');
  reopen();
  await vi.waitFor(() => expect(restoreFocus).toHaveBeenCalled());
  expect(screen.getByRole('tab', { name: '更换邮箱' }).getAttribute('data-state')).toBe('active');
  expect(screen.getByLabelText('新邮箱')).toHaveProperty('value', '');
});

test('entering the bound email again is refused before any mail is sent', async () => {
  const { user } = setup();
  await user.type(screen.getByLabelText('新邮箱'), 'OWNER@example.com');
  await user.type(screen.getByLabelText('当前密码'), 'correct-horse-battery');
  await user.click(screen.getByRole('button', { name: '发送确认邮件' }));
  expect(screen.getByRole('alert').textContent).toBe('这已经是当前绑定的邮箱。');
});
