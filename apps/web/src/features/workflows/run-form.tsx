/** 按当前工作机读取输入定义，编辑本次参数，并向平台提交排队任务。 */
import { t } from '../../app/i18n.ts';
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
  GenerationInputs,
  InputValue,
  Workflow,
  ReplaySource,
  Task,
  WorkflowForm,
  WorkflowParameterDisplay,
} from '@comfyshop/api-client';
import { useMachines, useWorkspace } from '../../app/use-workspace';
import { workspaceKey } from '../../app/workspace-scope';
import { machineOption } from '../../data/machine-option';
import { createRequestId } from '../../data/request-id';
import type { RequireAuth } from '../auth/login-dialog';
import { InputField } from './input-field';
import { applyInputPatch } from './form-values';
import type { InputPatch } from './form-values';
import { AutomaticSizeFields, RatioSizePreview } from './output-size';
import { promptWithAspect } from './output-specification';
import { placementEditorFor } from './placement-fields';
import { cropEditorFor } from './crop-box';
import { outpaintEditorFor } from './outpaint-fields';
import { maskEditorFor } from './mask-fields';
import type { ParameterRow } from './parameter-layout';
import RunParameterDialog from './run-parameter-dialog';
import type { RunParameterDialogMode } from './run-parameter-dialog';
import { useRunParameters } from './run-assets';
import { RunCostEstimate } from './run-cost-estimate';
import { workflowFormQuery } from './workflow-form-query';
import { WorkflowMetadata } from './workflow-metadata';
import { ProjectSelect } from '../projects/project-select';

const ParameterEditor = lazy(() => import('./parameter-editor'));

export type RunIntent = { fingerprint: string; key: string };

