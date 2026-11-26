export type ItemDirection = -1 | 1;

export function collectionPosition<Item extends { id: string }>(
  items: readonly Item[],
  id: string,
  hasNextPage: boolean,
):
  | { index: number; previous: Item | undefined; next: Item | undefined; atPageBoundary: boolean }
  | undefined {
  const index = items.findIndex((item) => item.id === id);
  if (index === -1) return undefined;
  return {
    index,
    previous: items[index - 1],
    next: items[index + 1],
    atPageBoundary: index === items.length - 1 && hasNextPage,
  };
}
