import { useState } from 'react';
import type { ComponentType } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { afterEach, expect, test, vi } from 'vitest';
import { createApiClient } from '@comfyshop/api-client';
import type { Artifact, Execution } from '@comfyshop/api-client';
import type { MediaRendererProps } from '@comfyshop/media';
import { Tooltip } from '@comfyshop/ui';
import { WorkspaceContext } from '../app/use-workspace';
import { ExecutionDialog } from './execution-dialog';
import { Notify } from './notify';
import type { NoticeAction } from './notify';

// jsdom 不做布局测量；保留真实卡片、弹框、删除确认、查询及撤销流程。
vi.mock('@comfyshop/media', () => ({
  MediaMasonry: ({
    items,
    render: Card,
  }: {
    items: Artifact[];
    render: ComponentType<MediaRendererProps<Artifact>>;
  }) => (
    <div>
      {items.map((item, index) => (
        <Card key={item.id} data={item} index={index} width={300} />
      ))}
    </div>
  ),
}));

afterEach(cleanup);

const artifact = (id: string, executionId = 'first'): Artifact => ({
  id,
  taskId: 'task',
  workflowId: 'workflow',
  workflowName: '工作流',
  filename: `${id}.png`,
  sha256: 'checksum',
  size: 100,
  contentType: 'image/png',
  media: {
    src: `/${id}.png`,
    width: 300,
    height: 300,
    kind: 'image',
    video: null,
    thumbnail: null,
    videoPreview: null,
    filename: null,
    durationMs: null,
  },
  executionId,
  outputNodeId: '1',
  outputNodeTitle: '输出',
  outputSlot: 'images',
  outputIndex: 0,
  created: 1,
});

const first: Execution = {
  id: 'first',
  taskId: 'task',
  taskOwnerId: 'owner',
  projectId: null,
  workflowId: 'workflow',
  versionId: 'version',
  workflowName: '第一组',
  index: 0,
  status: 'succeeded',
  promptId: 'prompt',
  inputValues: {},
  effectivePrompt: null,
  promptExpanded: null,
  coverArtifactId: 'a',
  coverFrameMs: null,
  coverImage: null,
  media: artifact('a').media,
  imageCount: 2,
  videoCount: 0,
  audioCount: 0,
  modelCount: 0,
  textCount: 0,
  artifactCount: 2,
  created: 1,
};
const second: Execution = {
  ...first,
  id: 'second',
  workflowName: '第二组',
  imageCount: 1,
  artifactCount: 1,
  coverArtifactId: 'c',
  media: artifact('c', 'second').media,
};

async function setup() {
  let members = [artifact('a'), artifact('b')];
  const notices: NoticeAction[] = [];
  const fetcher: typeof fetch = (input, init) => {
    const url = new URL(input instanceof Request ? input.url : input, 'http://platform.test');
    const path = url.pathname;
    if (path === '/api/v1/auth/session')
      return Promise.resolve(
        Response.json({ user: { id: 'owner', username: 'owner', email: null }, csrfToken: 'csrf' }),
      );
    if (path === '/api/v1/workspace') return Promise.resolve(Response.json({ favoriteIds: [] }));
    if (path === '/api/v1/workflows/workflow')
      return Promise.resolve(Response.json({ published: true }));
    if (path === '/api/v1/artifacts')
      return Promise.resolve(
        Response.json({
          items:
            url.searchParams.get('execution_id') === 'second' ? [artifact('c', 'second')] : members,
          nextCursor: null,
        }),
      );
    if (path === '/api/v1/artifacts/a' && init?.method === 'DELETE') {
      members = [artifact('b')];
      return Promise.resolve(
        Response.json({ ...first, imageCount: 1, artifactCount: 1, coverArtifactId: 'b' }),
      );
    }
    if (path === '/api/v1/artifacts/a/restore') {
      members = [artifact('a'), artifact('b')];
      return Promise.resolve(Response.json(first));
    }
    throw new Error(`Unexpected request: ${init?.method} ${path}`);
  };
  const api = createApiClient('', fetcher);
  const queries = new QueryClient({
    defaultOptions: { queries: { staleTime: Infinity, retry: false } },
  });
  queries.setQueryData(['session'], await api.session());
  function Browser() {
    const [execution, select] = useState(first);
    return (
      <ExecutionDialog
        initialExecution={execution}
        pages={{
          data: { pages: [{ items: [first, second] }], pageParams: [null] },
          hasNextPage: false,
          fetchNextPage: vi.fn(),
        }}
        select={select}
        onClose={() => {}}
      />
    );
  }
  const view = render(
    <QueryClientProvider client={queries}>
      <WorkspaceContext.Provider value={api}>
        <Tooltip.Provider>
          <MemoryRouter>
            <Notify.Provider value={(_message, action) => action && notices.push(action)}>
              <Browser />
            </Notify.Provider>
          </MemoryRouter>
        </Tooltip.Provider>
      </WorkspaceContext.Provider>
    </QueryClientProvider>,
  );
  return {
    user: userEvent.setup(),
    notices,
    dispose: () => {
      view.unmount();
      queries.clear();
    },
  };
}

test.each([false, true])(
  'undo restores the count and respects later navigation: %s',
  async (move) => {
    const { user, notices, dispose } = await setup();
    try {
      await user.click(await screen.findByRole('button', { name: '查看 a.png' }));
      await user.click(screen.getByRole('button', { name: '删除成品' }));
      await user.click(screen.getByRole('button', { name: '确认删除' }));
      await waitFor(() => expect(notices).toHaveLength(1));
      expect(screen.getByText(/1 张图片/)).toBeDefined();
      if (move) {
        await user.click(screen.getByRole('button', { name: '下一项' }));
        await screen.findByRole('img', { name: 'c.png' });
      }
      await act(async () => {
        await notices[0].run();
      });
      if (move) {
        expect(screen.getByRole('heading', { name: '第二组' })).toBeDefined();
        expect(screen.getByRole('img', { name: 'c.png' })).toBeDefined();
      } else {
        expect(await screen.findByRole('button', { name: '查看 a.png' })).toBeDefined();
        expect(screen.getByRole('button', { name: '查看 b.png' })).toBeDefined();
        expect(screen.getByText(/2 张图片/)).toBeDefined();
      }
    } finally {
      dispose();
    }
  },
);
