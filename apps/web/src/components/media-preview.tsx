import { t } from '../app/i18n.ts';
import { lazy, Suspense } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useWorkspace } from '../app/use-workspace';
import type { Media } from '../domain/types';

const ModelPreview = lazy(() => import('./model-preview'));
const VideoPlayer = lazy(() => import('./media-player'));
const AudioPlayer = lazy(() =>
  import('./media-player').then(({ AudioPreview }) => ({ default: AudioPreview })),
);

function TextPreview({ src, name }: { src: string; name: string }) {
  const { state } = useWorkspace();
  const preview = useQuery({
    queryKey: ['text-preview', state.userId, src],
    queryFn: async ({ signal }) => {
      const response = await fetch(src, { signal, headers: { Range: 'bytes=0-65535' } });
      if (!response.ok) throw new Error(t('mediaPreview.textUnavailable'));
      const buffer = await response.arrayBuffer();
      const total = response.headers.get('Content-Range')?.split('/')[1];
      const clipped = Number(total) > buffer.byteLength;
      return { text: new TextDecoder().decode(buffer, { stream: clipped }), clipped };
    },
    retry: false,
  });
  if (preview.isPending) return <p role="status">{t('mediaPreview.loadingText')}</p>;
  if (!preview.data) return <p role="status">{t('mediaPreview.textUnavailable')}</p>;
  const { text, clipped } = preview.data;
  return (
    <section className="text-preview" aria-label={name}>
      <pre tabIndex={0}>{text.trim() ? text : t('mediaPreview.emptyText')}</pre>
      {clipped && <p className="form-hint">{t('mediaPreview.downloadFullText')}</p>}
    </section>
  );
}

export function MediaPreview({
  media,
  name,
  autoPlay,
  keyboardScope,
  onPosition,
}: {
  media: Media;
  name: string;
  autoPlay?: boolean;
  keyboardScope?: 'player' | 'dialog';
  onPosition?: (milliseconds: number) => void;
}) {
  if (media.kind === 'text') return <TextPreview src={media.src} name={name} />;
  if (media.kind === 'audio' && /\.(raw|pcm|mulaw|ulaw|alaw)$/i.test(media.filename ?? ''))
    return <p>{t('mediaPreview.rawAudio')}</p>;
  if (media.kind === 'audio')
    return (
      <Suspense fallback={<p role="status">{t('common.loading')}</p>}>
        <AudioPlayer src={media.src} name={name} />
      </Suspense>
    );
  if (media.kind === '3d') {
    if (media.filename && /\.(fbx|obj|mtl|stl|usdz|3mf|zip)$/i.test(media.filename))
      return <p role="status">{t('modelPreview.previewUnavailableDownloadTheOriginalTo')}</p>;
    return (
      <Suspense fallback={<span role="status">{t('mediaPreview.loadingModel')}</span>}>
        <ModelPreview key={media.src} src={media.src} name={name} />
      </Suspense>
    );
  }
  const image = (
    <img
      className="preview-image"
      src={media.src}
      width={media.width ?? undefined}
      height={media.height ?? undefined}
      alt={name}
    />
  );
  if (!media.video) return image;
  return (
    <Suspense fallback={media.src ? image : null}>
      <VideoPlayer
        src={media.video}
        name={name}
        poster={media.src}
        width={media.width}
        height={media.height}
        autoPlay={autoPlay}
        keyboardScope={keyboardScope}
        onPosition={onPosition}
      />
    </Suspense>
  );
}
