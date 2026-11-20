import assert from 'node:assert/strict';
import test from 'node:test';
import type { InputValue, WorkflowForm, WorkflowInput } from '@comfyshop/api-client';
import { applyInputPatch } from './form-values.ts';
import { runParameterState, sameInputValue } from './run-parameter-state.ts';

function field(id: string, kind: WorkflowInput['kind'], value: InputValue): WorkflowInput {
  return {
    id,
    kind,
    default: value,
    label: id,
    nodeId: id,
    nodeTitle: id,
    inputName: id,
    choices: [],
    minimum: null,
    maximum: null,
    step: null,
    multiline: false,
    named: true,
    primary: false,
    integerAsString: false,
  };
}

function form(fields: WorkflowInput[], hidden: string[] = []): WorkflowForm {
  return {
    machineId: 'machine',
    versionId: 'version',
    schemaHash: 'hash',
    fields,
    issues: [],
    parameterLayout: hidden.map((fieldId) => ({
      fieldId,
      section: 'hidden',
      displayName: '隐藏选项',
      help: null,
      control: null,
      defaultValue: null,
    })),
    parameterControls: {},
    parameterPresentation: {},
    outputSizes: [],
    referenceTimelines: [],
    imageCrops: {},
    originalDefaults: {},
    sharedAssets: [],
  };
}

await test('hidden choices can be repaired only when their initial choice is unavailable', () => {
  const layout = form(
    [
      { ...field('choice', 'choice', 'template'), choices: ['other'] },
      field('internal', 'integer', 10),
    ],
    ['choice', 'internal'],
  );
  const unresolved = runParameterState(layout, null);
  assert.equal(unresolved.issues.get('choice')?.kind, 'choice');
  assert.equal(unresolved.locked.has('choice'), false);

  const draft = { choice: 'other', internal: 100 };
  const repaired = runParameterState(layout, draft);
  assert.equal(repaired.values.choice, 'other');
  assert.equal(repaired.values.internal, 10);
  assert.equal(repaired.issues.size, 0);
  assert.deepEqual(
    repaired.groups.hidden.map(({ id }) => id),
    ['choice', 'internal'],
  );

  layout.fields[0].choices = ['template', 'other'];
  const compatible = runParameterState(layout, draft);
  assert.equal(compatible.values.choice, 'template');
  assert.equal(compatible.locked.has('choice'), true);

  layout.fields[0].choices = [];
  const missing = runParameterState(layout, draft);
  assert(missing.locked.has('choice'));
  assert.match(missing.issues.get('choice')?.message ?? '', /切换工作机/);
});

await test('draft uploads and reference timings use the same issue calculation', () => {
  const input = form([
    field('source', 'image', null),
    field('duration', 'number', 5),
    field('guide', 'number', 5),
  ]);
  input.referenceTimelines = [
    {
      durationFieldId: 'duration',
      framesPerSecond: 24,
      minimumFrames: 5,
      frameStep: 17,
      frames: [{ imageFieldId: 'source', timeFieldId: 'guide' }],
    },
  ];
  const incomplete = runParameterState(input, { duration: 4.4 });
  assert.equal(incomplete.issues.get('source')?.kind, 'asset');
  assert.equal(incomplete.issues.get('guide')?.kind, 'timing');
  assert.equal(incomplete.frameCounts.get('duration'), 107);
  const source = { assetId: 'asset' };
  const fixed = runParameterState(input, { source, duration: 4.4, guide: 4.3 });
  assert.equal(fixed.issues.size, 0);
  assert(sameInputValue(fixed.values.source, { assetId: 'asset' }));
  assert(!sameInputValue(fixed.values.source, null));
});

await test('explicit overrides keep their values when editing is locked again', () => {
  const layout = form(
    [
      field('internal', 'integer', 32),
      { ...field('option', 'choice', 'original'), choices: ['original', 'different'] },
      field('prompt', 'string', 'original prompt'),
    ],
    ['internal', 'option'],
  );
  const draft = { internal: 123, prompt: 'user prompt' };
  // 重跑时字段初始值来自执行记录，和作者原始默认值可能不同。
  layout.originalDefaults.internal = 24;
  const unlocked = runParameterState(layout, draft, { editHidden: true });
  assert.equal(unlocked.locked.size, 0);
  assert.equal(unlocked.values.internal, 32);

  const hiddenValues = { internal: 40, option: 'different' };
  const relocked = runParameterState(layout, draft, { hiddenValues });
  assert(relocked.locked.has('internal') && relocked.locked.has('option'));
  assert.deepEqual([...relocked.changedHidden], ['internal', 'option']);
  assert.deepEqual(relocked.values, { internal: 40, option: 'different', prompt: 'user prompt' });

  const reset = { internal: undefined, option: undefined };
  const restored = runParameterState(layout, applyInputPatch(draft, reset), {
    hiddenValues: applyInputPatch(hiddenValues, reset),
  });
  assert.deepEqual(restored.values, { internal: 32, option: 'original', prompt: 'user prompt' });
  assert.equal(restored.changedHidden.size, 0);
});

await test('a hidden override incompatible with the selected work machine remains repairable', () => {
  const layout = form(
    [{ ...field('option', 'choice', 'original'), choices: ['original', 'alternative'] }],
    ['option'],
  );
  const hiddenValues = { option: 'different' };
  const incompatible = runParameterState(layout, null, { hiddenValues });
  assert.equal(incompatible.values.option, 'different');
  assert(!incompatible.locked.has('option'));
  assert.equal(incompatible.issues.get('option')?.kind, 'choice');
  const repaired = runParameterState(layout, null, { hiddenValues: { option: 'alternative' } });
  assert(repaired.locked.has('option'));
  assert.equal(repaired.issues.size, 0);
  layout.fields[0].choices = [];
  assert(runParameterState(layout, null, { hiddenValues, editHidden: true }).locked.has('option'));
});
