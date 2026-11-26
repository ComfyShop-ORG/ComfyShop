import { UploadIcon } from '@radix-ui/react-icons';
import { FileInput } from '@comfyshop/ui';
import { t } from '../../app/i18n';
import { useWorkspace } from '../../app/use-workspace';
import { BrowseDialog } from '../../components/browse-dialog-content';
import { DeleteButton } from '../../components/delete-button';
import { DownloadOriginal } from '../../components/download-original';
import { MediaPreview } from '../../components/media-preview';
import { useNotify } from '../../components/notify';
import { useAction } from '../../components/use-action';
import { useCollectionSelection } from '../../components/use-collection-navigation';
import { CopyToTeam } from '../workspace/team-switcher';
import { useChangeProjectMaterial } from '../projects/project-queries';
import { AssetLibraryCollection } from './asset-library-collection';
import { useAssetLibraryActions } from './asset-queries';
import type { Asset } from '@comfyshop/api-client';

export default function AssetLibraryPage({
  projectId,
  projectArchived = false,
}: {
  projectId?: string;
  projectArchived?: boolean;
}) {
  const { selected, open, close, fallbackRef, restoreFocus } = useCollectionSelection<Asset>();
  const { workspaceScope, canEditWorkspace } = useWorkspace();
  const library = useAssetLibraryActions();
  const changeMaterial = useChangeProjectMaterial();
  const upload = useAction();
  const notify = useNotify();

  return (
    <>
      <div ref={fallbackRef} tabIndex={-1}>
        <AssetLibraryCollection
          onOpen={open}
          error={upload.error}
          projectId={projectId}
          action={
            canEditWorkspace &&
            !projectId && (
              <FileInput
                variant="inline"
                aria-label={t('assetLibrary.upload')}
                accept="image/*,video/*,audio/*,.glb,.raw,.pcm,.mulaw,.ulaw,.alaw"
                disabled={upload.busy}
                onChange={(event) => {
                  const file = event.currentTarget.files?.[0];
                  event.currentTarget.value = '';
                  if (!file) return;
                  void upload.run(async () => {
                    await library.upload(file);
                    notify(t('assetLibrary.saved'));
                  });
                }}
              >
                <UploadIcon />
                {upload.busy ? t('inputField.uploading') : t('assetLibrary.upload')}
              </FileInput>
            )
          }
        />
      </div>
      {selected && (
        <BrowseDialog
          className="result-dialog"
          itemId={selected.id}
          title={selected.filename}
          onClose={close}
          restoreFocus={restoreFocus}
          actions={
            <>
              <DownloadOriginal media={selected.media} filename={selected.filename} />
              {!workspaceScope && !projectId && <CopyToTeam source={{ assetId: selected.id }} />}
              {canEditWorkspace && !projectArchived && (
                <DeleteButton
                  label={t(projectId ? 'projects.unlink' : 'assetLibrary.remove')}
                  description={t(
                    projectId ? 'projects.unlinkDescription' : 'assetLibrary.removeConfirmation',
                    selected.filename,
                  )}
                  done={t(projectId ? 'projects.materialRemoved' : 'assetLibrary.removed')}
                  onDelete={() =>
                    projectId
                      ? changeMaterial(projectId, 'assets', selected.id, false)
                      : library.remove(selected.id)
                  }
                  onDeleted={close}
                />
              )}
            </>
          }
        >
          <div className="collection-scroll asset-library-preview">
            <MediaPreview media={selected.media} name={selected.filename} keyboardScope="dialog" />
          </div>
        </BrowseDialog>
      )}
    </>
  );
}
