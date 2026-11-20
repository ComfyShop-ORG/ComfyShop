import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, test, vi } from 'vitest';
import { createApiClient } from '@comfyshop/api-client';
import type { AuthSession } from '@comfyshop/api-client';
import { Tooltip } from '@comfyshop/ui';
import { WorkspaceContext } from '../../app/use-workspace';
import { AccountDialog } from './account-dialog';
import type { AccountSection } from './account-dialog';

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

// jsdom 没有 ResizeObserver，勾选框和标签动效在测量尺寸时需要它。
globalThis.ResizeObserver ??= class {
  observe() {}
  unobserve() {}
  disconnect() {}
};

const initialUser: NonNullable<AuthSession['user']> = {
  id: 'user-1',
  username: 'owner',
  email: 'owner@example.com',
  pendingEmail: null,
  nickname: null,
  avatarUrl: null,
};

/** 打开账号设置。会话接口返回已登录用户，其他请求返回空数据。 */
function setup(section: AccountSection = 'profile') {
  let profile = initialUser;
  const avatarWrites = vi.fn();
  const avatarUrl = '/api/v1/authors/user-1/avatar/current';
  const fetcher: typeof fetch = (input, init) => {
    const path = new URL(input instanceof Request ? input.url : input, 'http://platform.test')
      .pathname;
    if (path === '/api/v1/auth/session') {
      return Promise.resolve(Response.json({ user: profile, csrfToken: 'csrf' }));
    }
    if (path === '/api/v1/auth/profile' && typeof init?.body === 'string') {
      const { nickname } = JSON.parse(init.body) as { nickname: string | null };
      profile = { ...profile, nickname };
      return Promise.resolve(Response.json(profile));
    }
    if (path === '/api/v1/auth/profile/avatar') {
      avatarWrites(init?.method, init?.body);
      profile = { ...profile, avatarUrl: init?.method === 'DELETE' ? null : avatarUrl };
      return Promise.resolve(Response.json(profile));
    }
    return Promise.resolve(Response.json({ favoriteIds: [] }));
  };
  const restoreFocus = vi.fn();
  const queries = new QueryClient();
  // 应用里只有登录后才渲染账号设置，会话已经读到。
  queries.setQueryData(['session'], { user: profile, csrfToken: 'csrf' });
  const view = (open: boolean) => (
    <QueryClientProvider client={queries}>
      <WorkspaceContext.Provider value={createApiClient('', fetcher)}>
        <Tooltip.Provider>
          <AccountDialog
            section={section}
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
    avatarUrl,
    avatarWrites,
    queries,
    restoreFocus,
    user: userEvent.setup(),
    reopen: () => {
      rendered.rerender(view(false));
      rendered.rerender(view(true));
    },
  };
}

test('the profile dialog reopens with saved fields and restores focus on close', async () => {
  const { restoreFocus, user, reopen } = setup();
  expect(screen.getByRole('dialog', { name: '个人资料' })).toBeDefined();
  await user.type(screen.getByLabelText('昵称'), '未保存的昵称');
  reopen();
  await vi.waitFor(() => expect(restoreFocus).toHaveBeenCalled());
  expect(screen.getByLabelText('昵称')).toHaveProperty('value', '');
});

test('entering the bound email again is refused before any mail is sent', async () => {
  const { user } = setup('settings');
  await user.click(screen.getByRole('tab', { name: '更换邮箱' }));
  await user.type(screen.getByLabelText('新邮箱'), 'OWNER@example.com');
  await user.type(screen.getByLabelText('当前密码'), 'correct-horse-battery');
  await user.click(screen.getByRole('button', { name: '发送确认邮件' }));
  expect(screen.getByRole('alert').textContent).toBe('这已经是当前绑定的邮箱。');
});

test('a nested crop can be canceled or saved independently of the nickname', async () => {
  const firstFrame = { width: 1200, height: 600, close: vi.fn() };
  const drawImage = vi.fn();
  vi.stubGlobal('createImageBitmap', vi.fn().mockResolvedValue(firstFrame));
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockImplementation(function (
    this: HTMLCanvasElement,
  ) {
    return { canvas: this, clearRect: vi.fn(), drawImage } as unknown as CanvasRenderingContext2D;
  });
  vi.spyOn(HTMLCanvasElement.prototype, 'toBlob').mockImplementation((callback) => {
    callback(new Blob(['crop'], { type: 'image/png' }));
  });
  const { avatarUrl, avatarWrites, queries, user } = setup();
  await user.type(screen.getByLabelText('昵称'), '创作者');
  const picker = screen.getByLabelText(/^头像/);
  const signature = new Uint8Array([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);
  const file = new File([signature], 'avatar.png', { type: 'image/png' });
  await user.upload(picker, file);
  let crop = within(await screen.findByRole('dialog', { name: '裁剪头像' }));
  await user.click(crop.getByRole('button', { name: '取消' }));
  await waitFor(() => expect(document.activeElement).toBe(picker));
  expect(avatarWrites).not.toHaveBeenCalled();
  expect(screen.getByLabelText('昵称')).toHaveProperty('value', '创作者');

  await user.upload(picker, file);
  crop = within(await screen.findByRole('dialog', { name: '裁剪头像' }));
  const zoom = await crop.findByRole('slider', { name: '缩放' });
  zoom.focus();
  await user.keyboard('{End}');
  expect(zoom.getAttribute('aria-valuenow')).toBe('400');
  crop.getByRole('group', { name: '头像裁剪区域' }).focus();
  await user.keyboard('{Shift>}{ArrowRight}{/Shift}');
  expect(avatarWrites).not.toHaveBeenCalled();
  await user.click(crop.getByRole('button', { name: '保存头像' }));
  await screen.findByText('头像已更新');
  expect(drawImage).toHaveBeenLastCalledWith(firstFrame, 510, 225, 150, 150, 0, 0, 256, 256);
  expect(avatarWrites).toHaveBeenCalledTimes(1);
  expect(avatarWrites).toHaveBeenCalledWith('PUT', expect.any(Blob));
  expect(document.querySelector('.account-avatar img')?.getAttribute('src')).toBe(avatarUrl);
  expect(queries.getQueryData<AuthSession>(['session'])?.user?.nickname).toBeNull();

  await user.click(screen.getByRole('button', { name: '保存昵称' }));
  await screen.findByText('昵称已保存');
  expect(queries.getQueryData<AuthSession>(['session'])?.user?.nickname).toBe('创作者');

  await user.click(screen.getByRole('button', { name: '移除头像' }));
  await screen.findByText('头像已移除');
  await waitFor(() => expect(document.querySelector('.account-avatar img')).toBeNull());
});
