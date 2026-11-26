import assert from 'node:assert/strict';
import { test } from 'node:test';
import { collectionPosition } from './collection-position.ts';

const first = { id: 'first' };
const second = { id: 'second' };
const third = { id: 'third' };

void test('neighbors use the item ID and the order of the current list without wrapping', () => {
  assert.deepEqual(collectionPosition([second, first, third], first.id, false), {
    index: 1,
    previous: second,
    next: third,
    atPageBoundary: false,
  });
  assert.equal(collectionPosition([first, second], first.id, false)?.previous, undefined);
  assert.equal(collectionPosition([first, second], second.id, false)?.next, undefined);
  assert.equal(collectionPosition([first, second], third.id, true), undefined);
});

void test('appended pages supply a neighbor rather than restarting the list', () => {
  assert.equal(collectionPosition([first, second], second.id, true)?.atPageBoundary, true);
  assert.equal(collectionPosition([first, second], second.id, false)?.atPageBoundary, false);
  const position = collectionPosition([first, second, third], second.id, true);
  assert.equal(position?.next, third);
  assert.equal(position?.atPageBoundary, false);
});
