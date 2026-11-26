import { t } from '../app/i18n.ts';
import { lazy, Suspense, useContext, useEffect, useRef, useState } from 'react';
import type { PointerEvent, ReactNode } from 'react';
import {
  ArrowTopRightIcon,
  BookmarkFilledIcon,
  BookmarkIcon,
  Component1Icon,
  CubeIcon,
  FileTextIcon,
  PlayIcon,
  SpeakerLoudIcon,
} from '@radix-ui/react-icons';
import { Button, IconButton } from '@comfyshop/ui';
import type { MediaRendererProps } from '@comfyshop/media';
import type { Workflow } from '../domain/types';
import type { Media } from '@comfyshop/api-client';
import { useWorkspace } from '../app/use-workspace';
import audioWorkflowCoverUrl from '../assets/audio-workflow-cover.webp';
import { cardThumbnail, cardVideoPreview } from '../data/card-thumbnail';
import { CardActions } from './card-actions';
import { CardAttribution } from './publication-attribution';

const VideoPlayer = lazy(() => import('./media-player'));
const hoverDelayMs = 300;
const motionHover =
  '(hover: hover) and (pointer: fine) and (prefers-reduced-motion: no-preference)';
const defaultAudioCover = { src: audioWorkflowCoverUrl, width: 768, height: 768 };
const mediaIcons = {
  audio: SpeakerLoudIcon,
  '3d': CubeIcon,
  text: FileTextIcon,
  video: Component1Icon,
} as const;
const mediaLabels = {
  video: () => t('mediaCards.video'),
  audio: () => t('mediaCards.audio'),
  '3d': () => t('mediaCards.dModel'),
  text: () => t('mediaCards.text'),
} as const;

export function MediaCardContent({
  media,
  coverImage,
  audioCoverFallback,
  placeholder,
  title,
  width,
  detail,
  index = 0,
}: {
  media: Media | null;
  coverImage?: Media | null;
  audioCoverFallback?: boolean;
  placeholder?: ReactNode;
  title?: string;
  width: number;
  detail?: ReactNode;
  index?: number;
}) {
  const [failedCover, setFailedCover] = useState<string>();
  const image = coverImage && coverImage.src !== failedCover ? coverImage : media;
  const thumbnail = image ? cardThumbnail(image, width) : null;
  const fallbackImage = audioCoverFallback ? defaultAudioCover : undefined;
  const picture =
    image && thumbnail
      ? { ...thumbnail, width: image.width ?? undefined, height: image.height ?? undefined }
      : fallbackImage;
  const preview = media ? cardVideoPreview(media, width) : null;
  const kind = media?.kind;
  const mediaKind = kind === 'image' ? undefined : kind;
  const Placeholder = (mediaKind && mediaIcons[mediaKind]) || Component1Icon;
  const [clip, setClip] = useState<{ src: string; visible: boolean } | null>(null);
  const timer = useRef<number | undefined>(undefined);
  const activeSrc = clip?.src === preview ? clip.src : null;

  useEffect(() => () => window.clearTimeout(timer.current), []);

  function beginPreview(event: PointerEvent<HTMLSpanElement>) {
    if (
      !preview ||
      event.pointerType !== 'mouse' ||
      event.buttons ||
      !matchMedia(motionHover).matches
    )
      return;
    const surface = event.currentTarget;
    timer.current = window.setTimeout(() => {
      if (
        surface.isConnected &&
        surface.matches(':hover') &&
        !surface.closest('[aria-hidden="true"]')
      )
        setClip({ src: preview, visible: false });
    }, hoverDelayMs);
  }

  function stopPreview() {
    window.clearTimeout(timer.current);
    setClip(null);
  }

  return (
    <span
      className="media-card-surface"
      onPointerEnter={beginPreview}
      onPointerLeave={stopPreview}
      onPointerCancel={stopPreview}
      onPointerDown={stopPreview}
    >
      {picture ? (
        <img
          key={thumbnail ? image?.src : picture.src}
          {...picture}
          alt=""
          decoding="async"
          loading={index < 4 ? 'eager' : 'lazy'}
          // 图片读完后淡入。已在缓存里的图片挂载时即为完成状态，不再闪动。
          ref={(image) => {
            if (image?.complete) image.dataset.loaded = 'true';
          }}
          onLoad={(event) => {
            event.currentTarget.dataset.loaded = 'true';
          }}
          onError={
            image && thumbnail && image === coverImage ? () => setFailedCover(image.src) : undefined
          }
        />
      ) : (
        <span className="media-placeholder" aria-hidden="true">
          {placeholder ?? <Placeholder />}
        </span>
      )}
      {activeSrc && (
        <Suspense fallback={null}>
          <VideoPlayer
            mode="clip"
            src={activeSrc}
            className="media-card-video"
            visible={clip?.visible}
            onPlaying={() =>
              setClip((current) =>
                current && !current.visible ? { ...current, visible: true } : current,
              )
            }
            onUnavailable={stopPreview}
          />
        </Suspense>
      )}
      {mediaKind && (
        <span className="media-card-kind">
          {mediaKind === 'video' ? <PlayIcon /> : <Placeholder />}
          {mediaLabels[mediaKind]()}
        </span>
      )}
      {title !== undefined && (
        <span className="media-card-caption">
          <strong>{title}</strong>
          {detail && <span className="media-card-author">{detail}</span>}
        </span>
      )}
    </span>
  );
}

export function WorkflowCard({
  data,
  index,
  width,
  showTeam = false,
}: MediaRendererProps<Workflow> & { showTeam?: boolean }) {
  const actions = useContext(CardActions);
  const { state, canEditWorkspace, workspaceTeam } = useWorkspace();
  const saved = state.favorites.includes(data.id);
  return (
    <article className="media-card workflow-card">
      <Button
        variant="ghost"
        className="media-card-open"
        aria-label={data.name}
        onClick={(event) => actions.openWorkflow(data, event.currentTarget)}
      >
        <MediaCardContent
          media={data.media}
          audioCoverFallback={data.category === 'audio'}
          title={data.name}
          width={width}
          index={index}
          detail={
            <>
              <CardAttribution content={data} showTeam={showTeam} />
              <ArrowTopRightIcon />
            </>
          }
        />
      </Button>
      {actions.workflowAction !== undefined
        ? actions.workflowAction?.(data)
        : (canEditWorkspace || (workspaceTeam && saved)) && (
            <IconButton
              className="media-card-action"
              label={
                (saved ? t('mediaCards.removeFromFavorites') : t('mediaCards.addToFavorites')) +
                data.name
              }
              aria-pressed={saved}
              disabled={!state.ready || !canEditWorkspace}
              onClick={(event) => actions.favorite(data, event.currentTarget)}
            >
              {saved ? <BookmarkFilledIcon /> : <BookmarkIcon />}
            </IconButton>
          )}
    </article>
  );
}
