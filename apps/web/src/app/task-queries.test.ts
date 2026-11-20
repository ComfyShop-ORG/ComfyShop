import assert from 'node:assert/strict';
import { test } from 'node:test';
import { QueryClient } from '@tanstack/react-query';
import { createApiClient } from '@comfyshop/api-client';
import type { Task } from '@comfyshop/api-client';
import {
  executionHistoryKey,
  taskActivityOptions,
  taskHistoryOptions,
  taskWithProgress,
} from './task-queries.ts';

const active: Task = {
  id: 'old-active',
  workflowId: 'workflow',
  versionId: 'version',
  workflowName: '工作流',
  executionCount: 2,
  status: 'running',
  progress: 10,
  machineId: 'machine',
  stage: 'executing',
  error: null,
  promptId: null,
  started: 1,
  updated: 10,
  inputValues: {},
  sourceExecutionId: null,
  sourceWorkId: null,
  media: null,
};

await test('activity polls keep cursor pages, refresh results on completion, and reconcile terminal tasks once', async () => {
  let progress = 10;
  let completedExecutions = 0;
  let activeVisible = true;
  let deleted = false;
  const calls: string[] = [];
  const api = createApiClient('http://local.test', (url) => {
    const request = new URL(url instanceof Request ? url.url : url);
    calls.push(request.pathname);
    if (request.pathname.endsWith('/activity')) {
      assert.equal(request.searchParams.get('workflow_id'), 'workflow');
      return Promise.resolve(
        Response.json({
          activeTasks: activeVisible
            ? [{ id: active.id, status: active.status, progress, stage: active.stage, updated: 11 }]
            : [],
          completedExecutions,
        }),
      );
    }
    assert.equal(request.pathname, '/api/v1/tasks/old-active');
    if (deleted) return Promise.resolve(Response.json({ detail: '任务不存在' }, { status: 404 }));
    return Promise.resolve(
      Response.json({ ...active, status: 'failed', error: '工作机连接中断', updated: 12 }),
    );
  });
  const queries = new QueryClient();
  const history = taskHistoryOptions(api, 'owner', 'workflow');
  const activity = taskActivityOptions(api, queries, 'owner', { workflowId: 'workflow' });
  const results = executionHistoryKey('owner', 'workflow');
  const earlierVersion = executionHistoryKey('owner', 'workflow', undefined, 'v2');
  const currentVersion = executionHistoryKey('owner', 'workflow', undefined, 'v3');
  const unrelated = executionHistoryKey('owner', 'different');
  const pages = {
    pages: [
      { items: [{ ...active, id: 'newest', status: 'succeeded' as const }], nextCursor: 'second' },
      { items: [{ ...active, id: 'middle', status: 'succeeded' as const }], nextCursor: 'third' },
      { items: [active], nextCursor: null },
    ],
    pageParams: [null, 'second', 'third'],
  };
  queries.setQueryData(history.queryKey, pages);
  await queries.fetchQuery(activity);
  queries.setQueryData(results, { pages: [], pageParams: [] });
  queries.setQueryData(earlierVersion, { pages: [{ items: [] }], pageParams: [null] });
  queries.setQueryData(currentVersion, { pages: [], pageParams: [] });
  queries.setQueryData(unrelated, { pages: [], pageParams: [] });
  assert.notDeepEqual(queries.getQueryData(earlierVersion), queries.getQueryData(currentVersion));

  progress = 45;
  let snapshot = await queries.fetchQuery(activity);
  assert.equal(taskWithProgress(active, snapshot.updates[active.id]).progress, 45);
  assert.equal(history.refetchInterval, undefined);
  assert.equal(queries.getQueryState(results)?.isInvalidated, false);
  assert.strictEqual(queries.getQueryData(history.queryKey), pages);

  completedExecutions = 1;
  await queries.fetchQuery(activity);
  assert.equal(queries.getQueryState(results)?.isInvalidated, true);
  assert.equal(queries.getQueryState(earlierVersion)?.isInvalidated, true);
  assert.equal(queries.getQueryState(currentVersion)?.isInvalidated, true);
  assert.equal(queries.getQueryState(unrelated)?.isInvalidated, false);

  activeVisible = false;
  snapshot = await queries.fetchQuery(activity);
  assert.equal(taskWithProgress(active, snapshot.updates[active.id]).error, '工作机连接中断');
  snapshot = await queries.fetchQuery(activity);
  assert.equal(taskWithProgress(active, snapshot.updates[active.id]).status, 'failed');
  assert.strictEqual(queries.getQueryData(history.queryKey), pages);
  assert.equal(calls.filter((path) => path === '/api/v1/tasks/activity').length, 5);
  assert.deepEqual(
    calls.filter((path) => !path.endsWith('/activity')),
    ['/api/v1/tasks/old-active'],
  );

  // Another session can delete a finished task while this tab still has its active snapshot.
  deleted = true;
  queries.removeQueries({ queryKey: activity.queryKey });
  snapshot = await queries.fetchQuery(activity);
  assert.equal(snapshot.updates[active.id], undefined);
  assert.equal(queries.getQueryState(history.queryKey)?.isInvalidated, true);
});

