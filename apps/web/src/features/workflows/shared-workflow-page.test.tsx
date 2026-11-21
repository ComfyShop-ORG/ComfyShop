import { useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router';
import { expect, test, vi } from 'vitest';
import { createApiClient } from '@comfyshop/api-client';
import { Button } from '@comfyshop/ui';
import { WorkspaceContext } from '../../app/use-workspace';
import SharedWorkflowPage from './shared-workflow-page';

vi.mock('./workflow-dialog', () => ({
  default: function WorkflowDialog({
    currentVersionId,
    linkedWork,
    onLinkedWorkClose,
  }: {
    currentVersionId?: string;
    linkedWork?: { id: string };
    onLinkedWorkClose: () => void;
  }) {
    const [replaySource, setReplaySource] = useState('');
    return (
      <>
        <p>当前版本 {currentVersionId}</p>
        {linkedWork && (
          <Button
            type="button"
            onClick={() => {
              onLinkedWorkClose();
              setReplaySource(linkedWork.id);
            }}
          >
            载入参数
          </Button>
        )}
        <p>重跑来源 {replaySource}</p>
      </>
    );
  },
}));

function Search() {
  return <output>{useLocation().search}</output>;
}

test('preserves the replay draft when closing a direct link to the current published version', async () => {
  const version = 'published-version';
  const detailReads: (string | null)[] = [];
  const api = createApiClient('', (input) => {
    const url = new URL(input instanceof Request ? input.url : input, 'http://platform.test');
    switch (url.pathname) {
      case '/api/v1/auth/session':
        return Promise.resolve(
          Response.json({ user: { id: 'reader', username: 'reader' }, csrfToken: 'csrf' }),
        );
      case '/api/v1/workspace':
        return Promise.resolve(Response.json({ favoriteIds: [] }));
      case '/api/v1/works/shared-work':
        return Promise.resolve(
          Response.json({ id: 'shared-work', workflowId: 'workflow', versionId: version }),
        );
      case '/api/v1/workflows/workflow':
        detailReads.push(url.searchParams.get('version_id'));
        return Promise.resolve(Response.json({ id: 'workflow', versionId: version }));
      case '/api/v1/workflows/workflow/versions':
        return Promise.resolve(Response.json({ currentVersionId: version, items: [] }));
      default:
        throw new Error('Unexpected request: ' + url.pathname);
    }
  });
  const queries = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const view = render(
    <QueryClientProvider client={queries}>
      <WorkspaceContext.Provider value={api}>
        <MemoryRouter initialEntries={['/workflows/workflow?work=shared-work']}>
          <Search />
          <Routes>
            <Route
              path="/workflows/:workflowId"
              element={
                <SharedWorkflowPage
                  restoreFocus={() => {}}
                  requireAuth={() => {}}
                  notify={() => {}}
                />
              }
            />
          </Routes>
        </MemoryRouter>
      </WorkspaceContext.Provider>
    </QueryClientProvider>,
  );
  try {
    await screen.findByText('当前版本 published-version');
    await userEvent.click(screen.getByRole('button', { name: '载入参数' }));
    await screen.findByText('?version=published-version');
    expect(screen.getByText('重跑来源 shared-work')).toBeTruthy();
    expect(detailReads).toEqual([version]);
  } finally {
    view.unmount();
    queries.clear();
  }
});
