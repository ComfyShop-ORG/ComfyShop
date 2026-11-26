import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useLocation, useNavigate } from 'react-router';
import type { Artifact, InpaintTarget } from '@comfyshop/api-client';
import { Button, Dialog, DialogClose, DialogContent, Select } from '@comfyshop/ui';
import { t } from '../../app/i18n';
import { clearResultParams } from '../../app/result-route';
import { useWorkspace } from '../../app/use-workspace';
import { workflowOverlayState, workflowPath, workflowRouteState } from '../../app/workflow-route';
import { workspaceKey } from '../../app/workspace-scope';
import { createRequestId } from '../../data/request-id';
import { PickerDialogContent } from '../../components/picker-dialog';
import { WorkflowChoices } from '../catalog/workflow-picker';
import { MaskDialog } from './mask-dialog';

type Source = {
  artifact: Pick<Artifact, 'id' | 'media'>;
  sourceWorkflowId: string;
  projectId?: string;
};

export function ContinueInpaint({ disabled, ...source }: Source & { disabled?: boolean }) {
  const [open, setOpen] = useState(false);
  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Trigger asChild>
        <Button size="small" disabled={disabled}>
          {t('inpaint.edit')}
        </Button>
      </Dialog.Trigger>
      {open && <InpaintEditor {...source} close={() => setOpen(false)} />}
    </Dialog.Root>
  );
}

function InpaintEditor({
  artifact,
  sourceWorkflowId,
  projectId,
  close,
}: Source & { close: () => void }) {
  const { api, state, workspaceScope } = useWorkspace();
  const location = useLocation();
  const navigate = useNavigate();
  const options = useQuery({
    queryKey: ['inpaint-targets', state.userId, ...workspaceKey(workspaceScope), artifact.id],
    queryFn: ({ signal }) => api.inpaintTargets(artifact.id, signal),
    retry: false,
    refetchOnWindowFocus: false,
  });
  const [selectedWorkflow, setSelectedWorkflow] = useState<string>();
  const [selectedInput, setSelectedInput] = useState<InpaintTarget>();
  const request = useRef<AbortController | null>(null);
  useEffect(() => () => request.current?.abort(), [api, artifact.id, state.userId]);
  const choices = options.data ?? [];
  const uniqueWorkflow = choices.every((choice) => choice.workflowId === choices[0]?.workflowId);
  const workflowId =
    selectedWorkflow ??
    (choices.some((choice) => choice.workflowId === sourceWorkflowId)
      ? sourceWorkflowId
      : undefined) ??
    (uniqueWorkflow ? choices[0]?.workflowId : undefined);
  const inputs = choices.filter((choice) => choice.workflowId === workflowId);
  const target = selectedInput ?? (inputs.length === 1 ? inputs[0] : undefined);

  async function apply(target: InpaintTarget, file: File | null) {
    if (!file) throw new Error(t('inpaint.paintFirst'));
    if (!state.userId) return false;
    request.current = new AbortController();
    const { signal } = request.current;
    const form = await api.workflowForm(
      target.workflowId,
      target.versionId,
      target.machineId,
      signal,
    );
    if (
      form.issues.length ||
      form.parameterPresentation[target.fieldId]?.mask?.fieldId !== target.mask.fieldId
    ) {
      void options.refetch();
      throw new Error(t('inpaint.changed'));
    }
    const source = await api.useArtifactInput(artifact.id, signal);
    const mask = await api.uploadAsset(file, createRequestId(), signal);
    if (signal.aborted) return false;
    const prior = workflowRouteState(location);
    const background = prior?.background ?? location;
    const params = new URLSearchParams(background.search);
    clearResultParams(params);
    const overlay = workflowOverlayState({
      ...background,
      pathname: background.pathname.startsWith('/workflows/') ? '/' : background.pathname,
      search: params.size ? '?' + params.toString() : '',
    });
    overlay.projectId = projectId ?? prior?.projectId;
    overlay.inpaintDraft = {
      key: createRequestId(),
      userId: state.userId,
      teamId: workspaceScope?.id,
      workflowId: target.workflowId,
      versionId: target.versionId,
      machineId: target.machineId,
      inputValues: {
        [target.fieldId]: { assetId: source.id },
        [target.mask.fieldId]: { assetId: mask.id },
      },
    };
    const presentView = new URLSearchParams(location.search).get('view');
    const view = presentView === 'fullscreen' || presentView === 'dialog' ? presentView : undefined;
    void navigate(workflowPath(target.workflowId, target.versionId, view), {
      state: overlay,
      preventScrollReset: true,
    });
    return true;
  }

  if (target)
    return (
      <MaskDialog
        source={artifact}
        editor={{ nativeAlpha: !target.mask.channelFieldId, assetId: null, sharedAsset: undefined }}
        close={close}
        onSave={(file) => apply(target, file)}
      />
    );
  if (inputs.length > 1)
    return (
      <DialogContent size="form" aria-describedby={undefined}>
        <div className="compact-dialog-heading">
          <Dialog.Title>{t('inpaint.chooseInput')}</Dialog.Title>
          <DialogClose label={t('common.close')} />
        </div>
        <Select
          label={t('inpaint.chooseInput')}
          placeholder={t('inpaint.chooseInput')}
          value=""
          options={inputs.map((input) => ({ value: input.fieldId, label: input.label }))}
          onValueChange={(id) => setSelectedInput(inputs.find((input) => input.fieldId === id))}
        />
      </DialogContent>
    );
  return (
    <PickerDialogContent title={t('inpaint.choose')}>
      {(scrollRoot) =>
        choices.length ? (
          <WorkflowChoices
            scrollRoot={scrollRoot}
            initialScope={choices.some((choice) => choice.scope === 'mine') ? 'mine' : 'public'}
            inpaintArtifactId={artifact.id}
            onSelect={(workflow) => setSelectedWorkflow(workflow.id)}
          />
        ) : (
          <div className="inline-status" role={options.isError ? 'alert' : 'status'}>
            {options.error?.message ??
              t(options.isPending ? 'common.loading' : 'inpaint.unavailable')}
            {!options.isPending && (
              <Button
                size="small"
                disabled={options.isFetching}
                onClick={() => void options.refetch()}
              >
                {t('app.retry')}
              </Button>
            )}
          </div>
        )
      }
    </PickerDialogContent>
  );
}
