import assert from 'node:assert/strict';
import { test } from 'node:test';
import { avatarCropArea, constrainAvatarCrop, readAvatarSource } from './avatar-crop.ts';

void test('avatar panning stays on the source image at both zoom levels', () => {
  const landscape = { width: 1200, height: 600 };
  const centered = avatarCropArea(landscape, { x: 0, y: 0, zoom: 100 });
  assert.deepEqual(centered, { left: 300, top: 0, side: 600 });
  const edge = constrainAvatarCrop(landscape, { x: 2, y: -1, zoom: 100 });
  assert.deepEqual(avatarCropArea(landscape, edge), { left: 0, top: 0, side: 600 });

  const portrait = { width: 600, height: 1200 };
  const zoomed = constrainAvatarCrop(portrait, { x: 2, y: -3, zoom: 200 });
  assert.deepEqual(avatarCropArea(portrait, zoomed), { left: 0, top: 900, side: 300 });
});

void test('avatar image types are read from bytes, and oversized or foreign files are rejected', async () => {
  const png = new Uint8Array([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);
  const source = await readAvatarSource(new File([png], 'portrait.png'));
  assert.equal(source.type, 'image/png');
  await assert.rejects(readAvatarSource(new File(['<svg/>'], 'portrait.png')), /有效的 JPG/);
  const large = new File([new Uint8Array(5 * 1024 * 1024 + 1)], 'large.png');
  await assert.rejects(readAvatarSource(large), /5 MB/);
});
