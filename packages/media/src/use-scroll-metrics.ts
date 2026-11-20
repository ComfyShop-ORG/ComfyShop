import { useLayoutEffect, useRef, useState } from 'react';
import type { RefObject } from 'react';

interface Metrics {
  width: number;
  height: number;
  scrollTop: number;
  isScrolling: boolean;
}

/** Normalize window and element scrolling to the feed's own coordinate space. */
export function useScrollMetrics(
  container: RefObject<HTMLDivElement | null>,
  root: HTMLElement | null,
) {
  const [metrics, setMetrics] = useState<Metrics>({
    width: 0,
    height: 0,
    scrollTop: 0,
    isScrolling: false,
  });
  const scrolling = useRef(false);
  useLayoutEffect(() => {
    const element = container.current;
    if (!element) return;
    const target = root ?? window;
    let frame = 0;
    let idle: ReturnType<typeof setTimeout>;
    function measure() {
      frame = 0;
      const bounds = element!.getBoundingClientRect();
      const top = root ? root.getBoundingClientRect().top + root.clientTop : 0;
      const next: Metrics = {
        width: Math.floor(bounds.width),
        height: root ? root.clientHeight : window.innerHeight,
        scrollTop: Math.max(0, top - bounds.top),
        isScrolling: scrolling.current,
      };
      setMetrics((previous) =>
        Object.keys(next).every(
          (key) => previous[key as keyof Metrics] === next[key as keyof Metrics],
        )
          ? previous
          : next,
      );
    }
    function schedule() {
      if (!frame) frame = requestAnimationFrame(measure);
    }
    function onScroll() {
      scrolling.current = true;
      schedule();
      clearTimeout(idle);
      idle = setTimeout(() => {
        scrolling.current = false;
        schedule();
      }, 120);
    }
    const observer = new ResizeObserver(schedule);
    observer.observe(element);
    if (root) observer.observe(root);
    target.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', schedule);
    measure();
    return () => {
      observer.disconnect();
      target.removeEventListener('scroll', onScroll);
      window.removeEventListener('resize', schedule);
      cancelAnimationFrame(frame);
      clearTimeout(idle);
    };
  }, [container, root]);
  return metrics;
}
