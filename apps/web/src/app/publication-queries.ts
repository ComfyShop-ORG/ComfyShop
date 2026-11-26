import type { QueryClient } from '@tanstack/react-query';

export function refreshPublishedContent(queries: QueryClient) {
  return Promise.all(
    ['workflows', 'works', 'public-team'].map((key) =>
      queries.invalidateQueries({ queryKey: [key] }),
    ),
  );
}
