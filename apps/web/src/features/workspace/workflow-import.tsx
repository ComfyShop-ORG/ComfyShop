import { useContext, useEffect, useId, useRef, useState } from 'react';
import { UploadIcon } from '@radix-ui/react-icons';
import { useQueryClient } from '@tanstack/react-query';
import {
  Button,
  Dialog,
  DialogClose,
  DialogContent,
  Field,
  FileInput,
  Input,
  RadioGroup,
  Select,
} from '@comfyshop/ui';
import type { Machine, Workflow } from '@comfyshop/api-client';
import { t } from '../../app/i18n';
import { useMachines, useWorkspace } from '../../app/use-workspace';
import { workspaceKey } from '../../app/workspace-scope';
import { CardActions } from '../../components/card-actions';
import { DialogActions } from '../../components/dialog-actions';
import { useNotify } from '../../components/notify';
import { useAction } from '../../components/use-action';
import { isEditorGraph, readWorkflow } from '../../data/workflow-import';
import type { Category } from '../../domain/types';
import { workflowCategories } from '../../domain/workflow-categories';
import { OfficialImportGrants } from './official-import-grants';

type Source = 'comfyui' | 'reference' | 'official';
type ImportProps = { machine?: Machine; categoryFilter?: Category };

export function WorkflowImport({ machine, categoryFilter }: ImportProps) {
  const [open, setOpen] = useState(false);
  const trigger = useRef<HTMLButtonElement>(null);
  const actions = useContext(CardActions);
  return (
    <>
      <Button ref={trigger} aria-haspopup="dialog" onClick={() => setOpen(true)}>
        {!machine && <UploadIcon />}
        {machine ? t('connection.import') : t('workspacePage.importWorkflow')}
      </Button>
      {open && (
        <ImportDialog
          machine={machine}
          onClose={() => setOpen(false)}
          restoreFocus={() => trigger.current?.focus({ preventScroll: true })}
          onImported={(workflow) => {
            setOpen(false);
            const filters =
              categoryFilter === 'all' || categoryFilter === workflow.category
                ? {
                    scope: 'mine' as const,
                    category: categoryFilter,
                    search: '',
                    sort: 'updated' as const,
                  }
                : undefined;
            if (trigger.current) actions.openWorkflow(workflow, trigger.current, filters);
          }}
        />
      )}
    </>
  );
}

