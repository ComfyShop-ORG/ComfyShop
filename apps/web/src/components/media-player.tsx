import { useCallback, useEffect, useEffectEvent, useRef, useState } from 'react';
import type { SyntheticEvent } from 'react';
import {
  OpenInNewWindowIcon,
  PauseIcon,
  PlayIcon,
  SpeakerLoudIcon,
  SpeakerOffIcon,
} from '@radix-ui/react-icons';
import { IconButton, TrackSlider } from '@comfyshop/ui';
import { Container, Hotkey } from '@videojs/react';
import { Audio, AudioPlayer, usePlayer as useAudioPlayer } from '@videojs/react/audio';
import { Video, VideoPlayer as Player, usePlayer as useVideoPlayer } from '@videojs/react/video';
import { t } from '../app/i18n.ts';
import { durationLabel } from './generation-stage';
import { useNotify } from './notify';
import { usePictureInPicture, useSystemPlayback } from './system-media';

const dialogSelector = '[role="dialog"], [role="alertdialog"]';
const spaceConsumers =
  "button, a[href], input, select, textarea, summary, audio, [contenteditable]:not([contenteditable='false']), [role=button], [role=slider]";

type InteractiveVideoProps = {
  mode?: 'controls';
  src: string;
  name: string;
  poster?: string;
  width?: number | null;
  height?: number | null;
  /** 打开时静音播放。系统设置为减少动态效果时保持静止。 */
  autoPlay?: boolean;
  /** 一个弹框有一份主视频时，空格也可在弹框的非控件区域使用。 */
  keyboardScope?: 'player' | 'dialog';
  /** 当前播放位置，单位为毫秒。 */
  onPosition?: (milliseconds: number) => void;
};

type VideoClipProps = {
  mode: 'clip';
  src: string;
  className?: string;
  visible?: boolean;
  onPlaying?: () => void;
  onUnavailable?: () => void;
};

function playbackState(state: {
  duration: number;
  currentTime: number;
  paused: boolean;
  muted: boolean;
}) {
  return {
    duration: Number.isFinite(state.duration) ? Math.round(state.duration * 1000) : 0,
    position: Math.round(state.currentTime * 1000),
    paused: state.paused,
    muted: state.muted,
  };
}

function PlaybackControls({
  duration,
  position,
  paused,
  muted,
  overlay,
  pictureInPicture,
  onTogglePlayback,
  onToggleMute,
  onSeek,
}: ReturnType<typeof playbackState> & {
  overlay?: boolean;
  pictureInPicture?: { active: boolean; onToggle: () => void };
  onTogglePlayback: () => void;
  onToggleMute: () => void;
  onSeek: (milliseconds: number) => void;
}) {
  return (
    <div
      className={
        overlay ? 'playback-controls video-controls ui-glass' : 'playback-controls ui-glass'
      }
    >
      <IconButton
        label={paused ? t('mediaPreview.play') : t('mediaPreview.pause')}
        aria-keyshortcuts="Space"
        onClick={onTogglePlayback}
      >
        {paused ? <PlayIcon /> : <PauseIcon />}
      </IconButton>
      <IconButton
        label={muted ? t('mediaPreview.unmute') : t('mediaPreview.mute')}
        onClick={onToggleMute}
      >
        {muted ? <SpeakerOffIcon /> : <SpeakerLoudIcon />}
      </IconButton>
      {duration > 0 && (
        <>
          <TrackSlider
            className="playback-seek"
            label={t('mediaPreview.playbackPosition')}
            min={0}
            max={duration}
            step={50}
            value={Math.min(position, duration)}
            thumbProps={{
              'aria-valuetext': t(
                'mediaPreview.of',
                durationLabel(position),
                durationLabel(duration),
              ),
            }}
            onValueChange={onSeek}
          />
          <span className="playback-time">
            {durationLabel(position)} / {durationLabel(duration)}
          </span>
        </>
      )}
      {pictureInPicture && (
        <IconButton
          label={t('mediaPreview.pictureInPicture')}
          aria-pressed={pictureInPicture.active}
          onClick={pictureInPicture.onToggle}
        >
          <OpenInNewWindowIcon />
        </IconButton>
      )}
    </div>
  );
}

type PlaybackTarget = {
  target: unknown;
  state: { paused: boolean };
  play: () => Promise<unknown>;
  pause: () => void;
};

function togglePlayback(player: PlaybackTarget) {
  if (!player.target) return;
  if (player.state.paused) void player.play().catch(() => undefined);
  else player.pause();
}

export function AudioPreview({ src, name }: { src: string; name: string }) {
  return (
    <AudioPlayer key={src}>
      <InteractiveAudio src={src} name={name} />
    </AudioPlayer>
  );
}

