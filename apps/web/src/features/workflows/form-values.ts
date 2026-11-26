/** 为运行表单合并工作机默认值和用户本次编辑的草稿。 */
import type { InputValue, WorkflowInput } from '@comfyshop/api-client';

export type InputPatch = Record<string, InputValue | undefined>;

/** undefined 恢复初始值，null 保留为用户主动清空的值。 */
export function applyInputPatch(
  prior: Record<string, InputValue> | null,
  patch: InputPatch,
): Record<string, InputValue> {
  const values = { ...prior };
  for (const [id, value] of Object.entries(patch)) {
    if (value === undefined) delete values[id];
    else values[id] = value;
  }
  return values;
}

/** 生成提交值。指定字段使用表单默认值，重跑表单的默认值来自历史记录。 */
export function formValues(
  fields: ReadonlyArray<Pick<WorkflowInput, 'id' | 'default'>>,
  draft: Record<string, InputValue> | null,
  hidden?: ReadonlySet<string>,
): Record<string, InputValue> {
  return Object.fromEntries(
    fields.map((field) => [
      field.id,
      draft && !hidden?.has(field.id) && Object.hasOwn(draft, field.id)
        ? draft[field.id]
        : field.default,
    ]),
  );
}