function ImportDialog({
  machine,
  onClose,
  restoreFocus,
  onImported,
}: {
  machine?: Machine;
  onClose: () => void;
  restoreFocus: () => void;
  onImported: (workflow: Workflow) => void;
}) {
  const { api, state, workspace, workspaceScope, workspaceTeam } = useWorkspace();
  const machines = useMachines(!machine);
  const queries = useQueryClient();
  const notify = useNotify();
  const id = useId();
  const completed = useRef(false);
  const [chosen, setChosen] = useState<Source>(machine ? 'reference' : 'comfyui');
  const [file, setFile] = useState<File>();
  const [reference, setReference] = useState('');
  const [name, setName] = useState('');
  const [machineId, setMachineId] = useState(machine?.id ?? '');
  const [category, setCategory] = useState<Workflow['category'] | 'auto'>(
    machine ? 'image' : 'auto',
  );
  const { busy, error, run, clearError } = useAction(t('workspacePage.importFailed'));
  const available = (machine ? [machine] : (machines.data?.items ?? [])).filter(
    (item) => item.worker.importsReference && !item.revoked,
  );
  const connection = available.find((item) => item.id === machineId) ?? available[0];
  const options = [{ value: 'comfyui', label: t('workflowImport.comfyuiFile') }];
  if (connection) options.push({ value: 'reference', label: t('workflowImport.referenceSource') });
  if (!workspaceTeam && state.canImportOfficialWorkflows)
    options.push({ value: 'official', label: t('workflowImport.officialFile') });
  const source = options.some((option) => option.value === chosen) ? chosen : 'comfyui';
  const byReference = source === 'reference';
  const fileType =
    source === 'official' ? t('workflowImport.officialFile') : t('workflowImport.comfyuiFile');
  const accessError = state.error ?? (!machine ? machines.error?.message : null);
  useEffect(() => {
    void queries.invalidateQueries({ queryKey: ['workspace', state.userId] });
  }, [queries, state.userId]);
  function choose(next: string) {
    if (next === source || (next !== 'comfyui' && next !== 'official' && next !== 'reference'))
      return;
    setChosen(next);
    setCategory(next === 'reference' ? 'image' : 'auto');
    setFile(undefined);
    clearError();
  }
  async function submit() {
    let workflow: Workflow;
    if (byReference) {
      if (!connection || !reference.trim()) return;
      workflow = await api.importReference({
        machineId: connection.id,
        reference: reference.trim(),
        name: name.trim() || undefined,
        category: category === 'auto' ? 'image' : category,
      });
      queries.setQueryData(
        [
          'run-machine',
          state.userId,
          connection.worker.kind,
          connection.worker.scope,
          ...workspaceKey(workspaceScope),
        ],
        connection.id,
      );
      await queries.invalidateQueries({ queryKey: ['workflows'] });
    } else {
      if (!file) return;
      const body = await readWorkflow(file);
      const manifest = body.graph.format === 'service';
      if (manifest !== (source === 'official')) {
        throw new Error(
          source === 'official'
            ? t('workflowImport.chooseManifest')
            : t('workflowImport.chooseComfyui'),
        );
      }
      workflow = await workspace.importWorkflow({
        ...body,
        category: category === 'auto' ? body.category : category,
      });
      notify(
        isEditorGraph(body.graph)
          ? t('workspacePage.importedInEditorFormatTheApi')
          : t('workspacePage.imported'),
      );
    }
    completed.current = true;
    onImported(workflow);
  }
  return (
    <Dialog.Root open onOpenChange={(next) => !next && !busy && onClose()}>
      <DialogContent
        size="form"
        className="machine-setup"
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          if (!completed.current) restoreFocus();
        }}
      >
        <div className="compact-dialog-heading">
          <Dialog.Title>{t('workspacePage.importWorkflow')}</Dialog.Title>
          <DialogClose label={t('common.close')} disabled={busy} />
        </div>
        {accessError && (
          <div className="inline-status" role="alert">
            {accessError}
            <Button size="small" onClick={() => void workspace.reload()}>
              {t('app.retry')}
            </Button>
          </div>
        )}
        <form
          className="machine-form"
          onSubmit={(event) => {
            event.preventDefault();
            void run(submit);
          }}
        >
          {options.length > 1 && (
            <Field label={t('workflowImport.source')}>
              <RadioGroup
                label={t('workflowImport.source')}
                options={options}
                value={source}
                onValueChange={choose}
                disabled={busy}
              />
            </Field>
          )}
          {byReference && connection ? (
            <>
              <Field htmlFor={id + '-machine'} label={t('app.workMachines')}>
                <Select
                  id={id + '-machine'}
                  label={t('app.workMachines')}
                  value={connection.id}
                  disabled={busy || available.length === 1}
                  onValueChange={setMachineId}
                  options={available.map((item) => ({ value: item.id, label: item.name }))}
                />
              </Field>
              <Field
                htmlFor={id + '-ref'}
                label={t('connection.reference', connection.worker.label)}
              >
                <Input
                  id={id + '-ref'}
                  required
                  disabled={busy}
                  maxLength={2048}
                  value={reference}
                  onChange={(event) => setReference(event.target.value)}
                />
              </Field>
              <Field htmlFor={id + '-name'} label={t('connection.optionalName')}>
                <Input
                  id={id + '-name'}
                  disabled={busy}
                  maxLength={120}
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                />
              </Field>
            </>
          ) : (
            <div className="machine-setup">
              <FileInput
                key={source}
                accept=".json,application/json"
                disabled={busy}
                aria-label={fileType}
                aria-describedby={id + '-hint'}
                onChange={(event) => {
                  setFile(event.target.files?.[0]);
                  clearError();
                }}
              >
                <UploadIcon />
                {file?.name || t('workflowImport.chooseFile')}
              </FileInput>
              <p id={id + '-hint'} className="form-hint">
                {source === 'official'
                  ? t('workflowImport.manifestHelp')
                  : t('workflowImport.fileHelp')}
              </p>
            </div>
          )}
          <Field label={t('workspacePage.importCategory')} htmlFor={id + '-category'}>
            <Select
              id={id + '-category'}
              label={t('workspacePage.importCategory')}
              disabled={busy}
              value={category}
              onValueChange={(value) => setCategory(value as typeof category)}
              options={
                byReference
                  ? workflowCategories
                  : [
                      { value: 'auto', label: t('workspacePage.automaticCategory') },
                      ...workflowCategories,
                    ]
              }
            />
          </Field>
          <DialogActions busy={busy} error={error}>
            <Button
              type="submit"
              variant="primary"
              disabled={busy || (byReference ? !reference.trim() : !file)}
            >
              {busy ? t('workspacePage.importing') : t('workspacePage.importWorkflow')}
            </Button>
          </DialogActions>
        </form>
        {source === 'official' && state.canManageOfficialImportGrants && <OfficialImportGrants />}
      </DialogContent>
    </Dialog.Root>
  );
}
