/** 按当前工作机读取输入定义，编辑本次参数，并向平台提交排队任务。 */
import { Fragment, lazy, Suspense, useState } from 'react';
import type { ReactNode } from 'react';
import { Link } from 'react-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ChevronDownIcon,
  ReloadIcon,
  ArrowRightIcon,
  PlayIcon,
  MixerHorizontalIcon,
} from '@radix-ui/react-icons';
import { Button, Collapsible, Field, IconButton, Input, Select } from '@comfyshop/ui';
import { ApiError } from '@comfyshop/api-client';
import type {
  InputValue,
  Workflow,
  ReplaySource,
  Task,
  WorkflowForm,
  WorkflowParameterDisplay,
} from '@comfyshop/api-client';
import { useMachines, useWorkspace } from '../../app/use-workspace';
import { authorPath } from '../../app/workflow-route';
import { ProfileAvatar } from '../../components/profile-avatar';
import { createRequestId } from '../../data/request-id';
import type { RequireAuth } from '../auth/login-dialog';
import { InputField } from './input-field';
import { applyInputPatch } from './form-values';
import { AutomaticSizeFields, RatioSizePreview } from './output-size';
import { promptWithAspect } from './output-specification';
import { workflowCategories } from '../../domain/workflow-categories';
import type { ParameterRow } from './parameter-layout';
import RunParameterDialog from './run-parameter-dialog';
import type { RunParameterDialogMode } from './run-parameter-dialog';
import { runParameterState } from './run-parameter-state';
import { workflowFormQuery } from './workflow-form-query';

const ParameterEditor = lazy(() => import('./parameter-editor'));

export type RunIntent = { fingerprint: string; key: string };