export function RunForm({
  formId,
  viewer,
  workflow,
  initialProjectId,
  switchingVersion,
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
  viewer: ReactNode;
  workflow: Workflow;
  initialProjectId?: string;
  switchingVersion: boolean;
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
  const { api, workspace, state, workspaceScope, workspaceTeam, canManageWorkspace } =
    useWorkspace();
  const queries = useQueryClient();
  const [projectId, setProjectId] = useState<string | null>(initialProjectId ?? null);
  const platformManaged = workflow.worker.connection === 'platform';
  const machines = useMachines(!platformManaged);
  // 在线的工作机排在前面，同一状态内保持平台返回的顺序。
  const available = (
    platformManaged
      ? []
      : (machines.data?.items.filter(
          (machine) =>
            !machine.revoked &&
            machine.worker.kind === workflow.worker.kind &&
            machine.worker.scope === workflow.worker.scope,
        ) ?? [])
  ).toSorted((a, b) => Number(b.online) - Number(a.online));
  const defaultMachine = available.find(({ id }) => id === machines.data?.defaultMachineId);
  // 本次会话里上一次选过的工作机。只保存在内存缓存，不改变账户的默认工作机。
  const recentKey = [
    'run-machine',
    state.userId,
    workflow.worker.kind,
    workflow.worker.scope,
    ...workspaceKey(workspaceScope),
  ] as const;
  const recentMachine = useQuery({
    queryKey: recentKey,
    queryFn: () => null as string | null,
    enabled: false,
    staleTime: Infinity,
    gcTime: Infinity,
  }).data;
  const machine =
    available.find(({ id }) => id === (selectedMachine ?? recentMachine)) ??
    defaultMachine ??
    (workflow.worker.connection === 'account' && available.length === 1 ? available[0] : undefined);
  const machineId = machine?.id ?? '';
  const machineOptions = available.map(machineOption);
  const onlineAlternative =
    available.find((item) => item.online && !item.paused) ?? available.find((item) => item.online);
  function chooseMachine(id: string) {
    queries.setQueryData(recentKey, id);
    onMachineChange(id);
    setError('');
  }
  // 编辑器格式的图不能直接执行，表单只在 API 格式下生成。
  const editorFormat = workflow.format === 'ui';
  const formKey = [
    'workflow-form',
    state.userId,
    workflow.id,
    workflow.versionId,
    ...workspaceKey(workspaceScope),
  ] as const;
  const readForm = (id: string) =>
    workflowFormQuery(api, formKey, id, replaySource, platformManaged);
  const schema = useQuery({
    ...readForm(machineId),
    enabled: !!state.user && (platformManaged || !!machineId) && !editorFormat,
  });
  const submitOperation = formId + ':submit';
  const errorId = formId + '-error';
  const blockId = formId + '-block';
  const issueId = formId + '-issue';
  const submitting = operations.has(submitOperation);
  const pending = operations.size > 0;
  const [error, setError] = useState('');
  const [parameterPanel, setParameterPanel] = useState<RunParameterDialogMode>(null);
  const {
    groups: parameters,
    rows,
    values,
    visibleRows,
    issues,
    frameCounts,
    changedHidden,
    sharedAssets,
    checkingCrops,
  } = useRunParameters(schema.data, inputValues, { hiddenValues: hiddenInputValues });
  const ownsWorkflow = workspaceTeam
    ? workflow.teamId === workspaceTeam.id
    : !workflow.teamId && workflow.owner === state.userId;
  const canEditParameters = ownsWorkflow && rows.length > 0;
  const sizes = schema.data?.outputSizes ?? [];
  const frameTimes = new Map<string, string | null>();
  const pairedTimeIds = new Set<string>();
  const timingDetails = new Map<string, string>();
  for (const timeline of schema.data?.referenceTimelines ?? []) {
    const { durationFieldId, framesPerSecond } = timeline;
    const count = frameCounts.get(durationFieldId);
    if (count != null) {
      timingDetails.set(
        durationFieldId,
        t('runForm.referenceFramesAreIndexedAtFps', framesPerSecond, count),
      );
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
  const hasIssues = schema.isError || !!schema.data?.issues.length;
  const machineBlocked = !!state.user && !platformManaged && !editorFormat && !machine?.online;
  const machineReadFailed = machines.isError && !machines.data;
  const needsMachineSetup = machineBlocked && machines.isSuccess && !available.length;
  const machineSetupLabel =
    workflow.worker.connection === 'account'
      ? canManageWorkspace
        ? t('connection.add', workflow.worker.label)
        : t('runForm.viewWorkMachines')
      : t('runForm.connectWorkMachine');
  let blockMessage = '';
  if (state.user) {
    if (editorFormat) blockMessage = t('runForm.generationRequiresTheApiFormatOf');
    else if (machineBlocked) {
      if (machines.isPending) blockMessage = t('runForm.loadingWorkMachines');
      else if (machineReadFailed) blockMessage = t('runForm.couldNotLoadWorkMachines');
      else if (machine) blockMessage = t('runForm.isOffline', machine.name);
      else if (onlineAlternative) blockMessage = t('runForm.selectTheWorkMachineForThis');
      else if (workflow.worker.connection === 'account') {
        const type = machines.data?.connectionTypes.find(
          (item) => item.kind === workflow.worker.kind,
        );
        const scope = workflow.worker.scope ?? '';
        blockMessage = t('connection.noMatch', workflow.worker.label, type?.sites[scope] ?? scope);
      } else
        blockMessage = available.length
          ? t('runForm.noWorkMachinesAreOnline')
          : t('runForm.connectAWorkMachineToContinue');
    } else if (checkingCrops) blockMessage = t('runForm.checkingImageDimensions');
    else if (schema.isPending) blockMessage = t('runForm.loadingInputs');
    else if (hasIssues && !platformManaged) blockMessage = t('runForm.fixTheSelectedWorkMachineS');
  }
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
  const countIssue = countInvalid ? t('runForm.enterAWholeNumberFromTo') : '';
  const firstIssue = issues.entries().next().value;
  const issueHint =
    state.user && schema.data && !hasIssues && !blockMessage && !pending
      ? countIssue || firstIssue?.[1].message
      : undefined;
  const [advancedChoice, setAdvancedChoice] = useState<boolean>();
  const advancedOpen =
    advancedChoice ??
    (parameters.default.length === 0 ||
      parameters.advanced.some((field) => issues.get(field.id)?.kind === 'choice'));
  function changeInputs(patch: InputPatch) {
    if (Object.keys(patch).length) onInputValuesChange((prior) => applyInputPatch(prior, patch));
    setError('');
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
        maxAssetBytes={schema.data?.maxAssetBytes}
        linkedAspect={boundPrompts.has(field.id)}
        sharedAsset={
          value && typeof value === 'object' ? sharedAssets.get(value.assetId) : undefined
        }
        issue={(issue?.kind === 'asset' ? undefined : issue?.message) ?? hiddenTiming?.message}
        crops={schema.data?.imageCrops?.[field.id]}
        crop={cropEditorFor(field, visibleRows, values, changeInputs)}
        outpaint={outpaintEditorFor(field, visibleRows, values, changeInputs)}
        placement={placementEditorFor(field, visibleRows, values, sharedAssets, changeInputs)}
        mask={maskEditorFor(field, visibleRows, values, sharedAssets, changeInputs)}
        onChange={(value) => changeInputs({ [field.id]: value })}
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
            {timeId === null && (
              <p className="form-hint">{t('runForm.usedAsTheReferenceForThe')}</p>
            )}
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
    await api.saveWorkflowParameterLayout(
      workflow.id,
      workflow.versionId,
      platformManaged ? undefined : machineId,
      layout,
    );
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
  function generationInputs(schemaHash: string): GenerationInputs {
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
    return {
      workflowId: workflow.id,
      versionId: workflow.versionId,
      inputValues: submittedValues,
      inputSchemaHash: schemaHash,
      sourceExecutionId: replaySource?.executionId,
      sourceWorkId: replaySource?.workId,
    };
  }

  async function submit() {
    if (!state.user || pending || parameterPanel || checkingCrops || switchingVersion) return;
    if (!platformManaged && !machine?.online) {
      setError(t('runForm.selectAnOnlineWorkMachineBefore'));
      return;
    }
    if (!schema.data || hasIssues) return;
    // 输入框里的次数无效时不提交，避免悄悄沿用上一次有效的次数。
    if (countInvalid) {
      setError(countIssue);
      document.getElementById('run-count')?.focus();
      return;
    }
    if (firstIssue) {
      const [id, issue] = firstIssue;
      if (visibleRows.has(id)) {
        setError(issue.message);
        focusField(id);
      } else {
        setError('');
        setParameterPanel('issues');
      }
      return;
    }
    const body = {
      ...generationInputs(schema.data.schemaHash),
      machineId: platformManaged ? undefined : machineId,
      executionCount,
      projectId: projectId ?? undefined,
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
      // 工作机可能在填写参数期间掉线或更新了输入定义。
      if (!platformManaged && error instanceof ApiError && error.status === 409) {
        const [refreshedMachines, refreshed] = await Promise.all([
          machines.refetch(),
          schema.refetch(),
        ]);
        const current = refreshedMachines.data?.items.find(({ id }) => id === machineId);
        if (
          current?.online &&
          refreshed.data &&
          refreshed.data.schemaHash !== body.inputSchemaHash
        ) {
          setError(t('runForm.theWorkMachineSInputConfiguration'));
          return;
        }
      }
      setError(error instanceof Error ? error.message : t('runForm.couldNotSubmit'));
    } finally {
      onPendingChange(submitOperation, false);
    }
  }

  return (
    <div className="workflow-dialog-body" inert={switchingVersion}>
      <div className="workflow-edit-scroll">
        {viewer}
        <div className="run-form-scroll">
          <WorkflowMetadata
            workflow={workflow}
            actions={
              (publishAction || canEditParameters) && (
                <>
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
                </>
              )
            }
          />
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
              <ProjectSelect value={projectId} onChange={setProjectId} disabled={pending} />
              {available.length > 0 && (
                <Field
                  label={t('runForm.workMachineForThisRun')}
                  htmlFor="run-machine"
                  detail={
                    machine?.online && machine === defaultMachine
                      ? t('machinesPage.default')
                      : undefined
                  }
                >
                  <Select
                    id="run-machine"
                    label={t('runForm.workMachineForThisRun')}
                    value={machine?.online ? machineId : ''}
                    placeholder={t('runForm.selectAnOnlineWorkMachine')}
                    // 上传素材期间切换工作机会重建参数表单，正在上传的文件会丢失。
                    disabled={pending}
                    onValueChange={chooseMachine}
                    options={machineOptions}
                  />
                  {machine?.worker.connection === 'account' && (
                    <p className="form-hint">{t('connection.billing', machine.worker.label)}</p>
                  )}
                  {machine?.online && machine.paused && (
                    <p className="form-hint" role="status">
                      {t('runForm.thisWorkMachineIsPausedSubmitted')}
                    </p>
                  )}
                </Field>
              )}
              {schema.data?.catalogLimited && (
                <p className="form-hint">{t('connection.limited')}</p>
              )}
              {editorFormat && (
                <p className="inline-status run-machine-empty" role="status">
                  {ownsWorkflow
                    ? t('runForm.thisWorkflowIsInEditorFormat')
                    : t('runForm.thisVersionIsInEditorFormat')}
                </p>
              )}
              {unavailableCount > 0 && (
                <div className="form-error" role="alert">
                  <span>{t('runForm.inputsToReviewOnThisWork', unavailableCount)}</span>
                  <Button
                    size="small"
                    variant="ghost"
                    disabled={pending}
                    onClick={() => setParameterPanel('issues')}
                  >
                    {t('runForm.reviewIssues')}
                  </Button>
                </div>
              )}
              {schema.data && (
                <div className="form-section-heading">
                  <span>{t('runForm.inputs')}</span>
                  <IconButton
                    label={t('runForm.resetParameters')}
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
                      {t('runForm.advancedParameters')}
                      <ChevronDownIcon />
                    </Button>
                  </Collapsible.Trigger>
                  <Collapsible.Content className="ui-collapsible advanced-content">
                    {renderGroup(advancedRows, false)}
                  </Collapsible.Content>
                </Collapsible.Root>
              )}
              {schema.data && (
                <Field label={t('runForm.runs')} htmlFor="run-count" detail={t('runForm.runs2')}>
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
              {(schema.error || (!platformManaged && machines.error)) && (
                <div className="form-error" role="alert">
                  {schema.error?.message || machines.error?.message}
                  <Button
                    variant="ghost"
                    size="small"
                    onClick={() => {
                      if (!platformManaged) void machines.refetch();
                      void schema.refetch();
                    }}
                  >
                    {t('runForm.refresh')}
                  </Button>
                </div>
              )}
            </form>
          )}
        </div>
      </div>
      <div className="run-footer">
        {error && (
          <p id={errorId} className="form-error" role="alert">
            {error}
          </p>
        )}
        {!error && issueHint && (
          <p id={issueId} className="form-hint run-issue-hint" role="status">
            {issueHint}
          </p>
        )}
        {!machineBlocked && taskSummary}
        {changedHidden.size > 0 && (
          <Button
            size="small"
            variant="ghost"
            className="run-hidden-changes"
            disabled={pending}
            onClick={() => setParameterPanel('hidden-changed')}
          >
            {t('runForm.hiddenParametersChanged', changedHidden.size)}
          </Button>
        )}
        {blockMessage && (
          <div className="machine-hint">
            <span id={blockId} className="form-hint" role="status">
              {blockMessage}
            </span>
            {machineBlocked &&
              !needsMachineSetup &&
              !machines.isPending &&
              (machineReadFailed ? (
                <Button size="small" variant="secondary" onClick={() => void machines.refetch()}>
                  {t('app.retry')}
                </Button>
              ) : onlineAlternative ? (
                <Button
                  size="small"
                  variant="secondary"
                  disabled={pending}
                  onClick={() => chooseMachine(onlineAlternative.id)}
                >
                  {t('runForm.switchToAnOnlineWorkMachine')}
                </Button>
              ) : (
                <Button asChild size="small" variant="secondary">
                  <Link to="/machines">{t('runForm.viewWorkMachines')}</Link>
                </Button>
              ))}
          </div>
        )}
        {state.user && schema.data?.costEstimate && (
          <RunCostEstimate
            key={JSON.stringify([
              state.userId,
              ...workspaceKey(workspaceScope),
              workflow.versionId,
            ])}
            api={api}
            inputs={generationInputs(schema.data.schemaHash)}
            executionCount={countInvalid ? null : executionCount}
            scope={[state.userId, ...workspaceKey(workspaceScope)]}
            inputsReady={!switchingVersion && !blockMessage && !hasIssues && !firstIssue}
            disabled={pending || !!parameterPanel}
          />
        )}
        <div className="run-action-buttons">
          {!!state.user && rows.length > 0 && (
            <RunParameterDialog
              mode={parameterPanel}
              platformManaged={platformManaged}
              issueCount={issues.size}
              disabled={pending}
              initialMachineId={machineId}
              machines={machineOptions}
              initialDraft={inputValues}
              initialHiddenDraft={hiddenInputValues}
              readForm={readForm}
              onApply={(nextMachineId, patch, hiddenPatch) => {
                if (nextMachineId !== machineId) chooseMachine(nextMachineId);
                changeInputs(patch);
                if (Object.keys(hiddenPatch).length)
                  onHiddenInputValuesChange((prior) => applyInputPatch(prior, hiddenPatch));
              }}
              onOpenChange={setParameterPanel}
            />
          )}
          {needsMachineSetup ? (
            <Button asChild className="generate-button" size="large" variant="primary">
              <Link to="/machines" aria-describedby={blockId}>
                <span>{machineSetupLabel}</span>
                <ArrowRightIcon />
              </Link>
            </Button>
          ) : (
            <Button
              className="generate-button"
              size="large"
              aria-describedby={
                blockMessage ? blockId : error ? errorId : issueHint ? issueId : undefined
              }
              form={state.user ? formId : undefined}
              type={state.user ? 'submit' : 'button'}
              variant="primary"
              onClick={
                state.user
                  ? undefined
                  : (event) =>
                      requireAuth(
                        event.currentTarget,
                        undefined,
                        t('runForm.signInToGenerateOnYour'),
                      )
              }
              disabled={pending || !!blockMessage}
            >
              {issueHint ? <MixerHorizontalIcon /> : <PlayIcon />}
              <span>
                {submitting
                  ? t('accountDialog.submitting')
                  : issueHint
                    ? t('runForm.reviewInputs')
                    : state.user
                      ? t('runForm.generate')
                      : t('runForm.signInToGenerate')}
              </span>
              <ArrowRightIcon />
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
