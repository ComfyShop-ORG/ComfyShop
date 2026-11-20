export type AvatarSize = { width: number; height: number };

/** x 和 y 是图片相对方形预览中心的偏移，占预览边长的比例。 */
export type AvatarCrop = { x: number; y: number; zoom: number };

const sideAtZoom = (size: AvatarSize, zoom: number) =>
  (Math.min(size.width, size.height) * 100) / zoom;

export function constrainAvatarCrop(size: AvatarSize, crop: AvatarCrop): AvatarCrop {
  const side = sideAtZoom(size, crop.zoom);
  const limitX = (size.width / side - 1) / 2;
  const limitY = (size.height / side - 1) / 2;
  return {
    ...crop,
    x: Math.max(-limitX, Math.min(limitX, crop.x)),
    y: Math.max(-limitY, Math.min(limitY, crop.y)),
  };
}

/** 给出原图中对应预览的方形取样区域，供预览与最终导出共用。 */
export function avatarCropArea(size: AvatarSize, crop: AvatarCrop) {
  const side = sideAtZoom(size, crop.zoom);
  return {
    left: Math.max(0, Math.min(size.width - side, (size.width - side) / 2 - crop.x * side)),
    top: Math.max(0, Math.min(size.height - side, (size.height - side) / 2 - crop.y * side)),
    side,
  };
}

/** 核对文件内容，给浏览器正确的图片类型。 */
export async function readAvatarSource(file: File): Promise<Blob> {
  if (file.size > 5 * 1024 * 1024) throw new Error('头像不能超过 5 MB');
  const signature = new Uint8Array(await file.slice(0, 12).arrayBuffer());
  if (signature[0] === 0xff && signature[1] === 0xd8 && signature[2] === 0xff)
    return file.slice(0, file.size, 'image/jpeg');
  if ([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a].every((value, i) => signature[i] === value))
    return file.slice(0, file.size, 'image/png');
  const ascii = String.fromCharCode(...signature);
  if (ascii.startsWith('RIFF') && ascii.slice(8, 12) === 'WEBP')
    return file.slice(0, file.size, 'image/webp');
  throw new Error('请选择有效的 JPG、PNG 或 WebP 图片');
}
