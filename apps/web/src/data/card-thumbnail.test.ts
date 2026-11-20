import assert from 'node:assert/strict';
import { test } from 'node:test';
import { cardThumbnail, cardVideoPreview } from './card-thumbnail.ts';
import type { Media } from '@comfyshop/api-client';

const thumbnail = { src: '/api/v1/artifacts/example/thumbnail', sizes: [160, 256, 384, 512, 768] };
const portrait: Media = {
  src: '/api/v1/artifacts/example/file',
  width: 512,
  height: 768,
  video: null,
  videoPreview: null,
  thumbnail,
};

void test('card sources use the rendered long edge and expose higher pixel densities', () => {
  const sources = cardThumbnail(portrait, 128);
  assert.equal(sources?.src, thumbnail.src + '?size=256');
  assert.match(sources?.srcSet ?? '', /size=384 2x/);
  assert.match(sources?.srcSet ?? '', /size=768 4x/);
  assert.equal(cardThumbnail(portrait, 280)?.src, thumbnail.src + '?size=512');
  assert.equal(
    cardThumbnail({ ...portrait, width: 768, height: 512 }, 200)?.src,
    thumbnail.src + '?size=256',
  );
});

void test('card sources cap at the server variant and never use the original file', () => {
  assert.equal(cardThumbnail(portrait, 1000)?.src, thumbnail.src + '?size=768');
  assert.equal(cardThumbnail({ ...portrait, thumbnail: null }, 128), null);
});

void test('hover clips use the card dimensions and the server preview URL', () => {
  const videoPreview = { src: '/api/v1/artifacts/example/video-preview', sizes: [160, 256, 384] };
  const video = { ...portrait, video: portrait.src, videoPreview };
  assert.equal(cardVideoPreview(video, 128), videoPreview.src + '?size=256');
  assert.equal(cardVideoPreview(video, 1000), videoPreview.src + '?size=384');
  assert.equal(cardVideoPreview(portrait, 128), null);
});
