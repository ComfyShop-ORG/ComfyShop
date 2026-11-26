import { t } from '../../app/i18n.ts';
import { useId, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import type { ReactNode, RefObject } from 'react';
import {
  ArrowLeftIcon,
  ArrowRightIcon,
  CheckIcon,
  EnvelopeClosedIcon,
  EyeClosedIcon,
  EyeOpenIcon,
} from '@radix-ui/react-icons';
import {
  Button,
  Dialog,
  DialogClose,
  DialogContent,
  Field,
  IconButton,
  Input,
  Logo,
} from '@comfyshop/ui';
import { ApiError } from '@comfyshop/api-client';
import { useWorkspace } from '../../app/use-workspace';

/**
 * 需要登录才能继续的操作入口。已登录时直接执行 `action`。
 * @param reason 登录框里说明登录后会做什么，例如「登录后收藏」。
 */
export type RequireAuth = (
  source: HTMLElement,
  action?: () => void | Promise<void>,
  reason?: string,
) => void;

/** 登录框的几个步骤。找回密码和设置新密码都在同一个弹框里完成。 */
type Mode = 'login' | 'register' | 'forgot' | 'sent' | 'reset' | 'reset-done';
type Errors = {
  account?: string;
  password?: string;
  confirm?: string;
  email?: string;
  form?: string;
};

const titles: Record<Mode, string> = {
  login: t('app.signIn'),
  register: t('loginDialog.register'),
  forgot: t('loginDialog.resetPassword'),
  sent: t('loginDialog.checkYourEmail'),
  reset: t('loginDialog.setANewPassword'),
  'reset-done': t('loginDialog.passwordReset'),
};

const emailPattern = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

const passwordIssue = (value: string) => {
  const length = [...value].length;
  return length < 8 || length > 128 ? t('loginDialog.useCharactersForThePassword') : undefined;
};

/** 带错误提示的输入框。错误通过 `aria-describedby` 关联到输入框。 */
function TextField({
  id,
  label,
  detail,
  error,
  inputRef,
  trailing,
  ...input
}: React.ComponentProps<typeof Input> & {
  id: string;
  label: string;
  detail?: ReactNode;
  error?: string;
  inputRef?: RefObject<HTMLInputElement | null>;
  trailing?: ReactNode;
}) {
  const control = (
    <Input
      ref={inputRef}
      id={id}
      aria-invalid={error ? true : undefined}
      aria-describedby={error ? id + '-error' : undefined}
      required
      {...input}
    />
  );
  return (
    <Field label={label} htmlFor={id} detail={detail}>
      {trailing ? (
        <div className="field-with-action">
          {control}
          {trailing}
        </div>
      ) : (
        control
      )}
      {error && (
        <p className="form-error" role="alert" id={id + '-error'}>
          {error}
        </p>
      )}
    </Field>
  );
}

export function LoginDialog({
  open,
  onOpenChange,
  onSuccess,
  restoreFocus,
  reason,
  resetToken,
}: {
  /** 触发登录的操作说明，显示在标题下方。 */
  reason?: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess?: () => void;
  restoreFocus: () => void;
  /** 邮件里的重置凭据。传入时弹框从「设置新密码」开始。 */
  resetToken?: string;
}) {
  const id = useId();
  const firstField = useRef<HTMLInputElement>(null);
  const passwordRef = useRef<HTMLInputElement>(null);
  const confirmRef = useRef<HTMLInputElement>(null);
  const emailRef = useRef<HTMLInputElement>(null);
  const [mode, setMode] = useState<Mode>(resetToken ? 'reset' : 'login');
  const [account, setAccount] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [email, setEmail] = useState('');
  const [revealed, setRevealed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<Errors>({});
  const { identityApi: api, workspace } = useWorkspace();
  const queries = useQueryClient();
  // 每次打开都从登录（或邮件链接的设置新密码）开始。关闭可能来自导航而不经过
  // `onOpenChange`，所以在打开时重置；关闭动画期间保持原来的内容。
  const [shown, setShown] = useState(open);
  if (open !== shown) {
    setShown(open);
    if (open) {
      setMode(resetToken ? 'reset' : 'login');
      setErrors({});
      setPassword('');
      setConfirm('');
      setRevealed(false);
    }
  }

  function go(next: Mode) {
    setMode(next);
    setErrors({});
    setPassword('');
    setConfirm('');
    setRevealed(false);
    requestAnimationFrame(() => firstField.current?.focus());
  }
  function edit(field: keyof Errors, set: (value: string) => void) {
    return (event: React.ChangeEvent<HTMLInputElement>) => {
      set(event.target.value);
      setErrors((previous) => ({ ...previous, [field]: undefined, form: undefined }));
    };
  }
  /** 提交前的本地校验。有问题时聚焦第一个出错的字段并返回假。 */
  function validate(issues: Errors) {
    setErrors(issues);
    const first = issues.account
      ? firstField
      : issues.password
        ? mode === 'reset'
          ? firstField
          : passwordRef
        : issues.confirm
          ? confirmRef
          : issues.email
            ? mode === 'register'
              ? emailRef
              : firstField
            : null;
    first?.current?.focus();
    return !first;
  }
  async function run(
    action: () => Promise<void>,
    fallback: string,
    onError?: (e: unknown) => Errors,
  ) {
    setBusy(true);
    try {
      await action();
    } catch (error) {
      const message = error instanceof Error ? error.message : fallback;
      setErrors(onError?.(error) ?? { form: message });
    } finally {
      setBusy(false);
    }
  }

  async function submit() {
    if (busy) return;
    if (mode === 'login' || mode === 'register') {
      const username = account.normalize('NFKC').trim();
      const accountLength = [...username].length;
      const issues: Errors = {};
      if (accountLength < 2 || accountLength > 32)
        issues.account = t('loginDialog.useCharactersForYourUsername');
      else if (!/^[\p{L}\p{N}_-]+$/u.test(username))
        issues.account = t('loginDialog.useLettersChineseCharactersDigitsUnderscores');
      issues.password = passwordIssue(password);
      if (!issues.password && mode === 'register' && confirm !== password)
        issues.confirm = t('loginDialog.thePasswordsDoNotMatch');
      const recovery = mode === 'register' ? email.trim() : '';
      if (recovery && !emailPattern.test(recovery))
        issues.email = t('loginDialog.enterAValidEmailAddressOr');
      if (!validate(issues)) return;
      const register = mode === 'register';
      await run(
        async () => {
          await workspace.signIn(username, password, register, recovery);
          setPassword('');
          setConfirm('');
          setMode('login');
          onSuccess?.();
        },
        register ? t('loginDialog.registrationFailed') : t('loginDialog.signInFailed'),
        (error) =>
          register && error instanceof ApiError && error.status === 409
            ? { account: error.message }
            : {
                form:
                  error instanceof Error
                    ? error.message
                    : register
                      ? t('loginDialog.registrationFailed')
                      : t('loginDialog.signInFailed'),
              },
      );
    } else if (mode === 'forgot') {
      const value = email.trim();
      if (
        !validate({
          email: emailPattern.test(value) ? undefined : t('accountDialog.enterAValidEmailAddress'),
        })
      )
        return;
      await run(async () => {
        await api.requestPasswordReset(value);
        setMode('sent');
      }, t('loginDialog.couldNotSendTheEmail'));
    } else if (mode === 'reset' && resetToken) {
      const issues: Errors = { password: passwordIssue(password) };
      if (!issues.password && confirm !== password)
        issues.confirm = t('loginDialog.thePasswordsDoNotMatch');
      if (!validate(issues)) return;
      await run(async () => {
        await api.confirmPasswordReset(resetToken, password);
        setPassword('');
        setConfirm('');
        setMode('reset-done');
        // 重置让所有设备退出登录，包括这个浏览器。重新读取会话，界面随之回到未登录。
        await queries.invalidateQueries({ queryKey: ['session'] });
      }, t('loginDialog.passwordResetFailed'));
    } else {
      go('login');
    }
  }

  const reveal = (
    <IconButton
      size="normal"
      label={revealed ? t('loginDialog.hidePassword') : t('loginDialog.showPassword')}
      aria-pressed={revealed}
      disabled={busy}
      onClick={() => setRevealed(!revealed)}
    >
      {revealed ? <EyeOpenIcon /> : <EyeClosedIcon />}
    </IconButton>
  );
  const passwordFields = (
    <>
      <TextField
        id={id + '-password'}
        inputRef={mode === 'reset' ? firstField : passwordRef}
        label={mode === 'reset' ? t('accountDialog.newPassword') : t('loginDialog.password')}
        name="password"
        type={revealed ? 'text' : 'password'}
        autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
        value={password}
        onChange={edit('password', setPassword)}
        maxLength={128}
        disabled={busy}
        error={errors.password}
        trailing={reveal}
        detail={
          mode === 'login' ? (
            <Button
              variant="ghost"
              size="small"
              className="text-button"
              disabled={busy}
              onClick={() => {
                setEmail('');
                go('forgot');
              }}
            >
              {t('loginDialog.forgotPassword')}
            </Button>
          ) : (
            t('accountDialog.characters')
          )
        }
      />
      {mode !== 'login' && (
        <TextField
          id={id + '-confirm'}
          inputRef={confirmRef}
          label={
            mode === 'reset'
              ? t('accountDialog.confirmNewPassword')
              : t('loginDialog.confirmPassword')
          }
          name="confirm-password"
          type={revealed ? 'text' : 'password'}
          autoComplete="new-password"
          value={confirm}
          onChange={edit('confirm', setConfirm)}
          maxLength={128}
          disabled={busy}
          error={errors.confirm}
        />
      )}
      {mode === 'register' && (
        <TextField
          id={id + '-recovery'}
          inputRef={emailRef}
          label={t('accountDialog.email')}
          detail={t('loginDialog.optionalForPasswordRecoveryConfirmationIs')}
          name="email"
          type="email"
          autoComplete="email"
          value={email}
          onChange={edit('email', setEmail)}
          maxLength={254}
          disabled={busy}
          error={errors.email}
          required={false}
        />
      )}
    </>
  );

  const back = (label: string, target: Mode) => (
    <Button variant="ghost" className="text-button" disabled={busy} onClick={() => go(target)}>
      {target === 'login' && mode !== 'register' && <ArrowLeftIcon />}
      {label}
    </Button>
  );
  const primary = (label: string, icon: ReactNode = <ArrowRightIcon />) => (
    <Button type="submit" variant="primary" className="dialog-submit" disabled={busy}>
      {busy ? t('accountDialog.submitting') : label}
      {!busy && icon}
    </Button>
  );

  let body: ReactNode;
  let footer: ReactNode;
  if (mode === 'login' || mode === 'register') {
    body = (
      <>
        <TextField
          id={id + '-account'}
          inputRef={firstField}
          label={t('loginDialog.username')}
          detail={mode === 'register' ? t('loginDialog.characters') : undefined}
          name="username"
          autoComplete="username"
          autoCapitalize="none"
          spellCheck={false}
          value={account}
          onChange={edit('account', setAccount)}
          minLength={2}
          maxLength={32}
          disabled={busy}
          error={errors.account}
        />
        {passwordFields}
      </>
    );
    footer =
      mode === 'login' ? (
        <>
          {back(t('loginDialog.createAccount'), 'register')}
          {primary(t('app.signIn'))}
        </>
      ) : (
        <>
          {back(t('loginDialog.backToSignIn'), 'login')}
          {primary(t('loginDialog.register'))}
        </>
      );
  } else if (mode === 'forgot') {
    body = (
      <>
        <p className="form-hint login-lead">{t('loginDialog.enterTheEmailAddressLinkedTo')}</p>
        <TextField
          id={id + '-email'}
          inputRef={firstField}
          label={t('loginDialog.linkedEmail')}
          name="email"
          type="email"
          autoComplete="email"
          value={email}
          onChange={edit('email', setEmail)}
          maxLength={254}
          disabled={busy}
          error={errors.email}
        />
      </>
    );
    footer = (
      <>
        {back(t('loginDialog.backToSignIn'), 'login')}
        {primary(t('loginDialog.sendLink'))}
      </>
    );
  } else if (mode === 'sent' || mode === 'reset-done') {
    body = (
      <div className="dialog-notice" role="status">
        <span className="dialog-notice-icon" aria-hidden="true">
          {mode === 'sent' ? <EnvelopeClosedIcon /> : <CheckIcon />}
        </span>
        {mode === 'sent' ? (
          <div>
            <p>
              {t('loginDialog.if')}
              <strong>{email.trim()}</strong>
              {t('loginDialog.isLinkedToAnAccountA')}
            </p>
            <p className="form-hint">{t('loginDialog.checkYourSpamFolderIfYou')}</p>
          </div>
        ) : (
          <div>
            <p>{t('loginDialog.yourNewPasswordIsActiveOther')}</p>
            <p className="form-hint">{t('loginDialog.signInAgainWithYourNew')}</p>
          </div>
        )}
      </div>
    );
    footer = (
      <>
        {mode === 'sent' && back(t('loginDialog.useADifferentEmail'), 'forgot')}
        {primary(t('loginDialog.signIn'))}
      </>
    );
  } else {
    body = passwordFields;
    footer = (
      <>
        {back(t('loginDialog.requestANewLink'), 'forgot')}
        {primary(t('loginDialog.saveNewPassword'), <CheckIcon />)}
      </>
    );
  }

  return (
    <Dialog.Root
      open={open}
      onOpenChange={(value) => {
        if (busy) return;
        if (!value) {
          setRevealed(false);
          setPassword('');
          setConfirm('');
        }
        onOpenChange(value);
      }}
    >
      <DialogContent
        size="compact"
        className="login-dialog"
        onOpenAutoFocus={(event) => {
          event.preventDefault();
          firstField.current?.focus();
        }}
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          restoreFocus();
        }}
      >
        <header className="login-heading">
          <Logo />
          <Dialog.Title>{titles[mode]}</Dialog.Title>
          <DialogClose label={t('common.close')} disabled={busy} />
        </header>
        {reason && (mode === 'login' || mode === 'register') && (
          <p className="form-hint login-reason">{reason}</p>
        )}
        <form
          noValidate
          onSubmit={(event) => {
            event.preventDefault();
            void submit();
          }}
        >
          {body}
          {errors.form && (
            <p className="form-error" role="alert">
              {errors.form}
            </p>
          )}
          <div className="dialog-actions">{footer}</div>
        </form>
      </DialogContent>
    </Dialog.Root>
  );
}
