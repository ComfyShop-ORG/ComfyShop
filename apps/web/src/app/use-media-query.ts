import { useCallback, useSyncExternalStore } from 'react';

export function useMediaQuery(query: string) {
  const subscribe = useCallback(
    (update: () => void) => {
      const media = window.matchMedia(query);
      media.addEventListener('change', update);
      return () => media.removeEventListener('change', update);
    },
    [query],
  );
  const matches = useCallback(() => window.matchMedia(query).matches, [query]);
  return useSyncExternalStore(subscribe, matches);
}
