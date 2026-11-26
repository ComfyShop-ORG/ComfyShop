/** 确认邮件里的链接打开的弹框：点「确认绑定」后，邮箱才绑定到账号并用于找回密码。 */
import { t } from '../../app/i18n.ts';
import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { CheckIcon, EnvelopeClosedIcon } from '@radix-ui/react-icons';
import { Button, Dialog, DialogClose, DialogContent, Logo } from '@comfyshop/ui';
import { useWorkspace } from '../../app/use-workspace';

export function EmailConfirmDialog({
  token,
  onClose,
}: {
  /** 确认邮件里的一次性凭据。 */
  token: string;
  /** 关闭弹框，由上层回到首页。 */
  onClose: () => void;
}) {
  const { identityApi: api } = useWorkspace();
  const queries = useQueryClient();
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState('');
  // 由用户点击后才提交：邮件网关预读链接时不会替收件人完成确认。
  async function submit() {
    if (busy) return;
    if (done) return onClose();
    setBusy(true);
    setError('');
    try {
      await api.confirmEmail(token);
      setDone(true);
      // 当前浏览器登录着这个账号时，账号设置随即显示新邮箱。
      await queries.invalidateQueries({ queryKey: ['session'] });
    } catch (error) {
      setError(error instanceof Error ? error.message : t('emailConfirmDialog.confirmationFailed'));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog.Root
      open
      onOpenChange={(open) => {
        if (!open && !busy) onClose();
      }}
    >
      <DialogContent size="compact" className="login-dialog">
        <header className="login-heading">
          <Logo />
          <Dialog.Title>
            {done ? t('emailConfirmDialog.emailLinked') : t('emailConfirmDialog.confirmEmail')}
          </Dialog.Title>
          <DialogClose label={t('common.close')} disabled={busy} />
        </header>
        <form
          noValidate
          onSubmit={(event) => {
            event.preventDefault();
            void submit();
          }}
        >
          <div className="dialog-notice" role="status">
            <span className="dialog-notice-icon" aria-hidden="true">
              {done ? <CheckIcon /> : <EnvelopeClosedIcon />}
            </span>
            {done ? (
              <div>
                <p>{t('emailConfirmDialog.thisEmailIsLinkedToYour')}</p>
                <p className="form-hint">{t('emailConfirmDialog.youCanUseItToReset')}</p>
              </div>
            ) : (
              <div>
                <p>{t('emailConfirmDialog.linkTheEmailAddressThatReceived')}</p>
                <p className="form-hint">{t('emailConfirmDialog.closeThisWindowIfYouDid')}</p>
              </div>
            )}
          </div>
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          <div className="dialog-actions">
            <Button type="submit" variant="primary" className="dialog-submit" disabled={busy}>
              {busy
                ? t('accountDialog.submitting')
                : done
                  ? t('emailConfirmDialog.done')
                  : t('emailConfirmDialog.linkEmail')}
              {!busy && <CheckIcon />}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog.Root>
  );
}
