import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { afterEach, expect, test, vi } from 'vitest';
import { createApiClient } from '@comfyshop/api-client';
import { Tooltip } from '@comfyshop/ui';
import { WorkspaceContext } from '../../app/use-workspace';
import { LoginDialog } from './login-dialog';

afterEach(cleanup);

type Reply = { status: number; body: unknown };

/** 渲染登录弹框并记录它向平台发出的认证请求。`reply` 决定登录或注册接口的响应。 */
function setup(reply: Reply) {
  const requests: Array<{ path: string; body: unknown }> = [];
  const fetcher: typeof fetch = (input, init) => {
    const path = new URL(input instanceof Request ? input.url : input, 'http://platform.test')
      .pathname;
    if (path === '/api/v1/auth/session')
      return Promise.resolve(Response.json({ user: null, csrfToken: null }));
    requests.push({ path, body: JSON.parse(init?.body as string) as unknown });
    return Promise.resolve(Response.json(reply.body, { status: reply.status }));
  };
  const onSuccess = vi.fn();
  render(
    <QueryClientProvider client={new QueryClient()}>
      <WorkspaceContext.Provider value={createApiClient('', fetcher)}>
        <Tooltip.Provider>
          <MemoryRouter>
            <LoginDialog
              open
              onOpenChange={() => {}}
              onSuccess={onSuccess}
              restoreFocus={() => {}}
            />
          </MemoryRouter>
        </Tooltip.Provider>
      </WorkspaceContext.Provider>
    </QueryClientProvider>,
  );
  return { requests, onSuccess, user: userEvent.setup() };
}

const signedIn = {
  status: 200,
  body: { user: { id: 'user-1', username: 'owner' }, csrfToken: 'csrf' },
};

test('invalid credentials are explained locally and never reach the platform', async () => {
  const { requests, onSuccess, user } = setup(signedIn);
  await user.type(screen.getByLabelText('账号'), 'owner');
  await user.type(screen.getByLabelText('密码'), 'short');
  await user.click(screen.getByRole('button', { name: '登录' }));
  expect(screen.getByRole('alert').textContent).toBe('密码需为 8–128 位。');
  expect(screen.getByLabelText('密码').getAttribute('aria-invalid')).toBe('true');
  expect(requests).toEqual([]);
  expect(onSuccess).not.toHaveBeenCalled();
});

test('a valid login submits the normalized account and reports success', async () => {
  const { requests, onSuccess, user } = setup(signedIn);
  await user.type(screen.getByLabelText('账号'), '  ｏwner ');
  await user.type(screen.getByLabelText('密码'), 'correct-horse');
  await user.click(screen.getByRole('button', { name: '登录' }));
  await vi.waitFor(() => expect(onSuccess).toHaveBeenCalledTimes(1));
  expect(requests).toEqual([
    { path: '/api/v1/auth/login', body: { username: 'owner', password: 'correct-horse' } },
  ]);
});

test('a rejected login shows the platform message and stays open', async () => {
  const { onSuccess, user } = setup({ status: 401, body: { detail: '账号或密码错误' } });
  await user.type(screen.getByLabelText('账号'), 'owner');
  await user.type(screen.getByLabelText('密码'), 'wrong-password');
  await user.click(screen.getByRole('button', { name: '登录' }));
  expect((await screen.findByRole('alert')).textContent).toBe('账号或密码错误');
  expect(screen.getByRole('dialog')).toBeDefined();
  expect(onSuccess).not.toHaveBeenCalled();
});

test('registering a taken account marks the account field', async () => {
  const { requests, user } = setup({ status: 409, body: { detail: '账号已存在' } });
  await user.click(screen.getByRole('button', { name: '注册账号' }));
  await user.type(screen.getByLabelText(/^账号/), 'owner');
  await user.type(screen.getByLabelText(/^密码/), 'correct-horse');
  await user.type(screen.getByLabelText('确认密码'), 'correct-horsf');
  await user.click(screen.getByRole('button', { name: '注册' }));
  expect((await screen.findByRole('alert')).textContent).toBe('两次输入的密码不一致。');
  expect(requests).toHaveLength(0);
  await user.clear(screen.getByLabelText('确认密码'));
  await user.type(screen.getByLabelText('确认密码'), 'correct-horse');
  await user.click(screen.getByRole('button', { name: '注册' }));
  expect((await screen.findByRole('alert')).textContent).toBe('账号已存在');
  expect(screen.getByLabelText(/^账号/).getAttribute('aria-invalid')).toBe('true');
  expect(requests[0].path).toBe('/api/v1/auth/register');
});

test('a forgotten password is recovered without leaving the dialog', async () => {
  const { requests, user } = setup({ status: 200, body: {} });
  await user.click(screen.getByRole('button', { name: '忘记密码' }));
  expect(screen.getByRole('heading', { name: '找回密码' })).toBeDefined();
  await user.type(screen.getByLabelText('绑定的邮箱'), 'not-an-email');
  await user.click(screen.getByRole('button', { name: '发送链接' }));
  expect(screen.getByRole('alert').textContent).toBe('请输入有效的邮箱。');
  expect(requests).toEqual([]);
  await user.clear(screen.getByLabelText('绑定的邮箱'));
  await user.type(screen.getByLabelText('绑定的邮箱'), 'owner@example.com');
  await user.click(screen.getByRole('button', { name: '发送链接' }));
  expect(await screen.findByRole('heading', { name: '查收邮件' })).toBeDefined();
  expect(screen.getByRole('status').textContent).toContain('owner@example.com');
  expect(requests).toEqual([
    { path: '/api/v1/auth/password-reset', body: { email: 'owner@example.com' } },
  ]);
  await user.click(screen.getByRole('button', { name: '去登录' }));
  expect(screen.getByRole('heading', { name: '登录' })).toBeDefined();
});

test('a dialog closed by navigation opens at sign-in again', async () => {
  const fetcher: typeof fetch = () =>
    Promise.resolve(Response.json({ user: null, csrfToken: null }));
  const view = (open: boolean) => (
    <QueryClientProvider client={new QueryClient()}>
      <WorkspaceContext.Provider value={createApiClient('', fetcher)}>
        <Tooltip.Provider>
          <MemoryRouter>
            <LoginDialog open={open} onOpenChange={() => {}} restoreFocus={() => {}} />
          </MemoryRouter>
        </Tooltip.Provider>
      </WorkspaceContext.Provider>
    </QueryClientProvider>
  );
  const { rerender } = render(view(true));
  await userEvent.setup().click(screen.getByRole('button', { name: '忘记密码' }));
  expect(screen.getByRole('heading', { name: '找回密码' })).toBeTruthy();
  // 导航直接关掉弹框，不经过 onOpenChange。
  rerender(view(false));
  rerender(view(true));
  expect(screen.getByRole('heading', { name: '登录' })).toBeTruthy();
});
