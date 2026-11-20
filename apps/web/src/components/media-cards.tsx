import { useContext, useEffect, useRef, useState } from 'react';
import type { PointerEvent, ReactNode } from 'react';
import {
  ArrowTopRightIcon,
  BookmarkFilledIcon,
  BookmarkIcon,
  Component1Icon,
  CubeIcon,
  PlayIcon,
  SpeakerLoudIcon,
} from '@radix-ui/react-icons';
import { Button, IconButton } from '@comfyshop/ui';
import type { MediaRendererProps } from '@comfyshop/media';
import type { Workflow } from '../domain/types';
import type { Media } from '@comfyshop/api-client';
import { useWorkspace } from '../app/use-workspace';
import { cardThumbnail, cardVideoPreview } from '../data/card-thumbnail';
import { CardActions } from './card-actions';
import { ProfileAvatar } from './profile-avatar';

const hoverDelayMs = 300;
const motionHover =
  '(hover: hover) and (pointer: fine) and (prefers-reduced-motion: no-preference)';

export function MediaCardContent({
  media,
  coverImage,
  title,
  width,
  detail,
  index = 0,
}: {
  media: Media | null;
  coverImage?: Media | null;
  title: string;
  width: number;
  detail?: ReactNode;
  index?: number;
}) {
  const [failedCover, setFailedCover] = useState<string>();
  const image = coverImage && coverImage.src !== failedCover ? coverImage : media;
  const thumbnail = image ? cardThumbnail(image, width) : null;
  const preview = media ? cardVideoPreview(media, width) : null;
  const Placeholder =
    media?.kind === 'audio' ? SpeakerLoudIcon : media?.kind === '3d' ? CubeIcon : Component1Icon;
  const kind = media?.kind;
  const [clip, setClip] = useState<{ src: string; visible: boolean } | null>(null);
  const timer = useRef<number | undefined>(undefined);
  const video = useRef<HTMLVideoElement>(null);
  const activeSrc = clip?.src === preview ? clip.src : null;

  useEffect(() => () => window.clearTimeout(timer.current), []);
  useEffect(() => {
    const element = video.current;
    if (!activeSrc || !element) return;
    let active = true;
    element.src = activeSrc;
    void element.play().catch(() => {
      if (active) setClip(null);
    });
    return () => {
      active = false;
      element.pause();
      element.removeAttribute('src');
      element.load();
    };
  }, [activeSrc]);

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
      {image && thumbnail ? (
        <img
          key={image.src}
          srcSet={thumbnail.srcSet}
          src={thumbnail.src}
          width={image.width ?? undefined}
          height={image.height ?? undefined}
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
          onError={image === coverImage ? () => setFailedCover(image.src) : undefined}
        />
      ) : (
        <span className="media-placeholder" aria-hidden="true">
          <Placeholder />
        </span>
      )}
      {activeSrc && (
        <video
          ref={video}
          className="media-card-video"
          data-visible={clip?.visible}
          aria-hidden="true"
          muted
          playsInline
          preload="none"
          onPlaying={() =>
            setClip((current) =>
              current && !current.visible ? { ...current, visible: true } : current,
            )
          }
          onError={stopPreview}
        />
      )}
      {(kind === 'video' || kind === 'audio' || kind === '3d') && (
        <span className="media-card-kind">
          {kind === 'video' ? <PlayIcon /> : <Placeholder />}
          {kind === 'video' ? '视频' : kind === 'audio' ? '音频' : '3D 模型'}
        </span>
      )}
      <span className="media-card-caption">
        <strong>{title}</strong>
        {detail && <span className="media-card-author">{detail}</span>}
      </span>
    </span>
  );
}

export function WorkflowCard({ data, index, width }: MediaRendererProps<Workflow>) {
  const actions = useContext(CardActions);
  const { state } = useWorkspace();
  const saved = state.favorites.includes(data.id);
  const author = data.authorProfile.nickname ?? data.author;
  return (
    <article className="media-card">
      <Button
        variant="ghost"
        className="media-card-open"
        aria-label={data.name}
        onClick={(event) => actions.openWorkflow(data, event.currentTarget)}
      >
        <MediaCardContent
          media={data.media}
          title={data.name}
          width={width}
          index={index}
          detail={
            <>
              <ProfileAvatar name={author} src={data.authorProfile.avatarUrl} />
              <span className="profile-name">{author}</span>
              <ArrowTopRightIcon />
            </>
          }
        />
      </Button>
      <IconButton
        className="media-card-save"
        label={(saved ? '取消收藏 ' : '收藏 ') + data.name}
        aria-pressed={saved}
        onClick={(event) => actions.favorite(data.id, event.currentTarget)}
      >
        {saved ? <BookmarkFilledIcon /> : <BookmarkIcon />}
      </IconButton>
    </article>
  );
}
