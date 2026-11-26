import { test } from 'node:test';
import assert from 'node:assert/strict';
import { ApiError, createApiClient } from './index.ts';

function requestUrl(url: RequestInfo | URL): string {
  return url instanceof Request ? url.url : String(url);
}

await test('cookie requests preserve abort signals and use the server CSRF token for writes', async () => {
  const calls: Array<{ url: string; init?: RequestInit }> = [];
  const fetcher: typeof fetch = (url, init) => {
    calls.push({ url: requestUrl(url), init });
    if (requestUrl(url).endsWith('/auth/session'))
      return Promise.resolve(
        Response.json({ user: { id: '1', username: 'owner' }, csrfToken: 'csrf-value' }),
      );
    return Promise.resolve(new Response(null, { status: 204 }));
  };
  const api = createApiClient('https://api.example/', fetcher);
  const controller = new AbortController();
  await api.session(controller.signal);
  await api.favorite('workflow/id', true);
  assert.equal(calls[0].url, 'https://api.example/api/v1/auth/session');
  assert.equal(calls[0].init?.signal, controller.signal);
  assert.equal(calls[1].url, 'https://api.example/api/v1/workflows/workflow%2Fid/favorite');
  assert.equal(calls[1].init?.method, 'PUT');
  assert.equal(calls[1].init?.credentials, 'include');
  assert.equal((calls[1].init?.headers as Record<string, string>)['X-CSRF-Token'], 'csrf-value');
  assert.equal(calls[1].init?.cache, 'no-store');
});

await test('authentication errors are typed; expired sessions clear identity without a local fallback', async () => {
  let expired = 0;
  const api = createApiClient(
    '',
    () => Promise.resolve(Response.json({ detail: '请先登录' }, { status: 401 })),
    () => {
      expired++;
    },
  );
  await assert.rejects(
    api.workspace(),
    (error: unknown) =>
      error instanceof ApiError && error.status === 401 && error.message === '请先登录',
  );
  assert.equal(expired, 1);
  await assert.rejects(api.login('owner', 'wrong-password'), ApiError);
  assert.equal(expired, 1);
  await assert.rejects(
    createApiClient('', () => {
      return Promise.reject(new TypeError('offline'));
    }).health(),
    (error: unknown) => error instanceof ApiError && error.status === 0,
  );
});

await test('task requests preserve the caller idempotency key and cursor escaping', async () => {
  const calls: Array<{ url: string; init?: RequestInit }> = [];
  const api = createApiClient('', (url, init) => {
    calls.push({ url: requestUrl(url), init });
    return Promise.resolve(Response.json({}));
  });
  const body = {
    workflowId: 'workflow',
    versionId: 'version',
    inputValues: {},
    inputSchemaHash: 'a'.repeat(64),
    idempotencyKey: 'same-intent-key-1234',
  };
  await api.createTask(body);
  await api.createTask(body);
  assert.equal(calls[0].init?.body, calls[1].init?.body);
  assert.equal(calls[0].init?.body, JSON.stringify(body));
  await api.tasks({ cursor: 'a/b?=', workflow_id: 'id' });
  assert.match(calls[2].url, /cursor=a%2Fb%3F%3D/);
});

await test('asset uploads send raw files with session, CSRF and abort propagation', async () => {
  const calls: Array<{ url: string; init?: RequestInit }> = [];
  const api = createApiClient('', (url, init) => {
    calls.push({ url: requestUrl(url), init });
    return Promise.resolve(
      Response.json(
        requestUrl(url).endsWith('/auth/session')
          ? { user: { id: '1', username: 'owner' }, csrfToken: 'csrf-value' }
          : {},
      ),
    );
  });
  await api.session();
  const file = new File(['image-bytes'], 'reference image.png', { type: 'image/png' });
  const controller = new AbortController();
  await api.uploadAsset(file, 'upload-id', controller.signal);
  const request = calls[1];
  assert.equal(request.init?.body, file);
  assert.equal(request.init?.signal, controller.signal);
  assert.equal(request.init?.credentials, 'include');
  assert.equal(
    (request.init?.headers as Record<string, string>)['Content-Type'],
    'application/octet-stream',
  );
  assert.equal((request.init?.headers as Record<string, string>)['X-CSRF-Token'], 'csrf-value');
  assert.match(request.url, /filename=reference\+image.png/);
});

await test('work publication preserves the selected subset and replay requests keep their source version', async () => {
  const calls: Array<{ url: string; init?: RequestInit }> = [];
  const api = createApiClient('', (url, init) => {
    calls.push({ url: requestUrl(url), init });
    return Promise.resolve(Response.json({}));
  });
  const body = {
    id: 'publication-intent',
    executionId: 'execution',
    title: '作品',
    artifactIds: ['second', 'first'],
    coverArtifactId: 'second',
  };
  await api.publishWork(body);
  await api.publishWork(body);
  assert.equal(calls[0].init?.body, calls[1].init?.body);
  const submitted = calls[0].init?.body;
  assert.ok(typeof submitted === 'string');
  assert.deepEqual(JSON.parse(submitted), body);
  await api.workflowForm('workflow/id', 'source-version', 'my-machine', undefined, {
    workId: 'work/id',
  });
  const url = new URL(calls[2].url, 'http://localhost');
  assert.equal(url.pathname, '/api/v1/workflows/workflow%2Fid/inputs');
  assert.equal(url.searchParams.get('version_id'), 'source-version');
  assert.equal(url.searchParams.get('work_id'), 'work/id');
  assert.equal(url.searchParams.get('machine_id'), 'my-machine');
  assert.equal(url.searchParams.has('task_id'), false);
});
