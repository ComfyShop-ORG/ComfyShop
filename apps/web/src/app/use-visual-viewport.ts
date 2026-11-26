import { useEffect } from 'react';

/** 软键盘可以只缩小可视视口。弹框用它的高度和位置，页面仍由浏览器滚动和缩放。 */
export function useVisualViewport() {
  useEffect(() => {
    const viewport = window.visualViewport;
    if (!viewport) return;
    const style = document.documentElement.style;
    let frame = 0;
    function update() {
      frame = 0;
      if (viewport && viewport.scale === 1 && viewport.height > 0) {
        style.setProperty('--ui-viewport-height', `${viewport.height}px`);
        style.setProperty('--ui-viewport-top', `${viewport.offsetTop}px`);
      } else {
        style.removeProperty('--ui-viewport-height');
        style.removeProperty('--ui-viewport-top');
      }
    }
    function schedule() {
      if (!frame) frame = requestAnimationFrame(update);
    }
    update();
    viewport.addEventListener('resize', schedule);
    viewport.addEventListener('scroll', schedule);
    return () => {
      viewport.removeEventListener('resize', schedule);
      viewport.removeEventListener('scroll', schedule);
      cancelAnimationFrame(frame);
      style.removeProperty('--ui-viewport-height');
      style.removeProperty('--ui-viewport-top');
    };
  }, []);
}
