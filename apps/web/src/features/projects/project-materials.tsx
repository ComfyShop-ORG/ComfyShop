import { useRef } from 'react';
import type { Project } from '@comfyshop/api-client';
import { t } from '../../app/i18n';
import { useWorkspace } from '../../app/use-workspace';
import { DeleteButton } from '../../components/delete-button';
import { useNotify } from '../../components/notify';
import { PageToolbar } from '../../components/page-toolbar';
import { useAction } from '../../components/use-action';
import AssetLibraryPage from '../assets/asset-library-page';
import { AssetLibraryPicker } from '../assets/asset-library-picker';
import { WorkflowCollection } from '../catalog/workflow-collection';
import { useChangeProjectMaterial } from './project-queries';
import { WorkflowPicker } from '../catalog/workflow-picker';

export function ProjectMaterials({
  project,
  kind,
}: {
  project: Project;
  kind: 'workflows' | 'assets';
}) {
  const { canEditWorkspace } = useWorkspace();
  const projectId = project.id;
  const archived = project.archivedAt !== null;
  const editable = canEditWorkspace && !archived;
  const change = useChangeProjectMaterial();
  const { error, busy, run } = useAction();
  const notify = useNotify();
  const workflowList = useRef<HTMLDivElement>(null);
  function linkMaterial(id: string) {
    void run(async () => {
      await change(projectId, kind, id, true);
      notify(t('projects.materialLinked'));
    });
  }
  return (
    <>
      {editable && (
        <PageToolbar>
          {kind === 'workflows' ? (
            <WorkflowPicker
              label={t('projects.linkWorkflow')}
              disabled={busy}
              onSelect={(workflow) => linkMaterial(workflow.id)}
            />
          ) : (
            <AssetLibraryPicker
              label={t('projects.linkAsset')}
              size="normal"
              disabled={busy}
              onSelect={(asset) => linkMaterial(asset.id)}
            />
          )}
        </PageToolbar>
      )}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {kind === 'workflows' ? (
        <div ref={workflowList} tabIndex={-1}>
          <WorkflowCollection
            scope="mine"
            projectId={projectId}
            cardAction={
              editable
                ? (workflow) => (
                    <DeleteButton
                      label={t('projects.unlink')}
                      description={t('projects.unlinkDescription', workflow.name)}
                      triggerClassName="media-card-action"
                      disabled={busy}
                      done={t('projects.materialRemoved')}
                      onDelete={() => change(projectId, 'workflows', workflow.id, false)}
                      onDeleted={() => workflowList.current?.focus({ preventScroll: true })}
                    />
                  )
                : null
            }
          />
        </div>
      ) : (
        <AssetLibraryPage projectId={projectId} projectArchived={archived} />
      )}
    </>
  );
}
