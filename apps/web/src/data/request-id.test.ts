import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createRequestId } from './request-id.ts';

void test('creates a UUID with the crypto methods available over HTTP', (context) => {
  context.mock.getter(globalThis, 'crypto', () => ({
    getRandomValues: (bytes: Uint8Array) => bytes.fill(0xff),
  }));

  assert.equal(createRequestId(), 'ffffffff-ffff-4fff-bfff-ffffffffffff');
});
