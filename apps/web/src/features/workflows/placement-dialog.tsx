import { useState } from 'react';
import { useQueries, useQueryClient } from '@tanstack/react-query';
import { Crosshair2Icon, ReloadIcon } from '@radix-ui/react-icons';
import { IconButton, Select } from '@comfyshop/ui';
import type { Asset } from '@comfyshop/api-client';
import { Image as CanvasImage } from 'react-konva/lib/ReactKonvaCore.js';
import { t } from '../../app/i18n';
import { useWorkspace } from '../../app/use-workspace';
import { workspaceKey } from '../../app/workspace-scope';
import { assetQuery } from '../assets/asset-queries';
import { FrameEditor, FrameHistoryTools } from './frame-editor';
import FrameSelection from './frame-selection';
import { dragLayer, layerBox, moveLayer } from './placement-fields';
import type { Placement, PlacementEditor } from './placement-fields';
import { useFrameHistory } from './use-frame-history';

async function placementImage(asset: Asset, alpha: boolean) {
  const image = new Image();
  image.src = asset.media.src;
  await image.decode();
  if (!alpha && asset.contentType !== 'image/jpeg') {
    // LoadImage strips the alpha channel. A browser cannot recover hidden RGB values.
    const canvas = document.createElement('canvas');
    canvas.width = image.naturalWidth;
    canvas.height = Math.min(128, image.naturalHeight);
    const ctx = canvas.getContext('2d', { willReadFrequently: true });
    if (!ctx) throw new Error(t('outpaint.previewUnavailable'));
    for (let y = 0; y < image.naturalHeight; y += canvas.height) {
      const h = Math.min(canvas.height, image.naturalHeight - y);
      ctx.clearRect(0, 0, canvas.width, h);
      ctx.drawImage(image, 0, y, canvas.width, h, 0, 0, canvas.width, h);
      const pixels = ctx.getImageData(0, 0, canvas.width, h).data;
      for (let i = 3; i < pixels.length; i += 4)
        if (pixels[i] !== 255) throw new Error(t('layers.needsOpaque', asset.filename));
    }
  }
  return { image, name: asset.filename, width: image.naturalWidth, height: image.naturalHeight };
}
type Loaded = Awaited<ReturnType<typeof placementImage>>;

