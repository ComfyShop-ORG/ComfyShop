import { useRef, useState } from 'react';
import { PauseIcon, PlayIcon, SpeakerLoudIcon, SpeakerOffIcon } from '@radix-ui/react-icons';
import { IconButton, TrackSlider } from '@comfyshop/ui';
import { durationLabel } from './generation-stage';
import type { Media } from '../domain/types';

/**
 * @param autoPlay 打开时静音播放视频。系统设置为减少动态效果时保持静止。
 * @param onPosition 视频播放位置变化时调用，单位毫秒。用于把当前画面选作封面。
 */
export function MediaPreview({
  media,
  name,
  autoPlay = false,
  onPosition,
}: {
  media: Media;
  name: string;
  autoPlay?: boolean;
  onPosition?: (milliseconds: number) => void;
}) {
  const video = useRef<HTMLVideoElement>(null);
  const [playing, setPlaying] = useState(false);
  const [muted, setMuted] = useState(true);
  // 播放位置与总时长，单位为秒。时长在元数据读到后才可用。
  const [position, setPosition] = useState(0);
  const [duration, setDuration] = useState(0);
  function moveTo(seconds: number) {
    setPosition(seconds);
    onPosition?.(Math.round(seconds * 1000));
  }
  if (!media.video)
    return (
      <img
        className="preview-image"
        src={media.src}
        width={media.width}
        height={media.height}
        alt={name}
      />
    );
  return (
    <div className="video-preview">
      <video
        ref={video}
        src={media.video}
        width={media.width}
        height={media.height}
        poster={media.src || undefined}
        muted={muted}
        autoPlay={autoPlay && !matchMedia('(prefers-reduced-motion: reduce)').matches}
        loop
        playsInline
        onPlay={() => setPlaying(true)}
        onPause={() => setPlaying(false)}
        onTimeUpdate={(event) => moveTo(event.currentTarget.currentTime)}
        onDurationChange={(event) => {
          const total = event.currentTarget.duration;
          setDuration(Number.isFinite(total) ? total : 0);
        }}
        aria-label={name}
      />
      <div className="video-controls">
        <IconButton
          label={playing ? '暂停' : '播放'}
          onClick={() => {
            if (playing) video.current?.pause();
            else void video.current?.play().catch(() => setPlaying(false));
          }}
        >
          {playing ? <PauseIcon /> : <PlayIcon />}
        </IconButton>
        <IconButton label={muted ? '开启声音' : '静音'} onClick={() => setMuted(!muted)}>
          {muted ? <SpeakerOffIcon /> : <SpeakerLoudIcon />}
        </IconButton>
        {duration > 0 && (
          <>
            <TrackSlider
              className="video-seek"
              label="播放位置"
              min={0}
              max={Math.round(duration * 1000)}
              step={50}
              value={Math.min(Math.round(position * 1000), Math.round(duration * 1000))}
              thumbProps={{
                'aria-valuetext': `${durationLabel(position * 1000)}，共 ${durationLabel(duration * 1000)}`,
              }}
              onValueChange={(next) => {
                if (video.current) video.current.currentTime = next / 1000;
                moveTo(next / 1000);
              }}
            />
            <span className="video-time">
              {durationLabel(position * 1000)} / {durationLabel(duration * 1000)}
            </span>
          </>
        )}
      </div>
    </div>
  );
}
