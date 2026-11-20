import type { Media } from '@comfyshop/api-client';

function cardLongEdge(width: number, height: number, cardWidth: number) {
  return Math.max(1, (cardWidth * Math.max(width, height)) / width);
}

function sizeAtLeast(sizes: number[], edge: number) {
  return sizes.find((size) => size >= edge) ?? sizes.at(-1)!;
}

export function cardThumbnail(media: Media, cardWidth: number) {
  const thumbnail = media.thumbnail;
  if (!thumbnail?.sizes.length || !media.width || !media.height) return null;
  const edge = cardLongEdge(media.width, media.height, cardWidth);
  const normal = sizeAtLeast(thumbnail.sizes, edge);
  const url = (size: number) => `${thumbnail.src}?size=${size}`;
  return {
    src: url(normal),
    srcSet: thumbnail.sizes
      .map((size) => `${url(size)} ${size === normal ? 1 : size / edge}x`)
      .join(', '),
  };
}

export function cardVideoPreview(media: Media, cardWidth: number) {
  const preview = media.videoPreview;
  if (!preview?.sizes.length || !media.width || !media.height) return null;
  return `${preview.src}?size=${sizeAtLeast(preview.sizes, cardLongEdge(media.width, media.height, cardWidth))}`;
}
