/** 作者编辑工作流资料、封面和草稿版本。 */
import { t } from '../../app/i18n.ts';
import { useId, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { UploadIcon } from '@radix-ui/react-icons';
import type { Workflow } from '@comfyshop/api-client';
import {
  Button,
  Dialog,
  DialogClose,
  DialogContent,
  Field,
  FileInput,
  Input,
  Select,
  TextArea,
} from '@comfyshop/ui';
import { useWorkspace } from '../../app/use-workspace';
import { CoverImageUpload } from '../../components/cover-picker';
import { DialogActions } from '../../components/dialog-actions';
import { useAction } from '../../components/use-action';
import { isEditorGraph, readGraph } from '../../data/workflow-import';
import { workflowCategories } from '../../domain/workflow-categories';

export function WorkflowSettings({
  workflow,
  notify,
  onClose,
  restoreFocus,
}: {
  workflow: Workflow;
  notify: (message: string) => void;
  onClose: () => void;
  restoreFocus: () => void;
}) {
  const { api } = useWorkspace();
  const queries = useQueryClient();
  const id = useId();
  const [name, setName] = useState(workflow.name);
  const [category, setCategory] = useState(workflow.category);
  const [description, setDescription] = useState(workflow.description);
  const [file, setFile] = useState<{ name: string; graph: Record<string, unknown> }>();
  const [fileError, setFileError] = useState('');
  const save = useAction(t('parameterEditor.couldNotSave'));
  const upload = useAction(t('coverDialog.coverUploadFailed'));
  const busy = save.busy || upload.busy;
  const changed =
    name.trim() !== workflow.name ||
    category !== workflow.category ||
    description.trim() !== workflow.description ||
    !!file;
  return (
    <Dialog.Root open onOpenChange={(next) => !next && !busy && onClose()}>
      <DialogContent
        size="form"
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          restoreFocus();
        }}
      >
        <div className="compact-dialog-heading">
          <Dialog.Title>{t('workflowDialog.editWorkflow')}</Dialog.Title>
          <DialogClose label={t('common.close')} disabled={busy} />
        </div>
        <form
          className="publish-form"
          onSubmit={(event) => {
            event.preventDefault();
            if (busy || !name.trim() || !changed) return;
            void save.run(async () => {
              await api.updateWorkflow(workflow.id, {
                name: name.trim(),
                category,
                description: description.trim(),
                ...(file && { graph: file.graph }),
              });
              await Promise.all([
                queries.invalidateQueries({ queryKey: ['workflows'] }),
                queries.invalidateQueries({ queryKey: ['works'] }),
                queries.invalidateQueries({ queryKey: ['workflow-form'] }),
              ]);
              onClose();
              notify(file ? t('workflowSettings.savedAsANewVersion') : t('workflowSettings.saved'));
            });
          }}
        >
          <Field label={t('publishWorkDialog.name')} htmlFor={id + '-name'}>
            <Input
              id={id + '-name'}
              value={name}
              maxLength={120}
              required
              disabled={busy}
              onChange={(event) => setName(event.target.value)}
            />
          </Field>
          <Field label={t('workflowSettings.category')} htmlFor={id + '-category'}>
            <Select
              id={id + '-category'}
              label={t('workflowSettings.category')}
              value={category}
              disabled={busy}
              onValueChange={(value) => setCategory(value as Workflow['category'])}
              options={workflowCategories}
            />
          </Field>
          <Field
            label={t('workflowSettings.description')}
            htmlFor={id + '-description'}
            detail={`${description.length} / 2000`}
          >
            <TextArea
              id={id + '-description'}
              value={description}
              maxLength={2000}
              disabled={busy}
              placeholder={t('workflowSettings.whatTheWorkflowDoesAndWhich')}
              onChange={(event) => setDescription(event.target.value)}
            />
          </Field>
          <Field label={t('workflowSettings.cover')} htmlFor={id + '-cover'}>
            <CoverImageUpload
              id={id + '-cover'}
              disabled={save.busy}
              upload={upload}
              onUpload={async ({ id: assetId }) => {
                await api.setWorkflowCover(workflow.id, { assetId });
                await Promise.all([
                  queries.invalidateQueries({ queryKey: ['workflows'] }),
                  queries.invalidateQueries({ queryKey: ['asset-library'] }),
                ]);
                notify(t('workflowSettings.saved'));
              }}
            />
            {workflow.coverWorkId && (
              <p className="form-hint">
                {t('workflowSettings.uploadingACoverClearsTheSelectedWork')}
              </p>
            )}
          </Field>
          {workflow.worker.connection !== 'account' && (
            <Field
              label={t('workflowSettings.workflowFile')}
              htmlFor={id + '-file'}
              detail={file ? file.name : t('workflowSettings.currentV', workflow.version)}
            >
              <FileInput
                id={id + '-file'}
                accept=".json,application/json"
                disabled={busy}
                onChange={(event) => {
                  const input = event.currentTarget;
                  void (async () => {
                    const picked = input.files?.[0];
                    input.value = '';
                    if (!picked) return;
                    try {
                      setFile({ name: picked.name, graph: await readGraph(picked) });
                      setFileError('');
                    } catch (error) {
                      setFile(undefined);
                      setFileError(
                        error instanceof Error
                          ? error.message
                          : t('workflowSettings.couldNotReadTheFile'),
                      );
                    }
                  })();
                }}
              >
                <UploadIcon />
                {t('workflowSettings.uploadNewVersion')}
              </FileInput>
              <p className="form-hint">
                {file && isEditorGraph(file.graph)
                  ? t('workflowSettings.theEditorFormatCanBeSaved')
                  : t('workflowSettings.theFileIsSavedAsA')}
              </p>
            </Field>
          )}
          <DialogActions busy={busy} error={fileError || save.error}>
            <Button type="submit" variant="primary" disabled={busy || !name.trim() || !changed}>
              {save.busy ? t('avatarCropDialog.saving') : t('machinesPage.save')}
            </Button>
          </DialogActions>
        </form>
      </DialogContent>
    </Dialog.Root>
  );
}
