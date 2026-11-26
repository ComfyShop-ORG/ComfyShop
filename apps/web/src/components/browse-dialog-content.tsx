import { t } from '../app/i18n.ts';
import { forwardRef, useImperativeHandle, useLayoutEffect, useRef } from 'react';
import type { ComponentPropsWithoutRef, ReactNode, RefObject } from 'react';
import { ChevronLeftIcon, ChevronRightIcon } from '@radix-ui/react-icons';
import { Dialog, DialogClose, DialogContent, IconButton } from '@comfyshop/ui';
import type { ItemDirection } from '../data/collection-position';
import type { CollectionNavigation } from './use-collection-navigation';
import { useDialogFocus } from './use-dialog-focus';

const arrowConsumers =
  "input, textarea, select, video, audio, [contenteditable]:not([contenteditable='false']), [role=combobox], [role=listbox], [role=slider], [role=tablist], [role=toolbar], [role=menu], [role=radiogroup], .playback-controls";

type BrowseDialogProps = ComponentPropsWithoutRef<typeof DialogContent> & {
  itemId: string;
  navigation?: CollectionNavigation;
  onVerticalMove?: (direction: ItemDirection) => boolean;
  titleRef: RefObject<HTMLHeadingElement | null>;
};

export const BrowseDialogContent = forwardRef<HTMLDivElement, BrowseDialogProps>(
  function BrowseDialogContent(
    { children, itemId, navigation, onVerticalMove, titleRef, onKeyDown, ...props },
    ref,
  ) {
    const content = useRef<HTMLDivElement>(null);
    const previousId = useRef(itemId);
    useImperativeHandle(ref, () => content.current!, []);
    useLayoutEffect(() => {
      if (
        previousId.current !== itemId &&
        content.current &&
        !content.current.closest('[aria-hidden="true"]') &&
        !content.current.contains(document.activeElement)
      ) {
        titleRef.current?.focus({ preventScroll: true });
      }
      previousId.current = itemId;
    }, [itemId, titleRef]);
    function move(direction: ItemDirection) {
      const stillActive = () =>
        !!content.current?.isConnected && !content.current.closest('[aria-hidden="true"]');
      if (stillActive()) navigation?.move(direction, stillActive);
    }
    return (
      <DialogContent
        ref={content}
        {...props}
        onKeyDown={(event) => {
          onKeyDown?.(event);
          if (
            (!navigation && !onVerticalMove) ||
            event.defaultPrevented ||
            event.altKey ||
            event.ctrlKey ||
            event.metaKey ||
            event.shiftKey ||
            event.repeat ||
            event.nativeEvent.isComposing ||
            !(event.target instanceof Element) ||
            event.target.closest('[role="dialog"], [role="alertdialog"]') !== event.currentTarget ||
            event.currentTarget.closest('[aria-hidden="true"]') ||
            event.target.closest(arrowConsumers)
          )
            return;
          if (event.key === 'ArrowLeft' && navigation?.previous) {
            event.preventDefault();
            move(-1);
          } else if (event.key === 'ArrowRight' && navigation?.next) {
            event.preventDefault();
            move(1);
          } else if (
            (event.key === 'ArrowUp' || event.key === 'ArrowDown') &&
            onVerticalMove?.(event.key === 'ArrowUp' ? -1 : 1)
          ) {
            event.preventDefault();
          }
        }}
      >
        {children}
        {navigation && (
          <nav className="dialog-navigation" aria-label={t('browseDialogContent.browsePreviews')}>
            <IconButton
              variant="secondary"
              size="large"
              className="dialog-previous"
              label={t('browseDialogContent.previousItem')}
              aria-disabled={!navigation.previous}
              onClick={() => move(-1)}
            >
              <ChevronLeftIcon />
            </IconButton>
            <span className="dialog-position" role="status">
              {navigation.error ||
                (navigation.pending
                  ? t('browseDialogContent.loading')
                  : navigation.total
                    ? `${navigation.position} / ${navigation.total}`
                    : `${navigation.position} / ${navigation.loaded}+`)}
            </span>
            <IconButton
              variant="secondary"
              size="large"
              className="dialog-next"
              label={t('browseDialogContent.nextItem')}
              aria-disabled={!navigation.next}
              onClick={() => move(1)}
            >
              <ChevronRightIcon />
            </IconButton>
          </nav>
        )}
      </DialogContent>
    );
  },
);

/**
 * 可在相邻条目间切换的详情弹框：标题、标题栏操作、关闭按钮和焦点恢复。
 * @param itemId 当前条目。切换后焦点回到标题。
 * @param actions 标题栏的附加操作。
 */
export function BrowseDialog({
  className,
  itemId,
  title,
  navigation,
  actions,
  onClose,
  onEscape,
  restoreFocus,
  children,
}: {
  /** Escape 先交给它处理。返回真表示已处理，弹框保持打开。 */
  onEscape?: () => boolean;
  className: string;
  itemId: string;
  title: string;
  navigation?: CollectionNavigation;
  actions?: ReactNode;
  onClose: () => void;
  restoreFocus?: () => void;
  children: ReactNode;
}) {
  const { titleRef, focusProps } = useDialogFocus(restoreFocus);
  return (
    <Dialog.Root
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <BrowseDialogContent
        className={className}
        itemId={itemId}
        titleRef={titleRef}
        navigation={navigation}
        onEscapeKeyDown={(event) => {
          if (onEscape?.()) event.preventDefault();
        }}
        {...focusProps}
      >
        <header className="workflow-dialog-heading dialog-heading-wrap">
          <Dialog.Title ref={titleRef} tabIndex={-1}>
            {title}
          </Dialog.Title>
          {actions && <div className="dialog-heading-actions">{actions}</div>}
          <DialogClose label={t('common.close')} size="small" />
        </header>
        {children}
      </BrowseDialogContent>
    </Dialog.Root>
  );
}
