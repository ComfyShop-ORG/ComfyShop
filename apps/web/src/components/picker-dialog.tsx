import { useState } from 'react';
import type { ReactNode } from 'react';
import { Dialog, DialogClose, DialogContent } from '@comfyshop/ui';
import { t } from '../app/i18n';
import { useDialogFocus } from './use-dialog-focus';

export function PickerDialog({
  trigger,
  title,
  onCloseAutoFocus,
  children,
}: {
  trigger: ReactNode;
  title: string;
  onCloseAutoFocus?: (event: Event) => void;
  children: (scrollRoot: HTMLDivElement, close: () => void) => ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const [opening, setOpening] = useState(0);
  return (
    <Dialog.Root
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (next) setOpening((current) => current + 1);
      }}
    >
      <Dialog.Trigger asChild>{trigger}</Dialog.Trigger>
      <PickerDialogContent title={title} opening={opening} onCloseAutoFocus={onCloseAutoFocus}>
        {(scrollRoot) => children(scrollRoot, () => setOpen(false))}
      </PickerDialogContent>
    </Dialog.Root>
  );
}

export function PickerDialogContent({
  title,
  opening,
  onCloseAutoFocus,
  children,
}: {
  title: string;
  opening?: number;
  onCloseAutoFocus?: (event: Event) => void;
  children: (scrollRoot: HTMLDivElement) => ReactNode;
}) {
  const { titleRef, focusProps } = useDialogFocus();
  const [scrollRoot, setScrollRoot] = useState<HTMLDivElement | null>(null);
  return (
    <DialogContent className="result-dialog" {...focusProps} onCloseAutoFocus={onCloseAutoFocus}>
      <header className="workflow-dialog-heading dialog-heading-wrap">
        <Dialog.Title ref={titleRef} tabIndex={-1}>
          {title}
        </Dialog.Title>
        <DialogClose label={t('common.close')} size="small" />
      </header>
      <div className="collection-scroll" key={opening} ref={setScrollRoot}>
        {scrollRoot && children(scrollRoot)}
      </div>
    </DialogContent>
  );
}
