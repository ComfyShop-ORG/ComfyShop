import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { afterAll, beforeAll, expect, test } from 'vitest';
import { createApiClient } from '@comfyshop/api-client';
import type { Machine } from '@comfyshop/api-client';
import { Tooltip } from '@comfyshop/ui';
import { useMachines, WorkspaceContext } from '../../app/use-workspace';
import MachineLinkDialog from './machine-link-dialog';

const scrollIntoView = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'scrollIntoView');
beforeAll(() => {
  Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', {
    configurable: true,
    value: () => {},
  });
});
afterAll(() => {
  if (scrollIntoView)
    Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', scrollIntoView);
  else Reflect.deleteProperty(HTMLElement.prototype, 'scrollIntoView');
});

function MachineList() {
  const { data } = useMachines();
  return (
    <ul>
      {data?.items.map((machine) => (
        <li key={machine.id}>{machine.name}</li>
      ))}
    </ul>
  );
}

test.each(['first', 'new', 'reconnect'] as const)(
  'confirms a %s connection and refreshes the list after redemption',
  async (mode) => {
    const original: Machine = {
      id: 'original',
      name: '工作室',
      keyPrefix: 'cs_prefix',
      device: '',
      online: false,
      busy: false,
      revoked: false,
      lastSeen: null,
      nodeCount: 0,
      runtime: null,
      update: null,
      updateAvailable: false,
    };
    const incoming = { ...original, id: 'new-machine', name: '新工作机' };
    const previous = mode === 'first' ? [] : [original];
    const machine = mode === 'reconnect' ? original : incoming;
    let status: 'pending' | 'approved' | 'linked' = 'pending';
    let listReads = 0;
    let approved: unknown;
    const api = createApiClient('', (input, init) => {
      const path = new URL(input instanceof Request ? input.url : input, 'http://platform.test')
        .pathname;
      if (path === '/api/v1/auth/session') {
        return Promise.resolve(
          Response.json({ user: { id: 'owner', username: 'owner' }, csrfToken: 'csrf' }),
        );
      }
      if (path === '/api/v1/workspace') return Promise.resolve(Response.json({ favoriteIds: [] }));
      if (path === '/api/v1/machines') {
        listReads += 1;
        return Promise.resolve(
          Response.json({
            items: status === 'linked' && mode !== 'reconnect' ? [...previous, machine] : previous,
            defaultMachineId: previous[0]?.id ?? (status === 'linked' ? machine.id : null),
          }),
        );
      }
      if (path === '/api/v1/machines/links/ABCDEFGH') {
        return Promise.resolve(
          Response.json({
            code: 'ABCDEFGH',
            name: status === 'pending' ? incoming.name : machine.name,
            status,
            source: '192.0.2.10',
            sameNetwork: false,
            requestedAt: Date.now(),
            expiresAt: Date.now() + 600_000,
          }),
        );
      }
      if (path === '/api/v1/machines/links/ABCDEFGH/approve' && init?.method === 'POST') {
        if (typeof init.body !== 'string') throw new Error('Expected a JSON request body');
        approved = JSON.parse(init.body);
        status = 'approved';
        return Promise.resolve(new Response(null, { status: 204 }));
      }
      throw new Error(`Unexpected request: ${init?.method} ${path}`);
    });
    const queries = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const view = render(
      <QueryClientProvider client={queries}>
        <WorkspaceContext.Provider value={api}>
          <Tooltip.Provider>
            <MemoryRouter initialEntries={['/machines/link?code=ABCDEFGH']}>
              <MachineList />
              <MachineLinkDialog />
            </MemoryRouter>
          </Tooltip.Provider>
        </WorkspaceContext.Provider>
      </QueryClientProvider>,
    );
    try {
      const user = userEvent.setup();
      await waitFor(() => expect(listReads).toBe(1));
      if (mode !== 'first') {
        const target = await screen.findByRole('combobox', { name: '接入方式' });
        expect(screen.getByRole<HTMLButtonElement>('button', { name: '确认接入' }).disabled).toBe(
          true,
        );
        target.focus();
        await user.keyboard('{Enter}');
        fireEvent.keyDown(
          await screen.findByRole('option', {
            name: mode === 'reconnect' ? /^重新连接 工作室/ : '新增工作机',
          }),
          { key: 'Enter' },
        );
      }
      await user.click(
        await screen.findByRole('button', {
          name: mode === 'reconnect' ? '重新连接' : '确认接入',
        }),
      );
      await screen.findByText('已确认，等待工作机接入。');
      expect(approved).toEqual(
        mode === 'reconnect' ? { machineId: original.id } : { name: incoming.name },
      );
      expect(listReads).toBe(1);
      expect(screen.queryByRole('button', { name: '完成' })).toBeNull();

      status = 'linked';
      await screen.findByRole('button', { name: '完成' }, { timeout: 3000 });
      await waitFor(() => expect(listReads).toBe(2));
      expect(screen.getByText(machine.name, { selector: 'li' })).toBeTruthy();
    } finally {
      view.unmount();
      queries.clear();
    }
  },
);
