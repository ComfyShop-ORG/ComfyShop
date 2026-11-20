/**
 * 账号设置弹框：绑定或更换邮箱、修改密码和注销账号。敏感修改都需要再次输入当前密码，
 * 新邮箱在确认邮件里点击链接后才生效。
 */
import { useId, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import type { FormEvent, ReactNode } from 'react';
import { CheckIcon, EnvelopeClosedIcon, ExclamationTriangleIcon } from '@radix-ui/react-icons';
import {
  Button,
  Checkbox,
  Dialog,
  DialogClose,
  DialogContent,
  Field,
  Input,
  Tabs,
} from '@comfyshop/ui';
import { useWorkspace } from '../../app/use-workspace';
import { ActiveMark } from '../../motion';

type Tab = 'email' | 'password' | 'delete';
const tabs: { id: Tab; label: string }[] = [
  // 邮箱一组的名称按绑定状态显示要做的事：未绑定为「绑定邮箱」，已绑定为「更换邮箱」。
  { id: 'email', label: '' },
  { id: 'password', label: '修改密码' },
  { id: 'delete', label: '注销账号' },
];

const passwordValid = (value: string) => {
  const length = [...value].length;
  return length >= 8 && length <= 128;
};

/** 一组设置：提交时显示进行中状态，失败显示原因，成功显示 `done`。 */
function SettingsForm({
  submit,
  action,
  done,
  danger,
  disabled,
  children,
}: {
  submit: () => Promise<string | void>;
  action: string;
  done?: string;
  danger?: boolean;
  disabled?: boolean;
  children: ReactNode;
}) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ error: boolean; text: string }>();
  async function run(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setMessage(undefined);
    try {
      const issue = await submit();
      if (issue) setMessage({ error: true, text: issue });
      else if (done) setMessage({ error: false, text: done });
    } catch (error) {
      setMessage({ error: true, text: error instanceof Error ? error.message : '操作失败' });
    } finally {
      setBusy(false);
    }
  }
  return (
    <form className="account-form" noValidate onSubmit={(event) => void run(event)}>
      {children}
      <div className="account-form-footer">
        {message && (
          <p
            className={message.error ? 'form-error' : 'form-hint account-saved'}
            role={message.error ? 'alert' : 'status'}
          >
            {!message.error && <CheckIcon aria-hidden="true" />}
            {message.text}
          </p>
        )}
        <Button
          type="submit"
          size="small"
          variant={danger ? 'danger' : 'primary'}
          disabled={busy || disabled}
        >
          {busy ? '提交中' : action}
        </Button>
      </div>
    </form>
  );
}

function PasswordInput({
  id,
  label,
  value,
  onChange,
  autoComplete = 'current-password',
  detail,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  autoComplete?: string;
  detail?: string;
}) {
  return (
    <Field label={label} htmlFor={id} detail={detail}>
      <Input
        id={id}
        type="password"
        autoComplete={autoComplete}
        maxLength={128}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        required
      />
    </Field>
  );
}

export function AccountDialog({
  open,
  onOpenChange,
  onDeleted,
  restoreFocus,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** 注销成功后调用，由上层回到首页。 */
  onDeleted: () => void;
  /** 关闭后把焦点交回打开它的账号按钮。菜单项在弹框打开时已经卸载。 */
  restoreFocus: () => void;
}) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <DialogContent
        compact
        className="account-dialog"
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          restoreFocus();
        }}
      >
        {/* 内容随弹框关闭而卸载，每次打开都从邮箱一组和已保存的值开始。 */}
        <AccountSettings onDeleted={onDeleted} />
      </DialogContent>
    </Dialog.Root>
  );
}

