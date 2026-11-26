import type { ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, cleanup, renderHook } from '@testing-library/react';
import { afterEach, expect, test, vi } from 'vitest';
import { WorkspaceProvider } from './workspace-provider';
import { useWorkspace } from './use-workspace';

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

test('clears cached workspace data once per identity change', async () => {
  const queries = new QueryClient({ defaultOptions: { queries: { staleTime: Infinity } } });
  const session = (id: string) => ({ user: { id, username: id }, csrfToken: `csrf-${id}` });
  queries.setQueryData(['session'], session('first'));
  queries.setQueryData(['private-example', 'first'], 'old content');
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string) => {
      if (url.endsWith('/auth/login')) return Promise.resolve(Response.json(session('second')));
      if (url.endsWith('/auth/logout')) return Promise.resolve(new Response(null, { status: 204 }));
      return Promise.resolve(Response.json({ favoriteIds: [] }));
    }),
  );
  const clear = vi.spyOn(queries, 'removeQueries');
  const { result } = renderHook(useWorkspace, {
    wrapper: ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queries}>
        <WorkspaceProvider>{children}</WorkspaceProvider>
      </QueryClientProvider>
    ),
  });
  await act(async () => result.current.workspace.signIn('second', 'example-password'));
  expect(clear).toHaveBeenCalledTimes(1);
  expect(queries.getQueryData(['private-example', 'first'])).toBeUndefined();

  act(() => {
    queries.setQueryData(['session'], session('second'));
  });
  expect(clear).toHaveBeenCalledTimes(1);
  await act(async () => result.current.workspace.signOut());
  expect(clear).toHaveBeenCalledTimes(2);
  act(() => {
    queries.setQueryData(['session'], session('third'));
  });
  expect(clear).toHaveBeenCalledTimes(3);
});
