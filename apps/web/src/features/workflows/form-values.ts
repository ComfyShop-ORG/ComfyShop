/** 为运行表单合并工作机默认值和用户本次编辑的草稿。 */
import type { InputValue, WorkflowInput } from '@comfyshop/api-client';

/** 生成提交值。隐藏字段使用当前表单默认值，重跑表单的默认值来自历史记录。 */
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
