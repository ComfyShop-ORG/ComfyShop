import assert from 'node:assert/strict';
import { test } from 'node:test';
import {
  promptWithAspect,
  promptWithoutAspect,
  ratioDimensions,
  referenceFrameCount,
  referenceTimeIssue,
} from './output-specification.ts';

void test('ResolutionSelector previews the selected aspect, pixel budget and alignment', () => {
  assert.deepEqual(ratioDimensions('1:1 (Square)', 1, 8), [1024, 1024]);
  assert.deepEqual(ratioDimensions('9:16 (Portrait Widescreen)', 0.25, 8), [384, 680]);
  assert.deepEqual(ratioDimensions('9:16 (Portrait Widescreen)', 0.25, 32), [384, 672]);
  assert.deepEqual(ratioDimensions('9:16', 0.25, 8, null, 16), [384, 672]);
  assert.deepEqual(ratioDimensions('9:16', 0.25, 16, 32, 16), [384, 704]);
  assert.deepEqual(ratioDimensions('9:16', 0.25, 8, null, 8, 16), [384, 672]);
  assert.deepEqual(ratioDimensions('1:1', (696 / 1024) ** 2, 8, null, 8, 16), [704, 704]);
  assert.deepEqual(ratioDimensions('1:1', (20 / 1024) ** 2, 8), [16, 16]);
  assert.equal(ratioDimensions('1:1', '', 8), null);
  assert.equal(ratioDimensions('no ratio', 1, 8), null);
  assert.equal(ratioDimensions('1:1', 1, 0), null);
});

void test('user text can be edited separately from the linked aspect line', () => {
  const text = 'Aspect ratio: 4:3\r\nRequest: 一座山\nAspect ratio: 5:4 is written on a sign.';
  const body = 'Request: 一座山\nAspect ratio: 5:4 is written on a sign.';
  assert.equal(promptWithoutAspect(text), body);
  assert.equal(promptWithAspect(text, '9:16 (Portrait Widescreen)'), 'Aspect ratio: 9:16\n' + body);
  assert.equal(promptWithAspect(text, ''), text);
});

void test('reference time checks the model-aligned frame count and supports negative positions', () => {
  const timeline = {
    durationFieldId: 'duration',
    frames: [],
    framesPerSecond: 24,
    minimumFrames: 5,
    frameStep: 17,
  };
  assert.equal(referenceFrameCount(5, timeline), 124);
  assert.equal(referenceFrameCount(4.9, timeline), 124);
  assert.equal(referenceFrameCount(4.4, timeline), 107);
  assert.equal(referenceTimeIssue(5, 124, 24), null);
  assert.match(referenceTimeIssue(5, 107, 24) ?? '', /4.42 秒/);
  assert.equal(referenceTimeIssue(-1 / 24, 107, 24), null);
  assert.match(referenceTimeIssue(-5, 107, 24) ?? '', /超出片段/);
});