export function RunForm({
  formId,
  workflow,
  publishAction,
  taskSummary,
  selectedMachine,
  onMachineChange,
  executionCount,
  onExecutionCountChange,
  inputValues,
  onInputValuesChange,
  hiddenInputValues,
  onHiddenInputValuesChange,
  intent,
  onIntentChange,
  operations,
  onPendingChange,
  replaySource,
  onReset,
  requireAuth,
  onRun,
}: {
  /** 表单元素的 ID。表单之外的再次生成入口通过它提交同一份参数。 */
  formId: string;
  workflow: Workflow;
  publishAction?: ReactNode;
  taskSummary?: ReactNode;
  selectedMachine: string | null;
  onMachineChange: (id: string) => void;
  executionCount: number;
  onExecutionCountChange: (count: number) => void;
  inputValues: Record<string, InputValue> | null;
  onInputValuesChange: (
    update: (prior: Record<string, InputValue> | null) => Record<string, InputValue>,
  ) => void;
  hiddenInputValues: Record<string, InputValue>;
  onHiddenInputValuesChange: (
    update: (prior: Record<string, InputValue>) => Record<string, InputValue>,
  ) => void;
  intent?: RunIntent;
  onIntentChange: (intent: RunIntent | undefined) => void;
  operations: ReadonlySet<string>;
  onPendingChange: (operation: string, busy: boolean) => void;
  replaySource?: ReplaySource;
  onReset: () => void;
  requireAuth: RequireAuth;
  onRun: (task: Task) => void;
}) {
  const { api, workspace, state } = useWorkspace();
  const author = workflow.authorProfile.nickname ?? workflow.author;
  const queries = useQueryClient();
  const machines = useMachines();
  // 在线的工作机排在前面，同一状态内保持平台返回的顺序。
  const available = (machines.data?.items.filter((machine) => !machine.revoked) ?? []).toSorted(
    (a, b) => Number(b.online) - Number(a.online),
  );
  const defaultMachine = available.find(({ id }) => id === machines.data?.defaultMachineId);
  // 本次会话里上一次选过的工作机。只保存在内存缓存，不改变账户的默认工作机。
  const recentKey = ['run-machine', state.userId] as const;
  const recentMachine = useQuery({
    queryKey: recentKey,
    queryFn: () => null as string | null,
    enabled: false,
    staleTime: Infinity,
    gcTime: Infinity,
  }).data;
  const machine =
    available.find(({ id }) => id === (selectedMachine ?? recentMachine)) ?? defaultMachine;
  const machineId = machine?.id ?? '';
  const machineOptions = available.map((item) => ({
    value: item.id,
    label: `${item.name} · ${item.online ? (item.busy ? '忙碌' : '在线') : '离线'}`,
  }));
  const onlineAlternative =
    machine && !machine.online ? available.find((item) => item.online) : undefined;
  function chooseMachine(id: string) {
    queries.setQueryData(recentKey, id);
    onMachineChange(id);
    setError('');
  }
  // 编辑器格式的图不能直接执行，表单只在 API 格式下生成。
  const editorFormat = workflow.format === 'ui';
  const formKey = ['workflow-form', state.userId, workflow.id, workflow.versionId] as const;
  const readForm = (id: string) => workflowFormQuery(api, formKey, id, replaySource);
  const schema = useQuery({
    ...readForm(machineId),
    enabled: !!state.user && !!machineId && !editorFormat,
  });
  const submitOperation = formId + ':submit';
  const errorId = formId + '-error';
  const submitting = operations.has(submitOperation);
  const pending = operations.size > 0;
  const [error, setError] = useState('');
  const [parameterPanel, setParameterPanel] = useState<RunParameterDialogMode>(null);
  const {
    groups: parameters,
    rows,
    values,
    issues,
    frameCounts,
    changedHidden,
  } = runParameterState(schema.data, inputValues, { hiddenValues: hiddenInputValues });
  const canEditParameters = workflow.owner === state.userId && rows.length > 0;
  const sizes = schema.data?.outputSizes ?? [];
  const visibleRows = new Map(
    [...parameters.default, ...parameters.advanced].map((row) => [row.id, row]),
  );
  const frameTimes = new Map<string, string | null>();
  const pairedTimeIds = new Set<string>();
  const timingDetails = new Map<string, string>();
  for (const timeline of schema.data?.referenceTimelines ?? []) {
    const { durationFieldId, framesPerSecond } = timeline;
    const count = frameCounts.get(durationFieldId);
    if (count != null) {
      timingDetails.set(durationFieldId, `参考帧按 ${framesPerSecond} 帧/秒定位，共 ${count} 帧。`);
    }
    for (const { imageFieldId, timeFieldId } of timeline.frames) {
      if (!frameTimes.has(imageFieldId)) {
        frameTimes.set(imageFieldId, timeFieldId);
        if (timeFieldId && visibleRows.has(timeFieldId)) pairedTimeIds.add(timeFieldId);
      }
    }
  }
  const advancedRows = parameters.advanced.filter((row) => !pairedTimeIds.has(row.id));
  const boundPrompts = new Map<string, string>();
  for (const size of sizes) {
    if (
      size.kind === 'ratio' &&
      size.promptFieldId &&
      (visibleRows.has(size.promptFieldId) ||
        changedHidden.has(size.promptFieldId) ||
        changedHidden.has(size.ratioFieldId))
    ) {
      boundPrompts.set(size.promptFieldId, size.ratioFieldId);
    }
  }
  const [sizeReset, setSizeReset] = useState(0);
  const sharedAssets = new Map(schema.data?.sharedAssets?.map((asset) => [asset.id, asset]));
  const hasIssues = schema.isError || !!schema.data?.issues.length;
  // 默认区为空或高级区里有需要处理的选项时展开高级参数，用户手动开合后以用户为准。
  const unavailableCount = [...issues.values()].filter((issue) => issue.kind === 'choice').length;
  const [countText, setCountText] = useState<string>();
  const [countSeen, setCountSeen] = useState(executionCount);
  const replayKey = JSON.stringify(replaySource ?? null);
  const [replaySeen, setReplaySeen] = useState(replayKey);
  if (countSeen !== executionCount || replaySeen !== replayKey) {
    // 次数在别处被改写或载入了重跑参数时，丢掉框里未生效的输入。
    setCountSeen(executionCount);
    setReplaySeen(replayKey);
    if (countText !== undefined && Number(countText) !== executionCount) setCountText(undefined);
  }
  const countInvalid = countText !== undefined && Number(countText) !== executionCount;
  const [advancedChoice, setAdvancedChoice] = useState<boolean>();
  const advancedOpen =
    advancedChoice ??
    (parameters.default.length === 0 ||
      parameters.advanced.some((field) => issues.get(field.id)?.kind === 'choice'));
  function change(id: string, value: InputValue) {
    setError('');
    onInputValuesChange((prior) => ({ ...prior, [id]: value }));
  }
  function uploadState(id: string, busy: boolean) {
    onPendingChange(formId + ':asset:' + id, busy);
  }
  function renderField(field: ParameterRow, primary: boolean) {
    const value = values[field.id];
    const issue = issues.get(field.id);
    const pairedTime = frameTimes.get(field.id);
    const hiddenTiming =
      pairedTime && !visibleRows.has(pairedTime) ? issues.get(pairedTime) : undefined;
    return (
      <InputField
        key={field.id}
        field={{ ...field, primary }}
        value={value}
        linkedAspect={boundPrompts.has(field.id)}
        sharedAsset={
          value && typeof value === 'object' ? sharedAssets.get(value.assetId) : undefined
        }
        issue={(issue?.kind === 'asset' ? undefined : issue?.message) ?? hiddenTiming?.message}
        crops={schema.data?.imageCrops?.[field.id]}
        onChange={(value) => change(field.id, value)}
        onBusy={uploadState}
      />
    );
  }
  function renderGroup(rows: ParameterRow[], primary: boolean) {
    const positions = new Map(rows.map((row, index) => [row.id, index]));
    return rows.map((row, index) => {
      if (pairedTimeIds.has(row.id)) return null;
      if (frameTimes.has(row.id)) {
        const timeId = frameTimes.get(row.id);
        const timing = timeId && visibleRows.get(timeId);
        return (
          <div key={row.id} className="reference-frame-fields">
            {renderField(row, primary)}
            {timing && renderField(timing, primary)}
            {timeId === null && <p className="form-hint">作为整段视频的基础参考。</p>}
          </div>
        );
      }
      const automatic = sizes.find(
        (size): size is Extract<WorkflowForm['outputSizes'][number], { kind: 'automatic' }> =>
          size.kind === 'automatic' &&
          (row.id === size.widthFieldId || row.id === size.heightFieldId),
      );
      if (automatic) {
        const width = positions.get(automatic.widthFieldId);
        const height = positions.get(automatic.heightFieldId);
        if (width !== undefined && height !== undefined) {
          if (index !== Math.min(width, height)) return null;
          return (
            <AutomaticSizeFields
              key={JSON.stringify([row.id, machineId, replayKey, sizeReset])}
              id={`size-${row.id}`}
              width={values[automatic.widthFieldId]}
              height={values[automatic.heightFieldId]}
              usesReference={automatic.usesReference}
              onAutomatic={() => {
                setError('');
                onInputValuesChange((prior) => ({
                  ...prior,
                  [automatic.widthFieldId]: 0,
                  [automatic.heightFieldId]: 0,
                }));
              }}
            >
              {renderField(rows[width], primary)}
              {renderField(rows[height], primary)}
            </AutomaticSizeFields>
          );
        }
      }
      const ratio = sizes.find(
        (size): size is Extract<WorkflowForm['outputSizes'][number], { kind: 'ratio' }> =>
          size.kind === 'ratio' &&
          row.id ===
            (visibleRows.has(size.megapixelsFieldId) ? size.megapixelsFieldId : size.ratioFieldId),
      );
      return (
        <Fragment key={row.id}>
          {renderField(row, primary)}
          {timingDetails.has(row.id) && <p className="form-hint">{timingDetails.get(row.id)}</p>}
          {ratio && (
            <RatioSizePreview
              ratio={values[ratio.ratioFieldId]}
              megapixels={values[ratio.megapixelsFieldId]}
              multiple={values[ratio.multipleFieldId]}
              roundTo={ratio.roundTo}
              latentMultiple={ratio.latentMultiple}
              modelMultiple={ratio.modelMultiple}
            />
          )}
        </Fragment>
      );
    });
  }
  async function saveParameterLayout(layout: WorkflowParameterDisplay[]) {
    await api.saveWorkflowParameterLayout(workflow.id, workflow.versionId, machineId, layout);
    await queries.invalidateQueries({ queryKey: formKey });
  }
  function focusField(id: string) {
    if (advancedRows.some((row) => row.id === id)) setAdvancedChoice(true);
    requestAnimationFrame(() => {
      const input = document.getElementById(`input-${id}`);
      input?.scrollIntoView({ block: 'center' });
      input?.focus({ preventScroll: true });
    });
  }
  async function submit() {
    if (!state.user || !machineId || !schema.data || hasIssues || pending || parameterPanel) return;
    // 输入框里的次数无效时不提交，避免悄悄沿用上一次有效的次数。
    if (countInvalid) {
      setError('执行次数需为 1–32 的整数');
      document.getElementById('run-count')?.focus();
      return;
    }
    const invalid = issues.entries().next().value;
    if (invalid) {
      const [id, issue] = invalid;
      if (visibleRows.has(id)) {
        setError(issue.message);
        focusField(id);
      } else {
        setError('');
        setParameterPanel('issues');
      }
      return;
    }
    const submittedValues = { ...values };
    for (const [promptId, ratioId] of boundPrompts) {
      // 原样重跑使用历史记录，用户重新编辑提示词或比例时再同步。
      if (
        !replaySource ||
        Object.hasOwn(inputValues ?? {}, promptId) ||
        Object.hasOwn(inputValues ?? {}, ratioId) ||
        changedHidden.has(promptId) ||
        changedHidden.has(ratioId)
      ) {
        submittedValues[promptId] = promptWithAspect(values[promptId], values[ratioId]);
      }
    }
    const body = {
      workflowId: workflow.id,
      versionId: workflow.versionId,
      machineId,
      executionCount,
      inputValues: submittedValues,
      inputSchemaHash: schema.data.schemaHash,
      sourceExecutionId: replaySource?.executionId,
      sourceWorkId: replaySource?.workId,
    };
    onPendingChange(submitOperation, true);
    setError('');
    try {
      // 同参数重试复用请求键。参数变化后创建新键，避免把两次生成意图合为一个任务。
      const fingerprint = JSON.stringify(body);
      const attempt =
        intent?.fingerprint === fingerprint ? intent : { fingerprint, key: createRequestId() };
      onIntentChange(attempt);
      onRun(await workspace.run({ ...body, idempotencyKey: attempt.key }));
      onIntentChange(undefined);
    } catch (error) {
      // 工作机的输入配置在这期间变了：重新读取表单，确认参数后再提交。
      if (error instanceof ApiError && error.status === 409) {
        const refreshed = await schema.refetch();
        if (refreshed.data && refreshed.data.schemaHash !== body.inputSchemaHash) {
          setError('工作机输入配置已更新，参数已刷新，请确认后重新提交');
          return;
        }
      }
      setError(error instanceof Error ? error.message : '提交失败');
    } finally {
      onPendingChange(submitOperation, false);
    }
  }
  return (
    <div className="run-form">
      <div className="run-form-scroll">
        <div className="workflow-meta">
          <span className="eyebrow">
            {workflowCategories.find(({ value }) => value === workflow.category)?.label}
          </span>
          <h1>{workflow.name}</h1>
          <div className="author-line">
            <ProfileAvatar name={author} src={workflow.authorProfile.avatarUrl} />
            <Link
              className="author-link"
              to={authorPath(workflow.author)}
              aria-label={`查看 ${author} 的工作流`}
            >
              {author}
            </Link>
            <span className="meta-status">{workflow.published ? '已公开' : '私有'}</span>
          </div>
          {workflow.description && <p className="workflow-description">{workflow.description}</p>}
          {workflow.published && (
            <dl className="workflow-stats">
              <div>
                <dt>运行</dt>
                <dd>{workflow.runs}</dd>
              </div>
              <div>
                <dt>收藏</dt>
                <dd>{workflow.popularity}</dd>
              </div>
              <div>
                <dt>版本</dt>
                <dd>v{workflow.version}</dd>
              </div>
            </dl>
          )}
          {(publishAction || canEditParameters) && (
            <div className="workflow-actions">
              {publishAction}
              {canEditParameters && (
                <Suspense fallback={null}>
                  <ParameterEditor
                    groups={parameters}
                    disabled={pending}
                    onSave={saveParameterLayout}
                  />
                </Suspense>
              )}
            </div>
          )}
        </div>
        {state.user && (
          <form
            id={formId}
            className="run-fields"
            noValidate
            onSubmit={(event) => {
              event.preventDefault();
              void submit();
            }}
          >
            {available.length ? (
              <Field
                label="本次执行工作机"
                htmlFor="run-machine"
                detail={machine && machine === defaultMachine ? '默认' : undefined}
              >
                <Select
                  id="run-machine"
                  label="本次执行工作机"
                  value={machineId || 'none'}
                  // 上传素材期间切换工作机会重建参数表单，正在上传的文件会丢失。
                  disabled={pending}
                  onValueChange={chooseMachine}
                  options={[
                    ...(!machineId ? [{ value: 'none', label: '选择工作机', disabled: true }] : []),
                    ...machineOptions,
                  ]}
                />
                {machine && !machine.online && (
                  <p className="form-hint machine-hint">
                    工作机离线，提交后将排队等待它上线。
                    {onlineAlternative && (
                      <Button
                        size="small"
                        variant="ghost"
                        disabled={pending}
                        onClick={() => chooseMachine(onlineAlternative.id)}
                      >
                        改用 {onlineAlternative.name}
                      </Button>
                    )}
                  </p>
                )}
              </Field>
            ) : machines.isPending ? (
              <p className="form-hint" role="status">
                正在读取工作机
              </p>
            ) : !machines.error ? (
              <div className="inline-status run-machine-empty">
                生成在你自己的 ComfyUI 上运行。添加并连接工作机后，这里会出现参数。
                <Button asChild size="small" variant="primary">
                  <Link to="/machines">去工作机</Link>
                </Button>
              </div>
            ) : null}
            {editorFormat && (
              <p className="inline-status run-machine-empty" role="status">
                {workflow.owner === state.userId
                  ? '这是编辑器格式的工作流，运行需要 API 格式。在 ComfyUI 导出 API 格式后，通过上方「编辑工作流」上传新版本。'
                  : '这个版本是编辑器格式，暂时不能运行。'}
              </p>
            )}
            {machine && !editorFormat && schema.isPending && (
              <p className="form-hint" role="status">
                正在读取输入参数
              </p>
            )}
            {unavailableCount > 0 && (
              <div className="form-error" role="alert">
                <span>当前工作机有 {unavailableCount} 项参数需要处理。</span>
                <Button
                  size="small"
                  variant="ghost"
                  disabled={pending}
                  onClick={() => setParameterPanel('issues')}
                >
                  查看待处理
                </Button>
              </div>
            )}
            {schema.data && (
              <div className="form-section-heading">
                <span>输入</span>
                <IconButton
                  label="重置参数"
                  onClick={() => {
                    setCountText(undefined);
                    setSizeReset((prior) => prior + 1);
                    onReset();
                  }}
                >
                  <ReloadIcon />
                </IconButton>
              </div>
            )}
            {renderGroup(parameters.default, true)}
            {advancedRows.length > 0 && (
              <Collapsible.Root
                className="advanced"
                open={advancedOpen}
                onOpenChange={setAdvancedChoice}
              >
                <Collapsible.Trigger asChild>
                  <Button variant="ghost" className="advanced-trigger">
                    <MixerHorizontalIcon />
                    高级参数
                    <ChevronDownIcon />
                  </Button>
                </Collapsible.Trigger>
                <Collapsible.Content className="ui-collapsible advanced-content">
                  {renderGroup(advancedRows, false)}
                </Collapsible.Content>
              </Collapsible.Root>
            )}
            {schema.data && (
              <Field label="执行次数" htmlFor="run-count" detail="1–32 次">
                <Input
                  id="run-count"
                  type="number"
                  inputMode="numeric"
                  min={1}
                  max={32}
                  step={1}
                  value={countText ?? executionCount}
                  onChange={(event) => {
                    // 输入过程中允许暂时为空，只有 1–32 的整数才写入本次提交。
                    setCountText(event.target.value);
                    setError('');
                    const count = Number(event.target.value);
                    if (Number.isInteger(count) && count >= 1 && count <= 32)
                      onExecutionCountChange(count);
                  }}
                  aria-invalid={countInvalid}
                  aria-describedby={countInvalid && error ? errorId : undefined}
                  // 有效时恢复显示已记录的次数；无效内容保留在框里，提交时提示。
                  onBlur={() => {
                    if (Number(countText) === executionCount) setCountText(undefined);
                  }}
                />
              </Field>
            )}
            {schema.data?.issues.map((issue) => (
              <p className="form-error" key={issue} role="alert">
                {issue}
              </p>
            ))}
            {(schema.error || machines.error) && (
              <div className="form-error" role="alert">
                {schema.error?.message || machines.error?.message}
                <Button
                  variant="ghost"
                  size="small"
                  onClick={() => {
                    void machines.refetch();
                    void schema.refetch();
                  }}
                >
                  刷新
                </Button>
              </div>
            )}
          </form>
        )}
      </div>
      <div className="run-footer">
        {error && (
          <p id={errorId} className="form-error" role="alert">
            {error}
          </p>
        )}
        {taskSummary}
        {changedHidden.size > 0 && (
          <Button
            size="small"
            variant="ghost"
            className="run-hidden-changes"
            disabled={pending}
            onClick={() => setParameterPanel('hidden-changed')}
          >
            本次已修改 {changedHidden.size} 个隐藏参数
          </Button>
        )}
        <div className="run-action-buttons">
          {!!state.user && rows.length > 0 && (
            <RunParameterDialog
              mode={parameterPanel}
              issueCount={issues.size}
              disabled={pending}
              initialMachineId={machineId}
              machines={machineOptions}
              initialDraft={inputValues}
              initialHiddenDraft={hiddenInputValues}
              readForm={readForm}
              onApply={(nextMachineId, patch, hiddenPatch) => {
                if (nextMachineId !== machineId) chooseMachine(nextMachineId);
                if (Object.keys(patch).length)
                  onInputValuesChange((prior) => applyInputPatch(prior, patch));
                if (Object.keys(hiddenPatch).length)
                  onHiddenInputValuesChange((prior) => applyInputPatch(prior, hiddenPatch));
                setError('');
              }}
              onOpenChange={setParameterPanel}
            />
          )}
          <Button
            className="generate-button"
            form={state.user ? formId : undefined}
            type={state.user ? 'submit' : 'button'}
            variant="primary"
            onClick={
              state.user
                ? undefined
                : (event) => requireAuth(event.currentTarget, undefined, '登录后用自己的工作机生成')
            }
            disabled={pending || (!!state.user && (!schema.data || hasIssues))}
          >
            <PlayIcon />
            <span>{submitting ? '提交中' : state.user ? '生成' : '登录后生成'}</span>
            <ArrowRightIcon />
          </Button>
        </div>
      </div>
    </div>
  );
}
