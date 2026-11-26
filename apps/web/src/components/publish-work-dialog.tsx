/** 确认要公开的成品、封面和输入范围。 */
import { t } from '../app/i18n.ts';
import { useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import type { Artifact, Execution, Work } from '@comfyshop/api-client';
import {
  Button,
  Dialog,
  DialogClose,
  DialogContent,
  Disclosure,
  Field,
  Input,
  RadioGroup,
  TextArea,
} from '@comfyshop/ui';
import { useWorkspace } from '../app/use-workspace';
import { createRequestId } from '../data/request-id';
import type { useArtifactPages } from './artifact-collection';
import { CoverPicker, isVisualOutput, outputCover } from './cover-picker';
import type { CoverDraft } from './cover-picker';
import { useAction } from './use-action';
import { collectionFeed } from './use-collection-navigation';
import { useDialogFocus } from './use-dialog-focus';

export function PublishWorkDialog({
  execution,
  assets,
  outputs,
  returnToSelection,
  restoreFocus,
  onClose,
  onPublished,
}: {
  execution: Execution;
  assets: Artifact[];
  outputs: ReturnType<typeof useArtifactPages>;
  returnToSelection: boolean;
  restoreFocus: () => void;
  onClose: () => void;
  onPublished: (work: Work) => void;
}) {
  const { api, state } = useWorkspace();
  const [title, setTitle] = useState(execution.workflowName);
  const [previous, setPrevious] = useState(execution);
  const [cover, setCover] = useState<CoverDraft | null>();
  const feed = collectionFeed(outputs);
  const selectedIds = new Set(assets.map((asset) => asset.id));
  const candidates = feed.items.filter(
    (asset) => asset.media.kind === 'image' || selectedIds.has(asset.id),
  );
  const visual = assets.filter(isVisualOutput);
  const original = assets.find((asset) => !isVisualOutput(asset));
  const preferred =
    visual.find((asset) => asset.id === previous.coverArtifactId) ??
    visual.find((asset) => asset.media.kind === 'image') ??
    visual[0];
  const defaultCover = preferred ? outputCover(preferred, previous) : null;
  const inherited = cover === undefined ? previous.coverImage : null;
  const resultPicture: CoverDraft | null =
    previous.media?.kind === 'image' &&
    previous.coverArtifactId &&
    !selectedIds.has(previous.coverArtifactId)
      ? { source: { artifactId: previous.coverArtifactId }, media: previous.media }
      : null;
  const representative =
    cover === undefined
      ? inherited
        ? defaultCover
        : (resultPicture ?? defaultCover)
      : cover?.source.assetId
        ? defaultCover
        : cover;
  const coverArtifactId = representative?.source.artifactId;
  const separateImage =
    inherited || cover?.source.assetId || (coverArtifactId && !selectedIds.has(coverArtifactId));
  const [scope, setScope] = useState('full');
  const [description, setDescription] = useState('');
  const { busy, error, run, clearError } = useAction(t('publishWorkDialog.publishingFailed'));
  const upload = useAction(t('coverDialog.coverUploadFailed'));
  const refresh = useAction(t('publishWorkDialog.couldNotLoadTheResultCover'));
  const pending = busy || upload.busy || refresh.busy;
  const intent = useRef<{ fingerprint: string; id: string } | null>(null);
  const { titleRef, focusProps } = useDialogFocus(restoreFocus);
  const referenceIds = new Set(
    Object.values(execution.inputValues).flatMap((value) =>
      value && typeof value === 'object' ? [value.assetId] : [],
    ),
  );
  const showReferences = scope === 'full' && referenceIds.size > 0;
  const recorded = useQuery({
    queryKey: ['publish-inputs', state.userId, execution.taskId],
    queryFn: ({ signal }) => api.taskInputs(execution.taskId, signal),
    enabled: showReferences,
    retry: false,
  });
  const references = recorded.data?.assets.filter((asset) => referenceIds.has(asset.id)) ?? [];
  const ready = !showReferences || (recorded.isSuccess && references.length === referenceIds.size);
  return (
    <Dialog.Root
      open
      onOpenChange={(open) => {
        if (!open && !pending) onClose();
      }}
    >
      <DialogContent size="form" {...focusProps}>
        <div className="compact-dialog-heading">
          <Dialog.Title ref={titleRef} tabIndex={-1}>
            {t('executionDialog.publishWork')}
          </Dialog.Title>
          <DialogClose label={t('common.close')} disabled={pending} />
        </div>
        <form
          className="publish-form"
          onSubmit={(event) => {
            event.preventDefault();
            if (!title.trim() || !ready || pending) return;
            const body = {
              executionId: execution.id,
              artifactIds: [...selectedIds],
              coverArtifactId: coverArtifactId ?? null,
              coverFrameMs: representative?.source.frameMs ?? null,
              coverAssetId: cover?.source.assetId,
              executionCoverSha256: inherited?.sha256,
              title: title.trim(),
              shareParameters: scope !== 'artifacts',
              shareAssets: scope === 'full',
              description: description.trim(),
            };
            void run(async () => {
              // 内容不变的重试沿用同一个发布编号，平台据此返回已保存的作品。
              const fingerprint = JSON.stringify(body);
              if (intent.current?.fingerprint !== fingerprint)
                intent.current = { fingerprint, id: createRequestId() };
              onPublished(await api.publishWork({ id: intent.current.id, ...body }));
            });
          }}
        >
          <Field label={t('publishWorkDialog.name')} htmlFor={`work-title-${execution.id}`}>
            <Input
              id={`work-title-${execution.id}`}
              value={title}
              maxLength={120}
              required
              onChange={(event) => setTitle(event.target.value)}
            />
          </Field>
          <Field
            label={t('publishWorkDialog.description')}
            htmlFor={`work-description-${execution.id}`}
            detail={`${description.length} / 1000`}
          >
            <TextArea
              id={`work-description-${execution.id}`}
              value={description}
              maxLength={1000}
              placeholder={t('publishWorkDialog.optionalVisibleOnThePublishedWork')}
              onChange={(event) => setDescription(event.target.value)}
            />
          </Field>
          <Disclosure
            label={t('publishWorkDialog.publishSelectedOutputs', assets.length)}
            defaultOpen={assets.length <= 6}
          >
            <ul className="publish-reference-files">
              {assets.map((asset) => (
                <li key={asset.id}>{asset.filename}</li>
              ))}
            </ul>
          </Disclosure>
          <div className="cover-picker">
            <span className="form-section-heading">{t('publishWorkDialog.workCover')}</span>
            <CoverPicker
              {...feed}
              items={candidates}
              resetKey={`publish:${execution.id}`}
              previous={previous}
              selected={inherited || cover?.source.assetId ? null : coverArtifactId}
              media={inherited ?? cover?.media ?? representative?.media ?? original?.media ?? null}
              disabled={busy || refresh.busy}
              upload={upload}
              onChoose={setCover}
            />
            {separateImage && (
              <p className="form-hint">{t('publishWorkDialog.thisCoverImageWillBePublished')}</p>
            )}
            <div className="collection-actions">
              {(previous.coverImage || resultPicture) && cover !== undefined && (
                <Button size="small" disabled={pending} onClick={() => setCover(undefined)}>
                  {t('publishWorkDialog.useResultCover')}
                </Button>
              )}
              {defaultCover &&
                (separateImage ||
                  (cover !== undefined && coverArtifactId !== defaultCover.source.artifactId)) && (
                  <Button size="small" disabled={pending} onClick={() => setCover(defaultCover)}>
                    {t('publishWorkDialog.useDefaultOutputCover')}
                  </Button>
                )}
              {original &&
                cover !== null &&
                (inherited || representative || cover?.source.assetId) && (
                  <Button size="small" disabled={pending} onClick={() => setCover(null)}>
                    {t('publishWorkDialog.removeCover')}
                  </Button>
                )}
            </div>
            {inherited && error && (
              <Button
                size="small"
                disabled={pending}
                onClick={() =>
                  void refresh.run(async () => {
                    setPrevious(await api.execution(execution.id));
                    clearError();
                  })
                }
              >
                {t('publishWorkDialog.reloadResultCover')}
              </Button>
            )}
            {refresh.error && (
              <p className="form-error" role="alert">
                {refresh.error}
              </p>
            )}
          </div>
          <Field label={t('publishWorkDialog.sharingOptions')}>
            <RadioGroup
              label={t('publishWorkDialog.sharingOptions')}
              value={scope}
              options={[
                {
                  value: 'full',
                  label: t('publishWorkDialog.shareAllInputsIncludingAssetsRecommended'),
                },
                { value: 'parameters', label: t('publishWorkDialog.shareParameters') },
                { value: 'artifacts', label: t('publishWorkDialog.shareOutputsOnly') },
              ]}
              disabled={busy}
              onValueChange={setScope}
            />
            {showReferences && recorded.isPending && (
              <span className="form-hint" role="status">
                {t('publishWorkDialog.loadingReferenceAssets')}
              </span>
            )}
            {showReferences && recorded.isError && (
              <div className="inline-status" role="alert">
                {recorded.error.message}
                <Button size="small" onClick={() => void recorded.refetch()}>
                  {t('app.retry')}
                </Button>
              </div>
            )}
            {showReferences &&
              recorded.isSuccess &&
              (ready ? (
                <>
                  <span className="form-hint">
                    {t('publishWorkDialog.visitorsCanDownloadAndReuseThese')}
                  </span>
                  <ul className="publish-reference-files">
                    {references.map((asset) => (
                      <li key={asset.id}>{asset.filename}</li>
                    ))}
                  </ul>
                </>
              ) : (
                <span className="form-error" role="alert">
                  {t('publishWorkDialog.someReferenceAssetsAreUnavailableChange')}
                </span>
              ))}
          </Field>
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          <div className="compact-dialog-footer">
            <Dialog.Close asChild>
              <Button disabled={pending}>
                {returnToSelection
                  ? t('publishWorkDialog.backToSelection')
                  : t('deleteButton.cancel')}
              </Button>
            </Dialog.Close>
            <Button type="submit" variant="primary" disabled={pending || !title.trim() || !ready}>
              {busy ? t('publishWorkDialog.publishing') : t('executionDialog.publishWork')}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog.Root>
  );
}