function AccountSettings({ onDeleted }: { onDeleted: () => void }) {
  const id = useId();
  const { api, state, workspace } = useWorkspace();
  const queries = useQueryClient();
  const [tab, setTab] = useState<Tab>('email');
  const [email, setEmail] = useState('');
  const [unbinding, setUnbinding] = useState(false);
  const [emailPassword, setEmailPassword] = useState('');
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');
  const [understood, setUnderstood] = useState(false);
  const [closePassword, setClosePassword] = useState('');
  return (
    <>
      <header className="account-heading">
        <span className="account-avatar" aria-hidden="true">
          {state.user?.slice(0, 1).toUpperCase()}
        </span>
        <div className="account-identity">
          <Dialog.Title>{state.user}</Dialog.Title>
          <Dialog.Description
            className={state.email ? 'form-hint' : 'form-hint account-unbound'}
            title={state.email ?? undefined}
          >
            {state.email ?? '未绑定邮箱'}
          </Dialog.Description>
        </div>
        <DialogClose />
      </header>
      <Tabs.Root value={tab} onValueChange={(value) => setTab(value as Tab)}>
        <Tabs.List className="account-tabs" aria-label="账号设置">
          {tabs.map((item) => (
            <Tabs.Trigger key={item.id} value={item.id} asChild>
              <Button variant="ghost" size="small">
                {item.id === tab && <ActiveMark group="account-tabs" />}
                {item.id === 'email' ? (state.email ? '更换邮箱' : '绑定邮箱') : item.label}
              </Button>
            </Tabs.Trigger>
          ))}
        </Tabs.List>
        <Tabs.Content value="email">
          <SettingsForm
            action={unbinding ? '解除绑定' : '发送确认邮件'}
            danger={unbinding}
            done={unbinding ? '已解除绑定' : '确认邮件已发送，点击邮件里的链接后生效'}
            submit={async () => {
              const value = email.trim();
              if (!unbinding && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(value))
                return '请输入有效的邮箱。';
              if (!unbinding && value.toLowerCase() === state.email?.toLowerCase())
                return '这已经是当前绑定的邮箱。';
              if (!emailPassword) return '请输入当前密码。';
              await workspace.updateEmail(unbinding ? null : value, emailPassword);
              setEmail('');
              setEmailPassword('');
              setUnbinding(false);
            }}
          >
            {state.email ? (
              <div className="dialog-notice account-email-status">
                <span className="dialog-notice-icon" aria-hidden="true">
                  <EnvelopeClosedIcon />
                </span>
                <div>
                  <p className="form-hint">当前绑定</p>
                  <p>
                    <strong>{state.email}</strong>
                  </p>
                </div>
                {!unbinding && (
                  <Button
                    variant="ghost"
                    size="small"
                    className="text-button"
                    onClick={() => setUnbinding(true)}
                  >
                    解除绑定
                  </Button>
                )}
              </div>
            ) : (
              <div className="dialog-notice account-email-status" data-tone="warning">
                <span className="dialog-notice-icon" aria-hidden="true">
                  <ExclamationTriangleIcon />
                </span>
                <div>
                  <p>还没有绑定邮箱</p>
                  <p className="form-hint">
                    绑定后，忘记密码时可以通过邮件重置。填写后需在确认邮件里点击链接。
                  </p>
                </div>
              </div>
            )}
            {state.pendingEmail && !unbinding && (
              <p className="form-hint" role="status">
                等待确认：<strong>{state.pendingEmail}</strong>
                。点击确认邮件里的链接后生效，没有收到可以重新填写再发一封。
              </p>
            )}
            {unbinding ? (
              <p className="form-hint account-unbind-note">
                解除后，忘记密码时将无法找回账号。
                <Button
                  variant="ghost"
                  size="small"
                  className="text-button"
                  onClick={() => setUnbinding(false)}
                >
                  取消
                </Button>
              </p>
            ) : (
              <Field label={state.email ? '新邮箱' : '邮箱'} htmlFor={id + '-email'}>
                <Input
                  id={id + '-email'}
                  type="email"
                  autoComplete="email"
                  placeholder="name@example.com"
                  maxLength={254}
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  required
                />
              </Field>
            )}
            <PasswordInput
              id={id + '-email-password'}
              label="当前密码"
              value={emailPassword}
              onChange={setEmailPassword}
            />
          </SettingsForm>
        </Tabs.Content>
        <Tabs.Content value="password">
          <SettingsForm
            action="修改密码"
            done="密码已修改，其他设备已退出登录"
            submit={async () => {
              if (!current) return '请输入当前密码。';
              if (!passwordValid(next)) return '新密码需为 8–128 位。';
              if (next !== confirm) return '两次输入的新密码不一致。';
              await api.changePassword(current, next);
              setCurrent('');
              setNext('');
              setConfirm('');
              await queries.invalidateQueries({ queryKey: ['machines'] });
            }}
          >
            <p className="form-hint">
              修改后其他设备退出登录，全部工作机密钥失效，进行中的任务会结束。工作机需在「工作机」页重置密钥后重新连接。
            </p>
            <PasswordInput
              id={id + '-current'}
              label="当前密码"
              value={current}
              onChange={setCurrent}
            />
            <PasswordInput
              id={id + '-next'}
              label="新密码"
              detail="8–128 位"
              autoComplete="new-password"
              value={next}
              onChange={setNext}
            />
            <PasswordInput
              id={id + '-confirm'}
              label="确认新密码"
              autoComplete="new-password"
              value={confirm}
              onChange={setConfirm}
            />
          </SettingsForm>
        </Tabs.Content>
        <Tabs.Content value="delete">
          <SettingsForm
            action="注销账号"
            danger
            disabled={!understood}
            submit={async () => {
              if (!closePassword) return '请输入当前密码。';
              await workspace.deleteAccount(closePassword);
              onDeleted();
            }}
          >
            <ul className="account-consequences">
              <li>工作机密钥立即失效，进行中的任务会结束</li>
              <li>工作流、作品、任务和成品不再显示</li>
              <li>账号名之后可以被他人重新注册</li>
            </ul>
            <PasswordInput
              id={id + '-close-password'}
              label="当前密码"
              value={closePassword}
              onChange={setClosePassword}
            />
            <label className="account-confirm" htmlFor={id + '-understood'}>
              <Checkbox
                id={id + '-understood'}
                checked={understood}
                onCheckedChange={(value) => setUnderstood(value === true)}
              />
              我了解注销后无法恢复
            </label>
          </SettingsForm>
        </Tabs.Content>
      </Tabs.Root>
    </>
  );
}
