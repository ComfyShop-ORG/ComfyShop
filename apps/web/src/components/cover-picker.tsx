import { useState } from 'react';
import { ImageIcon, UploadIcon } from '@radix-ui/react-icons';
import type { Artifact, CoverUpdate, Execution, Media } from '@comfyshop/api-client';
import { Button, FileInput } from '@comfyshop/ui';
import { useWorkspace } from '../app/use-workspace';
import { createRequestId } from '../data/request-id';
import { AssetGallery } from './artifact-collection';
import { durationLabel } from './generation-stage';
import type { useAction } from './use-action';

type PreviousCover = Pick<Execution, 'coverArtifactId' | 'coverFrameMs' | 'media'>;

export type CoverDraft = { source: CoverUpdate; media: Media };

export function outputCover(asset: Artifact, previous: PreviousCover): CoverDraft {
  const frameMs = asset.id === previous.coverArtifactId ? previous.coverFrameMs : null;
  return {
    source: { artifactId: asset.id, frameMs },
    media: frameMs && previous.media ? previous.media : asset.media,
  };
}

export function isVisualOutput({ media }: Artifact) {
  return media.kind === 'image' || media.kind === 'video';
}

export function CoverPicker({
  media,
  previous,
  items,
  hasNextPage,
  loading,
  loadMore,
  resetKey,
  selected,
  disabled,
  upload,
  onChoose,
}: {
  media: Media | null;
  previous: PreviousCover;
  items: Artifact[];
  hasNextPage?: boolean;
  loading?: boolean;
  loadMore?: () => Promise<unknown>;
  resetKey: string;
  selected?: string | null;
  disabled: boolean;
  upload: ReturnType<typeof useAction>;
  onChoose: (draft: CoverDraft) => void;
}) {
  const { api } = useWorkspace();
  const [scrollRoot, setScrollRoot] = useState<HTMLDivElement | null>(null);
  const choices = items.filter(isVisualOutput);
  const busy = disabled || upload.busy;
  const thumbnail = media?.thumbnail;
  return (
    <div className="cover-picker">
      <div className="cover-picker-preview">
        {thumbnail ? (
          <img
            src={thumbnail.src}
            alt="封面预览"
            width={media.width ?? undefined}
            height={media.height ?? undefined}
          />
        ) : (
          <span className="muted">
            <ImageIcon />
            {media?.filename || '无封面图片'}
          </span>
        )}
      </div>
      {selected === previous.coverArtifactId && !!previous.coverFrameMs && (
        <p className="form-hint">封面取自视频 {durationLabel(previous.coverFrameMs)} 处的画面。</p>
      )}
      <FileInput
        aria-label="上传封面图片"
        accept="image/png,image/jpeg,image/webp,image/gif"
        disabled={busy}
        onChange={(event) => {
          const file = event.currentTarget.files?.[0];
          event.currentTarget.value = '';
          if (!file) return;
          void upload.run(async () => {
            const asset = await api.uploadAsset(file, createRequestId());
            if (asset.media.kind !== 'image') throw new Error('请选择图片文件');
            onChoose({ source: { assetId: asset.id }, media: asset.media });
          });
        }}
      >
        <UploadIcon />
        {upload.busy ? '正在上传…' : '上传封面图片'}
      </FileInput>
      {upload.error && (
        <p className="form-error" role="alert">
          {upload.error}
        </p>
      )}
      {choices.length > 0 && (
        <>
          <span className="form-section-heading">从成品选封面</span>
          <div className="publish-media-scroll" ref={setScrollRoot}>
            <AssetGallery
              items={choices}
              resetKey={resetKey}
              scrollRoot={scrollRoot}
              selected={new Set(selected ? [selected] : [])}
              disabled={busy}
              onOpen={(asset) => {
                upload.clearError();
                onChoose(outputCover(asset, previous));
              }}
            />
          </div>
        </>
      )}
      {hasNextPage && (
        <Button size="small" disabled={busy || loading} onClick={() => void loadMore?.()}>
          {loading ? '正在读取…' : '加载更多成品'}
        </Button>
      )}
    </div>
  );
}
