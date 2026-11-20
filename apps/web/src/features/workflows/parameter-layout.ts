/** 把工作机返回的字段按作者的展示配置分组。其余字段沿用自动分组。 */
import type {
  InputValue,
  WorkflowForm,
  WorkflowInput,
  WorkflowParameterDisplay,
} from '@comfyshop/api-client';

export type ParameterSection = WorkflowParameterDisplay['section'];
export type ParameterRow = WorkflowInput &
  Partial<Pick<WorkflowParameterDisplay, 'displayName' | 'help' | 'control' | 'defaultValue'>> & {
    controls?: WorkflowForm['parameterControls'][string];
    originalDefault?: WorkflowForm['originalDefaults'][string];
  };
export type ParameterGroups = Record<ParameterSection, ParameterRow[]>;

export const parameterSections = [
  { value: 'default', label: '默认展示' },
  { value: 'advanced', label: '高级展示' },
  { value: 'hidden', label: '不显示' },
] as const;

export function canHideParameter(field: WorkflowInput) {
  return field.kind !== 'image' && field.kind !== 'video';
}

/** 选项字段的当前值是否不在所选工作机提供的选项里，例如工作机缺少该模型。 */
export function unavailableChoice(field: WorkflowInput, value: InputValue) {
  return (
    field.kind === 'choice' &&
    !field.choices.some((choice) => JSON.stringify(choice) === JSON.stringify(value))
  );
}

export function groupParameters(
  fields: readonly WorkflowInput[],
  layout: readonly WorkflowParameterDisplay[],
  controls: WorkflowForm['parameterControls'],
  originalDefaults: WorkflowForm['originalDefaults'],
): ParameterGroups {
  const groups: ParameterGroups = { default: [], advanced: [], hidden: [] };
  const remaining = new Map(
    fields.map((field) => [
      field.id,
      { ...field, controls: controls[field.id], originalDefault: originalDefaults[field.id] },
    ]),
  );
  for (const entry of layout) {
    const field = remaining.get(entry.fieldId);
    if (!field) continue;
    remaining.delete(entry.fieldId);
    // 工作机目录可能有差异。当前工作机识别出的必传素材始终提供上传入口。
    const section =
      entry.section === 'hidden' && !canHideParameter(field) ? 'default' : entry.section;
    groups[section].push({
      ...field,
      displayName: entry.displayName,
      help: entry.help,
      control: entry.control,
      defaultValue: entry.defaultValue,
    });
  }
  // 作者没有安排的字段：提示词与素材默认展示，有名称的进入高级参数，其余冷门参数不显示。
  // 当前工作机缺少默认选项的字段需要用户处理，保持可见。
  for (const field of remaining.values()) {
    const obscure =
      !field.named && canHideParameter(field) && !unavailableChoice(field, field.default);
    groups[field.primary ? 'default' : obscure ? 'hidden' : 'advanced'].push(field);
  }
  return groups;
}
