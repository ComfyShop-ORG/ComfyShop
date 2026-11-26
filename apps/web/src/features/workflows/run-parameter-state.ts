import { t } from '../../app/i18n.ts';
import type { InputValue, WorkflowFormData } from '@comfyshop/api-client';
import { formValues } from './form-values.ts';
import { groupParameters, isAssetInput, unavailableChoice } from './parameter-layout.ts';
import { referenceFrameCount, referenceTimeIssue } from './output-specification.ts';

type RunParameterIssue = { kind: 'asset' | 'choice' | 'crop' | 'timing'; message: string };

export function sameInputValue(left: InputValue | undefined, right: InputValue | undefined) {
  return (
    left === right ||
    (left !== null &&
      right !== null &&
      typeof left === 'object' &&
      typeof right === 'object' &&
      left.assetId === right.assetId)
  );
}

/** 为运行表单和本次参数面板计算同一份可编辑字段、实际输入和字段问题。 */
export function runParameterState(
  form: WorkflowFormData | undefined,
  draft: Record<string, InputValue> | null,
  {
    hiddenValues = {},
    editHidden = false,
  }: { hiddenValues?: Record<string, InputValue>; editHidden?: boolean } = {},
) {
  const groups = groupParameters(
    form?.fields ?? [],
    form?.parameterLayout ?? [],
    form?.parameterControls ?? {},
    form?.originalDefaults ?? {},
    form?.parameterPresentation ?? {},
  );
  const rows = [...groups.default, ...groups.advanced, ...groups.hidden];
  // 普通草稿里的隐藏值只用于修复失效选项。用户明确编辑的隐藏值独立保存。
  const useDefaults = new Set(
    groups.hidden
      .filter((row) => !unavailableChoice(row, row.default) || row.choices.length === 0)
      .map((row) => row.id),
  );
  const values = formValues(form?.fields ?? [], draft, useDefaults);
  const locked = new Set<string>();
  const changedHidden = new Set<string>();
  for (const row of groups.hidden) {
    const overridden = Object.hasOwn(hiddenValues, row.id);
    if (overridden) values[row.id] = hiddenValues[row.id];
    const value = values[row.id];
    if (!sameInputValue(value, row.default)) changedHidden.add(row.id);
    const noOptions = row.kind === 'choice' && row.choices.length === 0;
    const needsChoice = (!overridden && !useDefaults.has(row.id)) || unavailableChoice(row, value);
    if (noOptions || (!editHidden && !needsChoice)) locked.add(row.id);
  }
  const issues = new Map<string, RunParameterIssue>();
  const frameCounts = new Map<string, number>();
  for (const timeline of form?.referenceTimelines ?? []) {
    const { durationFieldId, framesPerSecond } = timeline;
    const count = referenceFrameCount(values[durationFieldId], timeline);
    if (count == null) {
      issues.set(durationFieldId, {
        kind: 'timing',
        message: t('runParameterState.enterAValidTargetDuration'),
      });
      continue;
    }
    frameCounts.set(durationFieldId, count);
    for (const { timeFieldId } of timeline.frames) {
      if (!timeFieldId) continue;
      const message = referenceTimeIssue(values[timeFieldId], count, framesPerSecond);
      if (message) issues.set(timeFieldId, { kind: 'timing', message });
    }
  }
  for (const row of rows) {
    const value = values[row.id];
    if (!row.optional && isAssetInput(row.kind) && (!value || typeof value !== 'object')) {
      issues.set(row.id, {
        kind: 'asset',
        message: t('runParameterState.upload', row.displayName || row.label),
      });
    }
  }
  for (const row of rows) {
    if (unavailableChoice(row, values[row.id])) {
      issues.set(row.id, {
        kind: 'choice',
        message: row.choices.length
          ? t('runParameterState.theCurrentValueForIsUnavailable', row.displayName || row.label)
          : t('runParameterState.noOptionsAreAvailableForSelect', row.displayName || row.label),
      });
    }
  }
  return { groups, rows, values, locked, changedHidden, issues, frameCounts };
}
