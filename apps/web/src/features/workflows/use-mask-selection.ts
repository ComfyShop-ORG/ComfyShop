import { useEffect, useRef, useState } from 'react';
import { maskBitmap, regionBitmap } from './mask-bitmap';
import type { MaskRegion, SelectionMode } from './mask-bitmap';
import type { MaskSelection, SelectionRequest, SelectionUpdate } from './mask-selection.worker';

type SelectionStatus = 'loading' | 'running' | 'loadFailed' | 'inferenceFailed' | 'empty';

function modelInput(image: HTMLImageElement) {
  const scale = Math.min(1, 1024 / Math.max(image.naturalWidth, image.naturalHeight));
  const canvas = maskBitmap(image, scale);
  try {
    const ctx = canvas.getContext('2d', { willReadFrequently: true });
    if (!ctx) throw new Error('Canvas unavailable');
    ctx.drawImage(image, 0, 0, canvas.width, canvas.height);
    return ctx.getImageData(0, 0, canvas.width, canvas.height);
  } finally {
    canvas.width = canvas.height = 1;
  }
}

export function useMaskSelection(
  image: HTMLImageElement | null | undefined,
  commit: (change: MaskRegion) => void,
) {
  const session = useRef<{ worker: Worker; kind: MaskSelection['kind']; busy: boolean } | null>(
    null,
  );
  const [status, setStatus] = useState<SelectionStatus>();
  useEffect(
    () => () => {
      session.current?.worker.terminate();
      session.current = null;
    },
    [image],
  );

  function cancel() {
    if (session.current?.busy) {
      session.current.worker.terminate();
      session.current = null;
    }
    setStatus(undefined);
  }

  function select(selection: MaskSelection, mode: SelectionMode) {
    if (!image || session.current?.busy) return;
    try {
      let pixels: ImageData | undefined;
      if (session.current?.kind !== selection.kind) {
        session.current?.worker.terminate();
        session.current = null;
        pixels = modelInput(image);
        const worker = new Worker(new URL('./mask-selection.worker.ts', import.meta.url), {
          type: 'module',
        });
        session.current = { worker, kind: selection.kind, busy: false };
      }
      const active = session.current;
      active.busy = true;
      setStatus(pixels ? 'loading' : 'running');
      const fail = (reason: 'loadFailed' | 'inferenceFailed') => {
        active.worker.terminate();
        if (session.current !== active) return;
        session.current = null;
        setStatus(reason);
      };
      active.worker.onerror = () => fail('loadFailed');
      active.worker.onmessageerror = () => fail('inferenceFailed');
      active.worker.onmessage = ({ data }: MessageEvent<SelectionUpdate>) => {
        if (session.current !== active) return;
        if (data.type === 'loadFailed' || data.type === 'inferenceFailed') return fail(data.type);
        active.busy = data.type === 'running';
        if (data.type !== 'region') return setStatus(data.type);
        try {
          commit({ region: regionBitmap(data.width, data.height, data.alpha), mode });
          setStatus(undefined);
        } catch {
          fail('inferenceFailed');
        }
      };
      const request: SelectionRequest = { selection, image: pixels };
      active.worker.postMessage(request, pixels ? [pixels.data.buffer] : []);
    } catch {
      session.current?.worker.terminate();
      session.current = null;
      setStatus('loadFailed');
    }
  }

  return { select, cancel, status, busy: status === 'loading' || status === 'running' };
}
