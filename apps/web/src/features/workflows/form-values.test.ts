import assert from 'node:assert/strict';
import test from 'node:test';
import { formValues } from './form-values.ts';

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