function InteractiveAudio({ src, name }: { src: string; name: string }) {
  const audio = useRef<HTMLAudioElement>(null);
  useSystemPlayback(audio, name);
  const player = useAudioPlayer();
  const playback = useAudioPlayer(playbackState);
  const [unavailable, setUnavailable] = useState(false);
  return (
    <Container className="audio-preview" role="group" aria-label={name}>
      <Audio ref={audio} src={src} preload="metadata" onError={() => setUnavailable(true)} />
      {unavailable ? (
        <p className="form-hint" role="status">
          {t('mediaPreview.audioUnavailable')}
        </p>
      ) : (
        <>
          <Hotkey keys="Space" action="togglePaused" />
          <PlaybackControls
            {...playback}
            onTogglePlayback={() => togglePlayback(player)}
            onToggleMute={() => player.setMuted(!player.state.muted)}
            onSeek={(milliseconds) => void player.seek(milliseconds / 1000)}
          />
        </>
      )}
    </Container>
  );
}

/** 站内视频播放入口。短片模式用于卡片，挂载时静音播放一次。 */
export default function VideoPlayer(props: InteractiveVideoProps | VideoClipProps) {
  if (props.mode === 'clip') return <VideoClip {...props} />;
  return (
    <Player key={props.src}>
      <InteractiveVideo {...props} />
    </Player>
  );
}

function VideoClip({ src, className, visible, onPlaying, onUnavailable }: VideoClipProps) {
  const video = useRef<HTMLVideoElement>(null);
  const reportUnavailable = useEffectEvent(() => onUnavailable?.());
  useEffect(() => {
    const element = video.current;
    if (!element) return;
    let active = true;
    element.src = src;
    void element.play().catch(() => {
      if (active) reportUnavailable();
    });
    return () => {
      active = false;
      element.pause();
      element.removeAttribute('src');
      element.load();
    };
  }, [src]);

  return (
    <Video
      ref={video}
      className={className}
      data-visible={visible}
      aria-hidden="true"
      muted
      playsInline
      preload="none"
      onPlaying={onPlaying}
      onError={onUnavailable}
    />
  );
}

function InteractiveVideo({
  src,
  name,
  poster,
  width,
  height,
  autoPlay = false,
  keyboardScope = 'player',
  onPosition,
}: InteractiveVideoProps) {
  const preview = useRef<HTMLDivElement>(null);
  const video = useRef<HTMLVideoElement>(null);
  const pictureInPicture = usePictureInPicture(video);
  useSystemPlayback(video, name, poster);
  const notify = useNotify();
  const player = useVideoPlayer();
  const playback = useVideoPlayer(playbackState);
  const toggle = useCallback(() => togglePlayback(player), [player]);

  useEffect(() => {
    if (keyboardScope !== 'dialog') return;
    const container = preview.current;
    const dialog = container?.closest(dialogSelector);
    if (!container || !dialog) return;
    const ownerDocument = container.ownerDocument;
    // 播放器获得焦点时由 Video.js 处理。主视频也响应弹框标题等非控件区域的空格。
    const handleSpace = (event: KeyboardEvent) => {
      if (
        event.key !== ' ' ||
        event.defaultPrevented ||
        event.isComposing ||
        event.altKey ||
        event.ctrlKey ||
        event.metaKey ||
        event.shiftKey ||
        !(event.target instanceof Element) ||
        event.target.closest(dialogSelector) !== dialog ||
        container.contains(event.target) ||
        event.target.closest(spaceConsumers) ||
        container.closest('[aria-hidden="true"], [inert]') ||
        !container.getClientRects().length
      )
        return;
      event.preventDefault();
      if (!event.repeat) toggle();
    };
    ownerDocument.addEventListener('keydown', handleSpace);
    return () => ownerDocument.removeEventListener('keydown', handleSpace);
  }, [keyboardScope, toggle]);

  function reportPosition(event: SyntheticEvent<HTMLVideoElement>) {
    onPosition?.(Math.round(event.currentTarget.currentTime * 1000));
  }

  return (
    <Container ref={preview} className="video-preview" aria-label={name}>
      <Video
        ref={video}
        src={src}
        width={width ?? undefined}
        height={height ?? undefined}
        poster={poster || undefined}
        muted
        autoPlay={autoPlay && !matchMedia('(prefers-reduced-motion: reduce)').matches}
        loop
        playsInline
        onLoadedMetadata={reportPosition}
        onPause={reportPosition}
        onTimeUpdate={reportPosition}
        aria-label={name}
      />
      <Hotkey keys="Space" action="togglePaused" />
      <PlaybackControls
        {...playback}
        overlay
        pictureInPicture={
          pictureInPicture.available
            ? {
                active: pictureInPicture.active,
                onToggle: () =>
                  void pictureInPicture
                    .toggle()
                    .catch(() => notify(t('mediaPreview.pipUnavailable'))),
              }
            : undefined
        }
        onTogglePlayback={toggle}
        onToggleMute={() => player.setMuted(!player.state.muted)}
        onSeek={(next) => {
          void player.seek(next / 1000);
          onPosition?.(next);
        }}
      />
    </Container>
  );
}
