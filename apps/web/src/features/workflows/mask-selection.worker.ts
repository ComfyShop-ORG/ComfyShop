import { ImageSegmenter, InteractiveSegmenter } from '@mediapipe/tasks-vision';
import wasmLoaderPath from '@mediapipe/tasks-vision/vision_wasm_module_internal.js?url';
import wasmBinaryPath from '@mediapipe/tasks-vision/vision_wasm_module_internal.wasm?url';
import touchModel from './.mask-models/interactive_segmentation.task?url';
import portraitModel from './.mask-models/selfie_multiclass_256x256.tflite?url';
import type { CanvasPoint } from './canvas-viewport';

export type MaskSelection =
  { kind: 'point'; point: CanvasPoint } | { kind: 'portrait'; category: 0 | 1 | 3 | 4 };
export type SelectionRequest = { selection: MaskSelection; image?: ImageData };
export type SelectionUpdate =
  | { type: 'running' | 'loadFailed' | 'inferenceFailed' | 'empty' }
  | { type: 'region'; width: number; height: number; alpha: Uint8Array<ArrayBuffer> };

const fileset = { wasmLoaderPath, wasmBinaryPath };
let touch: InteractiveSegmenter | undefined;
let portrait: ImageSegmenter | undefined;
let categories: { width: number; height: number; data: Uint8Array } | undefined;

function send(update: SelectionUpdate) {
  self.postMessage(update, { transfer: update.type === 'region' ? [update.alpha.buffer] : [] });
}

function sendRegion(width: number, height: number, alpha: Uint8Array<ArrayBuffer>) {
  send(alpha.includes(255) ? { type: 'region', width, height, alpha } : { type: 'empty' });
}

self.onmessage = async ({ data: { selection, image } }: MessageEvent<SelectionRequest>) => {
  try {
    if (selection.kind === 'point') {
      touch ??= await InteractiveSegmenter.createFromOptions(fileset, {
        baseOptions: { modelAssetPath: touchModel, delegate: 'CPU' },
      });
    } else if (!categories) {
      portrait ??= await ImageSegmenter.createFromOptions(fileset, {
        baseOptions: { modelAssetPath: portraitModel, delegate: 'CPU' },
        runningMode: 'IMAGE',
        outputCategoryMask: true,
        outputConfidenceMasks: false,
      });
    }
  } catch {
    send({ type: 'loadFailed' });
    return;
  }
  send({ type: 'running' });
  try {
    if (selection.kind === 'point') {
      if (!touch) throw new Error('Missing interactive segmenter');
      if (image) touch.setImage(image);
      // Identify the tapped object independently. The editor adds or subtracts it from any draft.
      const mask = touch.segment([{ brushMode: 1, point: [selection.point], isCompleted: true }]);
      try {
        const alpha = Uint8Array.from(mask.getAsFloat32Array(), (value) =>
          value >= 0.5 ? 255 : 0,
        );
        sendRegion(mask.width, mask.height, alpha);
      } finally {
        mask.close();
      }
    } else {
      if (image && portrait) {
        portrait.segment(image, ({ categoryMask }) => {
          if (categoryMask)
            categories = {
              width: categoryMask.width,
              height: categoryMask.height,
              data: categoryMask.getAsUint8Array().slice(),
            };
        });
        portrait.close();
        portrait = undefined;
      }
      if (!categories) throw new Error('Missing segmentation map');
      const { width, height, data } = categories;
      const alpha = Uint8Array.from(data, (value) => (value === selection.category ? 255 : 0));
      sendRegion(width, height, alpha);
    }
  } catch {
    send({ type: 'inferenceFailed' });
  }
};
