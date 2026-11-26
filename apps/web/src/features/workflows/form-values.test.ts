import assert from 'node:assert/strict';
import test from 'node:test';
import { applyInputPatch, formValues } from './form-values.ts';

await test('explicitly cleared references remain cleared while untouched inputs use defaults', () => {
  const fields = [
    { id: 'image', default: { assetId: 'source' } },
    { id: 'prompt', default: 'original' },
    { id: 'seed', default: 42 },
  ];
  assert.deepEqual(formValues(fields, { image: null, prompt: '', seed: 0, removed: 'unused' }), {
    image: null,
    prompt: '',
    seed: 0,
  });
  assert.deepEqual(formValues(fields, null), {
    image: { assetId: 'source' },
    prompt: 'original',
    seed: 42,
  });
});

await test('hidden inputs retain the form defaults even if the draft contains earlier edits', () => {
  const fields = [
    { id: 'steps', default: 24 },
    { id: 'prompt', default: 'source prompt' },
  ];
  assert.deepEqual(formValues(fields, { steps: 36, prompt: '' }, new Set(['steps'])), {
    steps: 24,
    prompt: '',
  });
});

await test('reset removes a draft override and keeps a deliberately cleared upload', () => {
  const draft = { hidden: 8, other: 'keep', image: { assetId: 'previous' } };
  const patch = { hidden: undefined, image: null };
  assert.deepEqual(applyInputPatch(draft, patch), { other: 'keep', image: null });
  assert.equal(draft.hidden, 8);
});