function LayerCanvas({
  editor,
  background,
  images,
  close,
}: {
  editor: PlacementEditor;
  background: Loaded;
  images: Loaded[];
  close: () => void;
}) {
  const [selected, select] = useState(0);
  const history = useFrameHistory(editor.layers.map((layer) => layer.initial));
  const [preview, setPreview] = useState<Placement | null>(null);
  const layer = editor.layers[selected];
  const original = history.current[selected];
  const current = preview ?? original;
  const image = images[selected];
  const box = layerBox(current, image);
  const centered = moveLayer(
    current,
    (background.width - box.width) / 2,
    (background.height - box.height) / 2,
    layer,
    background,
  );
  function commit(next: Placement) {
    setPreview(null);
    if (
      next.x === original.x &&
      next.y === original.y &&
      next.scale === original.scale &&
      next.turn === original.turn
    )
      return;
    history.commit(history.current.map((p, i) => (i === selected ? next : p)));
  }
  function rotate() {
    const next = { ...current, turn: (current.turn + 1) % 4 };
    const after = layerBox(next, image);
    commit(
      moveLayer(
        next,
        current.x + (box.width - after.width) / 2,
        current.y + (box.height - after.height) / 2,
        layer,
        background,
      ),
    );
  }
  return (
    <FrameEditor
      title={t('layers.title')}
      help={t('layers.help')}
      onApply={
        preview
          ? undefined
          : () => {
              editor.apply(history.current);
              close();
            }
      }
      toolbar={
        <div className="canvas-editor-toolbar placement-toolbar">
          <Select
            label={t('layers.active')}
            value={layer.field}
            options={images.map((img, i) => ({
              value: editor.layers[i].field,
              label: i + 1 + ' · ' + img.name,
            }))}
            onValueChange={(value) => {
              setPreview(null);
              select(editor.layers.findIndex((l) => l.field === value));
            }}
          />
          <div className="mask-tools">
            <IconButton
              size="large"
              label={t('outpaint.center')}
              disabled={centered.x === current.x && centered.y === current.y}
              onClick={() => commit(centered)}
            >
              <Crosshair2Icon />
            </IconButton>
            {layer.rotation && (
              <IconButton size="large" label={t('layers.rotate')} onClick={rotate}>
                <ReloadIcon />
              </IconButton>
            )}
            <FrameHistoryTools
              {...history}
              changed={history.current !== history.initial}
              reset={() => history.commit(history.initial)}
            />
          </div>
        </div>
      }
      status={
        <>
          <span>{t('frame.size', box.width, box.height)}</span>
          <span>
            X {box.x} · Y {box.y}
          </span>
          {layer.rotation && <span>{current.turn * 90}°</span>}
        </>
      }
    >
      <FrameSelection
        image={background.image}
        box={box}
        handles={!!layer.scale}
        onPick={(point) => {
          if (
            point.x >= box.x &&
            point.x < box.x + box.width &&
            point.y >= box.y &&
            point.y < box.y + box.height
          )
            return false;
          const hit = history.current.findLastIndex((p, i) => {
            const r = layerBox(p, images[i]);
            return (
              point.x >= r.x &&
              point.x < r.x + r.width &&
              point.y >= r.y &&
              point.y < r.y + r.height
            );
          });
          if (hit < 0 || hit === selected) return false;
          setPreview(null);
          select(hit);
          return true;
        }}
        onCancel={() => setPreview(null)}
        onDrag={(handle, delta, end) => {
          const next = dragLayer(original, layer, image, background, handle, delta.x, delta.y);
          if (end) commit(next);
          else setPreview(next);
        }}
      >
        {images.map((img, i) => {
          const p = i === selected ? current : history.current[i];
          const r = layerBox(p, img);
          const w = p.turn % 2 ? r.height : r.width,
            h = p.turn % 2 ? r.width : r.height;
          return (
            <CanvasImage
              key={editor.layers[i].field}
              image={img.image}
              x={r.x + r.width / 2}
              y={r.y + r.height / 2}
              width={w}
              height={h}
              offsetX={w / 2}
              offsetY={h / 2}
              rotation={p.turn * 90}
            />
          );
        })}
      </FrameSelection>
    </FrameEditor>
  );
}

export default function PlacementDialog({
  background,
  editor,
  close,
}: {
  background: Asset;
  editor: PlacementEditor;
  close: () => void;
}) {
  const { api, state, workspaceScope } = useWorkspace();
  const client = useQueryClient();
  const sources = [{ assetId: background.id, shared: background, alpha: false }, ...editor.layers];
  const queries = useQueries({
    queries: sources.map((source) => ({
      queryKey: [
        'placement-image',
        state.userId,
        ...workspaceKey(workspaceScope),
        source.assetId,
        source.alpha,
        source.shared?.media.src,
      ],
      queryFn: async () => {
        const asset =
          source.shared ??
          (await client.fetchQuery(assetQuery(api, state.userId, source.assetId, workspaceScope)));
        return placementImage(asset, source.alpha);
      },
      staleTime: Infinity,
      gcTime: 0,
      retry: false,
    })),
  });
  const error = queries.find((q) => q.error)?.error;
  const loaded = queries.flatMap((q) => (q.data ? [q.data] : []));
  if (loaded.length !== queries.length)
    return (
      <FrameEditor title={t('layers.title')} help={t('layers.help')}>
        <p className="canvas-editor-viewport" role={error ? 'alert' : 'status'}>
          {error?.message || t('common.loading')}
        </p>
      </FrameEditor>
    );
  return (
    <LayerCanvas editor={editor} background={loaded[0]} images={loaded.slice(1)} close={close} />
  );
}
