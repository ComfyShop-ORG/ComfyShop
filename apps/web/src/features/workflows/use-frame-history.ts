import { useState } from 'react';

export function useFrameHistory<T>(initial: T) {
  const [history, setHistory] = useState(() => ({ items: [initial], index: 0 }));
  return {
    current: history.items[history.index],
    initial: history.items[0],
    canUndo: history.index > 0,
    canRedo: history.index + 1 < history.items.length,
    commit(next: T) {
      setHistory(({ items, index }) => {
        const previous = items.slice(0, index + 1);
        return { items: [...previous, next], index: previous.length };
      });
    },
    navigate(delta: number) {
      setHistory((prior) => ({
        ...prior,
        index: Math.min(prior.items.length - 1, Math.max(0, prior.index + delta)),
      }));
    },
  };
}
