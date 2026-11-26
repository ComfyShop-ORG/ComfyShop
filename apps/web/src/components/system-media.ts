import { useEffect, useState } from 'react';
import type { RefObject } from 'react';

type PresentationMode = 'inline' | 'picture-in-picture';
type SafariVideo = HTMLVideoElement & {
  webkitPresentationMode?: string;
  webkitSupportsPresentationMode?: (mode: PresentationMode) => boolean;
  webkitSetPresentationMode?: (mode: PresentationMode) => void;
};

function pictureInPictureMode(video: SafariVideo) {
  if (video.disablePictureInPicture || !video.videoWidth) return;
  if (document.pictureInPictureEnabled && typeof video.requestPictureInPicture === 'function')
    return 'standard';
  if (
    video.webkitSetPresentationMode &&
    video.webkitSupportsPresentationMode?.('picture-in-picture')
  )
    return 'safari';
}

export function usePictureInPicture(ref: RefObject<HTMLVideoElement | null>) {
  const [state, setState] = useState({ available: false, active: false });
  useEffect(() => {
    const video: SafariVideo | null = ref.current;
    if (!video) return;
    function sync() {
      if (!video) return;
      const available = !!pictureInPictureMode(video);
      const active =
        document.pictureInPictureElement === video ||
        video.webkitPresentationMode === 'picture-in-picture';
      setState((previous) =>
        previous.available === available && previous.active === active
          ? previous
          : { available, active },
      );
    }
    const events = [
      'loadedmetadata',
      'emptied',
      'enterpictureinpicture',
      'leavepictureinpicture',
      'webkitpresentationmodechanged',
    ];
    const frame = requestAnimationFrame(sync);
    for (const event of events) video.addEventListener(event, sync);
    return () => {
      cancelAnimationFrame(frame);
      for (const event of events) video.removeEventListener(event, sync);
    };
  }, [ref]);

  async function toggle() {
    const video: SafariVideo | null = ref.current;
    if (!video) return;
    switch (pictureInPictureMode(video)) {
      case 'standard':
        if (document.pictureInPictureElement === video) await document.exitPictureInPicture();
        else await video.requestPictureInPicture();
        break;
      case 'safari':
        video.webkitSetPresentationMode?.(
          video.webkitPresentationMode === 'picture-in-picture' ? 'inline' : 'picture-in-picture',
        );
        break;
    }
  }

  return { ...state, toggle };
}

let activeMedia: HTMLMediaElement | null = null;

export function useSystemPlayback(
  ref: RefObject<HTMLMediaElement | null>,
  title: string,
  poster?: string,
) {
  useEffect(() => {
    const media = ref.current;
    const session = navigator.mediaSession;
    if (!media || !session) return;
    const element = media;
    const controls = session;

    function seek(time: number) {
      if (Number.isFinite(element.duration))
        element.currentTime = Math.min(element.duration, Math.max(0, time));
    }
    const actions: Partial<Record<MediaSessionAction, MediaSessionActionHandler>> = {
      play: () => void element.play().catch(() => undefined),
      pause: () => element.pause(),
      seekto: ({ seekTime }) => {
        if (seekTime !== undefined) seek(seekTime);
      },
      seekbackward: ({ seekOffset }) => seek(element.currentTime - (seekOffset ?? 10)),
      seekforward: ({ seekOffset }) => seek(element.currentTime + (seekOffset ?? 10)),
    };

    function listen(enable: boolean) {
      for (const [action, handler] of Object.entries(actions)) {
        try {
          controls.setActionHandler(action as MediaSessionAction, enable ? handler : null);
        } catch {
          // 不同浏览器开放的系统媒体按键不同。
        }
      }
    }

    function sync() {
      if (activeMedia !== element) return;
      controls.playbackState = element.paused ? 'paused' : 'playing';
      if (Number.isFinite(element.duration) && element.duration > 0) {
        controls.setPositionState?.({
          duration: element.duration,
          playbackRate: element.playbackRate,
          position: Math.min(element.duration, element.currentTime),
        });
      }
    }

    function activate() {
      if (activeMedia !== element) {
        activeMedia = element;
        if (typeof MediaMetadata === 'function') {
          controls.metadata = new MediaMetadata({
            title,
            artist: 'ComfyShop',
            artwork: poster ? [{ src: new URL(poster, location.href).href }] : [],
          });
        }
        listen(true);
      }
      sync();
    }

    const events = ['pause', 'ended', 'seeked', 'durationchange', 'ratechange'];
    element.addEventListener('play', activate);
    for (const event of events) element.addEventListener(event, sync);
    if (!element.paused) activate();
    return () => {
      element.removeEventListener('play', activate);
      for (const event of events) element.removeEventListener(event, sync);
      if (activeMedia === element) {
        activeMedia = null;
        controls.metadata = null;
        controls.playbackState = 'none';
        controls.setPositionState?.();
        listen(false);
      }
    };
  }, [ref, title, poster]);
}
