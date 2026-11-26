import { t } from '../app/i18n.ts';
import { useId, useRef, useState } from 'react';
import type { MouseEvent, ReactNode } from 'react';
import { Link2Icon, Share1Icon } from '@radix-ui/react-icons';
import { Button, Dialog, DialogClose, DialogContent, IconButton, Input } from '@comfyshop/ui';
import type { ButtonProps } from '@comfyshop/ui';
import { copyText } from '../data/clipboard';
import { useNotify } from './notify';

/**
 * 使用剪贴板；局域网 HTTP 等环境无法自动复制时，提供同一个可选择的链接。
 * 按钮本身只负责复制，不作为弹框触发器，关闭弹框后焦点回到按钮。
 * @param children 主按钮的内容；省略时使用图标按钮。
 */
export function CopyLink({
  href,
  title,
  shareTitle,
  reserveShareSlot = false,
  onCopied,
  children,
  size = 'small',
  variant,
}: {
  href: string;
  title: string;
  shareTitle?: string;
  reserveShareSlot?: boolean;
  onCopied?: () => void;
  children?: ReactNode;
  size?: ButtonProps['size'];
  variant?: ButtonProps['variant'];
}) {
  const url = new URL(href, window.location.href).href;
  const description = useId();
  const input = useRef<HTMLInputElement>(null);
  const origin = useRef<HTMLButtonElement | null>(null);
  const [open, setOpen] = useState(false);
  const notify = useNotify();
  const share = { title: shareTitle ?? title, url };
  const canShare = typeof navigator.share === 'function' && (navigator.canShare?.(share) ?? true);
  const copy = (event: MouseEvent<HTMLButtonElement>) => {
    origin.current = event.currentTarget;
    void copyText(url).then((copied) => {
      if (!copied) setOpen(true);
      else if (onCopied) onCopied();
      else notify(t('copyLink.copied', title));
    });
  };
  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      {children ? (
        <Button size={size} variant={variant ?? 'primary'} onClick={copy}>
          {children}
        </Button>
      ) : (
        <IconButton size={size} variant={variant} label={t('copyLink.copy', title)} onClick={copy}>
          <Link2Icon />
        </IconButton>
      )}
      {canShare && (shareTitle || reserveShareSlot) && (
        <IconButton
          size={size}
          label={t('copyLink.systemShare')}
          disabled={!shareTitle}
          aria-hidden={!shareTitle || undefined}
          style={!shareTitle ? { visibility: 'hidden' } : undefined}
          onClick={() => {
            void navigator.share(share).catch((error: unknown) => {
              if (!(error instanceof DOMException && error.name === 'AbortError'))
                notify(t('copyLink.shareUnavailable'));
            });
          }}
        >
          <Share1Icon />
        </IconButton>
      )}
      <DialogContent
        size="compact"
        aria-describedby={description}
        onOpenAutoFocus={(event) => {
          event.preventDefault();
          input.current?.focus();
          input.current?.select();
        }}
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          if (origin.current?.isConnected) origin.current.focus();
        }}
      >
        <div className="compact-dialog-heading">
          <Dialog.Title>{title}</Dialog.Title>
          <DialogClose label={t('common.close')} />
        </div>
        <Dialog.Description id={description} className="form-hint">
          {t('copyLink.copyTheLinkBelowManually')}
        </Dialog.Description>
        <Input ref={input} aria-label={title} value={url} readOnly />
      </DialogContent>
    </Dialog.Root>
  );
}