await test('terminal transitions refresh status filters even when their history is empty', async (t) => {
  for (const status of ['succeeded', 'failed', 'cancelled'] as const)
    await t.test(status, async () => {
      let ended = false;
      const api = createApiClient('http://local.test', (url) => {
        const request = new URL(url instanceof Request ? url.url : url);
        if (request.pathname.endsWith('/activity'))
          return Promise.resolve(
            Response.json({
              activeTasks: ended ? [] : [active],
              completedExecutions: ended && status === 'succeeded' ? 1 : 0,
            }),
          );
        assert.equal(request.pathname, '/api/v1/tasks');
        const filter = request.searchParams.get('state');
        return Promise.resolve(
          Response.json({
            items: ended && filter === status ? [{ ...active, status, updated: 20 }] : [],
            nextCursor: null,
          }),
        );
      });
      const queries = new QueryClient();
      const all = taskHistoryOptions(api, 'owner', 'workflow');
      const history = { pages: [{ items: [active], nextCursor: null }], pageParams: [null] };
      queries.setQueryData(all.queryKey, history);
      const filters = ['active', 'succeeded', 'failed', 'cancelled'] as const;
      for (const filter of filters)
        queries.setQueryData(taskHistoryOptions(api, 'owner', 'workflow', filter).queryKey, {
          pages: [{ items: filter === 'active' ? [active] : [], nextCursor: null }],
          pageParams: [null],
        });
      const unrelated = taskHistoryOptions(api, 'owner', 'different', 'active');
      const otherOwner = taskHistoryOptions(api, 'other-owner', 'workflow', 'active');
      queries.setQueryData(unrelated.queryKey, history);
      queries.setQueryData(otherOwner.queryKey, history);

      // 当前筛选没有历史条目，仍能根据活动集合的变化发现任务结束。
      const activity = taskActivityOptions(api, queries, 'owner', {
        workflowId: 'workflow',
        state: status,
      });
      await queries.fetchQuery(activity);
      ended = true;
      await queries.fetchQuery(activity);
      for (const filter of filters)
        assert.equal(
          queries.getQueryState(taskHistoryOptions(api, 'owner', 'workflow', filter).queryKey)
            ?.isInvalidated,
          true,
        );
      assert.strictEqual(queries.getQueryData(all.queryKey), history);
      assert.equal(queries.getQueryState(unrelated.queryKey)?.isInvalidated, false);
      assert.equal(queries.getQueryState(otherOwner.queryKey)?.isInvalidated, false);

      const completed = await queries.fetchInfiniteQuery(
        taskHistoryOptions(api, 'owner', 'workflow', status),
      );
      assert.equal(completed.pages[0].items[0].status, status);
      const remaining = await queries.fetchInfiniteQuery(
        taskHistoryOptions(api, 'owner', 'workflow', 'active'),
      );
      assert.deepEqual(remaining.pages[0].items, []);
      await queries.fetchQuery(activity);
      assert.equal(
        queries.getQueryState(taskHistoryOptions(api, 'owner', 'workflow', status).queryKey)
          ?.isInvalidated,
        false,
      );
      queries.clear();
    });
});

await test('a version-scoped activity poll refreshes that version of the results', async () => {
  let completedExecutions = 0;
  const api = createApiClient('http://local.test', (url) => {
    const request = new URL(url instanceof Request ? url.url : url);
    assert.equal(request.searchParams.get('workflow_id'), 'workflow');
    assert.equal(request.searchParams.get('version_id'), 'v3');
    return Promise.resolve(Response.json({ activeTasks: [], completedExecutions }));
  });
  const queries = new QueryClient();
  const activity = taskActivityOptions(api, queries, 'owner', {
    workflowId: 'workflow',
    versionId: 'v3',
  });
  await queries.fetchQuery(activity);
  const earlier = executionHistoryKey('owner', 'workflow', undefined, 'v2');
  const current = executionHistoryKey('owner', 'workflow', undefined, 'v3');
  for (const key of [earlier, current]) queries.setQueryData(key, { pages: [], pageParams: [] });

  completedExecutions = 1;
  await queries.fetchQuery(activity);
  assert.equal(queries.getQueryState(earlier)?.isInvalidated, false);
  assert.equal(queries.getQueryState(current)?.isInvalidated, true);
  queries.clear();
});
