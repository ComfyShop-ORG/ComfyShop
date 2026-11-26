export function mediaUrl(url: string, name: string, value: string | number) {
  return `${url}${url.includes('?') ? '&' : '?'}${name}=${encodeURIComponent(value)}`;
}
