import { useState } from 'react';
import type { CoverUpdate, Execution } from '@comfyshop/api-client';
import { Button, Dialog, DialogClose, DialogContent } from '@comfyshop/ui';
import type { useArtifactPages } from './artifact-collection';
import { CoverPicker } from './cover-picker';
import type { CoverDraft } from './cover-picker';
import { useAction } from './use-action';
import { collectionFeed } from './use-collection-navigation';
import { useDialogFocus } from './use-dialog-focus';

export function CoverDialog({
  title,
  note,
  record,
  artifacts,
  restoreFocus,
  onSave,
  onClose,
}: {
  title: string;
  note?: string;
  record: Pick<Execution, 'id' | 'media' | 'coverImage' | 'coverArtifactId' | 'coverFrameMs'>;
  artifacts: ReturnType<typeof useArtifactPages>;
  restoreFocus: () => void;
  onSave: (body: CoverUpdate) => Promise<void>;
  onClose: () => void;
}) {
  const [draft, setDraft] = useState<CoverDraft>();
  const upload = useAction('上传封面失败');
  const save = useAction('保存封面失败');
  const busy = upload.busy || save.busy;
  const { titleRef, focusProps } = useDialogFocus(restoreFocus);
  const feed = collectionFeed(artifacts);
  function apply(body: CoverUpdate) {
    void save.run(async () => {
      await onSave(body);
      onClose();
    });
  }
  return (
    <Dialog.Root open onOpenChange={(open) => !open && !busy && onClose()}>
      <DialogContent compact className="publish-dialog" {...focusProps}>
        <div className="compact-dialog-heading">
          <Dialog.Title ref={titleRef} tabIndex={-1}>
            {title}
          </Dialog.Title>
          <DialogClose disabled={busy} />
        </div>
        <div className="publish-form">
          <CoverPicker
            {...feed}
            resetKey={`cover:${record.id}`}
            previous={record}
            selected={
              draft ? draft.source.artifactId : record.coverImage ? null : record.coverArtifactId
            }
            media={draft?.media ?? record.coverImage ?? record.media}
            disabled={save.busy}
            upload={upload}
            onChoose={setDraft}
          />
          {artifacts.isError && (
            <div className="inline-status" role="alert">
              {artifacts.error.message}
              <Button size="small" onClick={() => void artifacts.refetch()}>
                重试
              </Button>
            </div>
          )}
          {note && <p className="form-hint">{note}</p>}
          {save.error && (
            <p className="form-error" role="alert">
              {save.error}
            </p>
          )}
          <div className="compact-dialog-footer">
            <Button
              disabled={busy || !(record.coverImage || record.media?.thumbnail)}
              onClick={() => apply({})}
            >
              恢复默认
            </Button>
            <Button
              variant="primary"
              disabled={busy || !draft}
              onClick={() => draft && apply(draft.source)}
            >
              {save.busy ? '正在保存…' : '保存封面'}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog.Root>
  );
}
