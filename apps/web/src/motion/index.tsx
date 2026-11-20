/** 应用内动效的唯一入口。时长取自 tokens，系统开启「减少动态效果」时自动停用。 */
import type { ComponentProps, ReactNode } from 'react';
import { AnimatePresence, LazyMotion, MotionConfig } from 'motion/react';
import * as m from 'motion/react-m';
import { motion as durations } from '@comfyshop/tokens';

const seconds = (value: string) => Number.parseFloat(value) / 1000;
const ease = [0.16, 1, 0.3, 1] as const;
const loadFeatures = () => import('./features').then((module) => module.default);

export function MotionRoot({ children }: { children: ReactNode }) {
  return (
    <LazyMotion features={loadFeatures} strict>
      <MotionConfig reducedMotion="user" transition={{ duration: seconds(durations.normal), ease }}>
        {children}
      </MotionConfig>
    </LazyMotion>
  );
}

/**
 * 同一 `group` 内当前选中项的底色，切换时滑到新的选中项。
 * 只沿水平方向移动：页面滚动位置变化时，吸顶导航里的标记不会上下飞动。
 */
export function ActiveMark({ group }: { group: string }) {
  return <m.span layoutId={group} layout="x" className="active-mark" aria-hidden="true" />;
}

/** 增删条目时保持其余条目平滑补位的列表容器。首次渲染不播放进入动画。 */
export function ListPresence({ children }: { children: ReactNode }) {
  return (
    <AnimatePresence initial={false} mode="popLayout">
      {children}
    </AnimatePresence>
  );
}

/** 列表条目：进入时淡入，移除时淡出，位置变化时平滑移动。 */
export function ListItem(props: ComponentProps<typeof m.article>) {
  return (
    <m.article
      layout="position"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0, transition: { duration: seconds(durations.fast) } }}
      {...props}
    />
  );
}
