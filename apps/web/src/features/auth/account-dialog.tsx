/**
 * 个人资料和账号设置弹框。敏感修改需要再次输入当前密码，
 * 新邮箱在确认邮件里点击链接后才生效。
 */
import { t } from '../../app/i18n.ts';
import { useId, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import type { FormEvent, ReactNode } from 'react';
import type { Team } from '@comfyshop/api-client';
import { Link } from 'react-router';
import {
  CheckIcon,
  EnvelopeClosedIcon,
  ExclamationTriangleIcon,
  UploadIcon,
} from '@radix-ui/react-icons';
import {
  Button,
  Checkbox,
  Dialog,
  DialogClose,
  DialogContent,
  Field,
  FileInput,
  Input,
  Switch,
  Tabs,
  TabsList,
} from '@comfyshop/ui';
import { usePublicTeam, useWorkspace } from '../../app/use-workspace';
import { refreshPublishedContent } from '../../app/publication-queries';
import { publicTeamPath } from '../../app/workflow-route';
import { ProfileAvatar } from '../../components/profile-avatar';
import { useAction } from '../../components/use-action';
import { readAvatarSource } from '../../data/avatar-crop';
import { ActiveMark } from '../../motion';
import { TeamEvents } from '../workspace/team-events';
import { AvatarCropDialog } from './avatar-crop-dialog';
import { WebPushSettings } from './web-push-settings';

export type AccountSection =
  'profile' | 'settings' | 'notifications' | 'team-profile' | 'team-events';
type Tab = 'email' | 'password' | 'delete';
const tabs: { id: Tab; label: string }[] = [
  // 邮箱一组的名称按绑定状态显示要做的事：未绑定为「绑定邮箱」，已绑定为「更换邮箱」。
  { id: 'email', label: '' },
  { id: 'password', label: t('accountDialog.changePassword') },
  { id: 'delete', label: t('accountDialog.deleteAccount') },
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
  footerAction,
  children,
}: {
  submit: () => Promise<string | void>;
  action: string;
  done?: string;
  danger?: boolean;
  disabled?: boolean;
  footerAction?: ReactNode;
  children: ReactNode;
}) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ error: boolean; text: string }>();
  async function run(event: FormEvent) {
    event.preventDefault();
    if (busy || disabled) return;
    setBusy(true);
    setMessage(undefined);
    try {
      const issue = await submit();
      if (issue) setMessage({ error: true, text: issue });
      else if (done) setMessage({ error: false, text: done });
    } catch (error) {
      setMessage({
        error: true,
        text: error instanceof Error ? error.message : t('app.theActionFailed'),
      });
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
        {footerAction}
        <Button type="submit" variant={danger ? 'danger' : 'primary'} disabled={busy || disabled}>
          {busy ? t('accountDialog.submitting') : action}
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

function AvatarSettings({
  avatarUrl,
  saveAvatar,
}: {
  avatarUrl: string | null;
  saveAvatar: (avatar: File | null) => Promise<void>;
}) {
  const id = useId();
  const avatarPicker = useRef<HTMLInputElement>(null);
  const [avatarSource, setAvatarSource] = useState<Blob | null>(null);
  const [avatarStatus, setAvatarStatus] = useState('');
  const avatarAction = useAction(t('accountDialog.couldNotUpdateAvatar'));

  return (
    <>
      <Field
        label={t('accountDialog.avatar')}
        htmlFor={id}
        detail={t('accountDialog.jpgPngOrWebpUpTo')}
      >
        <div className="account-avatar-actions">
          <FileInput
            variant="inline"
            ref={avatarPicker}
            id={id}
            accept="image/jpeg,image/png,image/webp"
            disabled={avatarAction.busy}
            onChange={(event) => {
              const file = event.currentTarget.files?.[0];
              event.currentTarget.value = '';
              if (file)
                void avatarAction.run(async () => {
                  setAvatarStatus('');
                  setAvatarSource(await readAvatarSource(file));
                });
            }}
          >
            <UploadIcon />
            {avatarAction.busy
              ? t('accountDialog.processing')
              : avatarUrl
                ? t('accountDialog.changeAvatar')
                : t('accountDialog.selectImage')}
          </FileInput>
          {avatarUrl && (
            <Button
              variant="ghost"
              disabled={avatarAction.busy}
              onClick={() =>
                void avatarAction.run(async () => {
                  setAvatarStatus('');
                  await saveAvatar(null);
                  setAvatarStatus(t('accountDialog.avatarRemoved'));
                })
              }
            >
              {t('accountDialog.removeAvatar')}
            </Button>
          )}
        </div>
        {avatarAction.error ? (
          <p className="form-error" role="alert">
            {avatarAction.error}
          </p>
        ) : avatarStatus ? (
          <p className="form-hint account-saved" role="status">
            {avatarStatus}
          </p>
        ) : null}
      </Field>
      {avatarSource && (
        <AvatarCropDialog
          source={avatarSource}
          save={async (avatar) => {
            await saveAvatar(avatar);
            setAvatarStatus(t('accountDialog.avatarUpdated'));
          }}
          onClose={() => setAvatarSource(null)}
          restoreFocus={() => avatarPicker.current?.focus({ preventScroll: true })}
        />
      )}
    </>
  );
}

function ProfileSettings() {
  const id = useId();
  const { state, workspace } = useWorkspace();
  const [draft, setDraft] = useState<string>();
  const nickname = draft ?? state.nickname ?? '';
  const normalized = nickname.trim().normalize('NFC');

  return (
    <div className="account-profile">
      <AvatarSettings
        avatarUrl={state.avatarUrl}
        saveAvatar={async (avatar) => {
          await workspace.updateProfile({ avatar });
        }}
      />
      <SettingsForm
        action={t('accountDialog.saveDisplayName')}
        done={t('accountDialog.displayNameSaved')}
        disabled={normalized === (state.nickname ?? '')}
        submit={async () => {
          if ([...normalized].length > 32) return t('accountDialog.useADisplayNameOfUp');
          await workspace.updateProfile({ nickname: normalized || null });
          setDraft((current) => (current === nickname ? undefined : current));
        }}
      >
        <Field
          label={t('accountDialog.displayName')}
          htmlFor={id + '-nickname'}
          detail={t('accountDialog.upToCharactersLeaveBlankTo')}
        >
          <Input
            id={id + '-nickname'}
            value={nickname}
            autoComplete="nickname"
            maxLength={64}
            placeholder={state.user ?? undefined}
            onChange={(event) => setDraft(event.target.value)}
          />
        </Field>
      </SettingsForm>
    </div>
  );
}

function TeamProfileSettings({ team, onClose }: { team: Team; onClose: () => void }) {
  const id = useId();
  const { state, identityApi } = useWorkspace();
  const queries = useQueryClient();
  const [draft, setDraft] = useState<string>();
  const [draftVisibility, setDraftVisibility] = useState<boolean>();
  const name = draft ?? team.name;
  const normalized = name.trim();
  const isPublic = draftVisibility ?? team.profilePublic;
  const publicProfile = usePublicTeam(team.profilePublic ? team.id : undefined);
  const publicPageLink = publicProfile.data && !publicProfile.error && (
    <Button asChild>
      <Link to={publicTeamPath(team.id)} onClick={onClose}>
        {t('teams.viewPublicProfile')}
      </Link>
    </Button>
  );

  async function refreshTeam() {
    await Promise.all([
      queries.invalidateQueries({
        queryKey: ['workspace-access', state.userId, { kind: 'team', id: team.id }],
      }),
      queries.invalidateQueries({ queryKey: ['teams', state.userId], refetchType: 'all' }),
      refreshPublishedContent(queries),
    ]);
  }

  return (
    <>
      <AccountIdentity name={team.name} avatarUrl={team.avatarUrl} title={t('teams.profile')}>
        <Dialog.Description className="form-hint" title={team.name}>
          {team.name}
        </Dialog.Description>
      </AccountIdentity>
      <div className="account-profile">
        <AvatarSettings
          avatarUrl={team.avatarUrl}
          saveAvatar={async (avatar) => {
            await identityApi.updateTeamAvatar(team.id, avatar);
            await refreshTeam();
          }}
        />
        <SettingsForm
          action={t('teams.saveName')}
          done={t('teams.nameSaved')}
          disabled={!normalized || normalized === team.name}
          submit={async () => {
            await identityApi.renameTeam(team.id, normalized);
            await refreshTeam();
            setDraft((current) => (current === name ? undefined : current));
          }}
        >
          <Field label={t('teams.name')} htmlFor={id}>
            <Input
              id={id}
              value={name}
              maxLength={80}
              autoComplete="off"
              onChange={(event) => setDraft(event.target.value)}
            />
          </Field>
        </SettingsForm>
        <SettingsForm
          action={t('teams.savePublicProfile')}
          done={t('teams.publicProfileSaved')}
          disabled={isPublic === team.profilePublic}
          footerAction={publicPageLink}
          submit={async () => {
            await identityApi.setTeamProfileVisibility(team.id, isPublic);
            await refreshTeam();
            setDraftVisibility((current) => (current === isPublic ? undefined : current));
          }}
        >
          <Field htmlFor={id + '-visibility'} label={t('teams.publicProfile')}>
            <div className="team-profile-visibility">
              <p className="form-hint" id={id + '-visibility-help'}>
                {t('teams.publicProfileHelp')}
              </p>
              <Switch
                id={id + '-visibility'}
                aria-describedby={id + '-visibility-help'}
                checked={isPublic}
                onCheckedChange={setDraftVisibility}
              />
            </div>
          </Field>
        </SettingsForm>
      </div>
    </>
  );
}

export function AccountDialog({
  section,
  team,
  open,
  onOpenChange,
  onDeleted,
  restoreFocus,
}: {
  section: AccountSection;
  team?: Team;
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
        size="form"
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          restoreFocus();
        }}
      >
        {section === 'profile' ? (
          <>
            <AccountHeading profile />
            <ProfileSettings />
          </>
        ) : section === 'settings' ? (
          <AccountSettings onDeleted={onDeleted} />
        ) : section === 'notifications' ? (
          <>
            <AccountHeading title={t('webPush.settings')} />
            <WebPushSettings />
          </>
        ) : team && section === 'team-profile' ? (
          <TeamProfileSettings key={team.id} team={team} onClose={() => onOpenChange(false)} />
        ) : (
          team && <TeamEvents key={team.id} team={team} />
        )}
      </DialogContent>
    </Dialog.Root>
  );
}

function AccountHeading({ profile = false, title }: { profile?: boolean; title?: string }) {
  const { state } = useWorkspace();
  const displayName = state.nickname ?? state.user ?? '';
  return (
    <AccountIdentity
      name={displayName}
      avatarUrl={state.avatarUrl}
      title={title ?? (profile ? t('app.profile') : displayName)}
    >
      {!profile && state.nickname && state.nickname !== state.user && (
        <p className="form-hint" title={state.user ?? undefined}>
          {t('accountDialog.account', state.user)}
        </p>
      )}
      <Dialog.Description
        className={profile || state.email ? 'form-hint' : 'form-hint account-unbound'}
        title={(profile ? state.user : state.email) ?? undefined}
      >
        {profile
          ? t('accountDialog.account', state.user ?? '')
          : (state.email ?? t('accountDialog.noEmailLinked'))}
      </Dialog.Description>
    </AccountIdentity>
  );
}

function AccountIdentity({
  name,
  avatarUrl,
  title,
  children,
}: {
  name: string;
  avatarUrl: string | null;
  title: string;
  children: ReactNode;
}) {
  return (
    <header className="account-heading">
      <ProfileAvatar name={name} src={avatarUrl} className="account-avatar" />
      <div className="account-identity">
        <Dialog.Title title={title}>{title}</Dialog.Title>
        {children}
      </div>
      <DialogClose label={t('common.close')} />
    </header>
  );
}

function AccountSettings({ onDeleted }: { onDeleted: () => void }) {
  const id = useId();
  const { identityApi: api, state, workspace } = useWorkspace();
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
      <AccountHeading />
      <Tabs.Root value={tab} onValueChange={(value) => setTab(value as Tab)}>
        <TabsList className="account-tabs" aria-label={t('app.accountSettings')}>
          {tabs.map((item) => (
            <Tabs.Trigger key={item.id} value={item.id} asChild>
              <Button variant="ghost">
                {item.id === tab && <ActiveMark group="account-tabs" />}
                {item.id === 'email'
                  ? state.email
                    ? t('accountDialog.changeEmail')
                    : t('accountDialog.linkEmail')
                  : item.label}
              </Button>
            </Tabs.Trigger>
          ))}
        </TabsList>
        <Tabs.Content value="email">
          <SettingsForm
            action={
              unbinding ? t('accountDialog.unlinkEmail') : t('accountDialog.sendConfirmationEmail')
            }
            danger={unbinding}
            done={
              unbinding
                ? t('accountDialog.emailUnlinked')
                : t('accountDialog.confirmationSentOpenTheLinkIn')
            }
            submit={async () => {
              const value = email.trim();
              if (!unbinding && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(value))
                return t('accountDialog.enterAValidEmailAddress');
              if (!unbinding && value.toLowerCase() === state.email?.toLowerCase())
                return t('accountDialog.thisEmailIsAlreadyLinked');
              if (!emailPassword) return t('accountDialog.enterYourCurrentPassword');
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
                  <p className="form-hint">{t('accountDialog.linkedEmail')}</p>
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
                    {t('accountDialog.unlinkEmail')}
                  </Button>
                )}
              </div>
            ) : (
              <div className="dialog-notice account-email-status" data-tone="warning">
                <span className="dialog-notice-icon" aria-hidden="true">
                  <ExclamationTriangleIcon />
                </span>
                <div>
                  <p>{t('accountDialog.noEmailAddressIsLinked')}</p>
                  <p className="form-hint">{t('accountDialog.linkAnEmailAddressToReset')}</p>
                </div>
              </div>
            )}
            {state.pendingEmail && !unbinding && (
              <p className="form-hint" role="status">
                {t('accountDialog.awaitingConfirmation')}
                <strong>{state.pendingEmail}</strong>
                {t('accountDialog.openTheConfirmationLinkToFinish')}
              </p>
            )}
            {unbinding ? (
              <p className="form-hint account-unbind-note">
                {t('accountDialog.unlinkingYourEmailRemovesThePassword')}
                <Button
                  variant="ghost"
                  size="small"
                  className="text-button"
                  onClick={() => setUnbinding(false)}
                >
                  {t('deleteButton.cancel')}
                </Button>
              </p>
            ) : (
              <Field
                label={state.email ? t('accountDialog.newEmail') : t('accountDialog.email')}
                htmlFor={id + '-email'}
              >
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
              label={t('accountDialog.currentPassword')}
              value={emailPassword}
              onChange={setEmailPassword}
            />
          </SettingsForm>
        </Tabs.Content>
        <Tabs.Content value="password">
          <SettingsForm
            action={t('accountDialog.changePassword')}
            done={t('accountDialog.passwordChangedOtherDevicesHaveBeen')}
            submit={async () => {
              if (!current) return t('accountDialog.enterYourCurrentPassword');
              if (!passwordValid(next)) return t('accountDialog.useCharactersForTheNewPassword');
              if (next !== confirm) return t('accountDialog.theNewPasswordsDoNotMatch');
              await api.changePassword(current, next);
              setCurrent('');
              setNext('');
              setConfirm('');
              await queries.invalidateQueries({ queryKey: ['machines'] });
            }}
          >
            <p className="form-hint">{t('accountDialog.changingYourPasswordSignsOutOther')}</p>
            <PasswordInput
              id={id + '-current'}
              label={t('accountDialog.currentPassword')}
              value={current}
              onChange={setCurrent}
            />
            <PasswordInput
              id={id + '-next'}
              label={t('accountDialog.newPassword')}
              detail={t('accountDialog.characters')}
              autoComplete="new-password"
              value={next}
              onChange={setNext}
            />
            <PasswordInput
              id={id + '-confirm'}
              label={t('accountDialog.confirmNewPassword')}
              autoComplete="new-password"
              value={confirm}
              onChange={setConfirm}
            />
          </SettingsForm>
        </Tabs.Content>
        <Tabs.Content value="delete">
          <SettingsForm
            action={t('accountDialog.deleteAccount')}
            danger
            disabled={!understood}
            submit={async () => {
              if (!closePassword) return t('accountDialog.enterYourCurrentPassword');
              await workspace.deleteAccount(closePassword);
              onDeleted();
            }}
          >
            <ul className="account-consequences">
              <li>{t('accountDialog.workMachineKeysAreRevokedImmediately')}</li>
              <li>{t('accountDialog.workflowsWorksTasksAndOutputsAre')}</li>
              <li>{t('accountDialog.yourUsernameBecomesAvailableToRegister')}</li>
            </ul>
            <PasswordInput
              id={id + '-close-password'}
              label={t('accountDialog.currentPassword')}
              value={closePassword}
              onChange={setClosePassword}
            />
            <label className="account-confirm" htmlFor={id + '-understood'}>
              <Checkbox
                id={id + '-understood'}
                checked={understood}
                onCheckedChange={(value) => setUnderstood(value === true)}
              />
              {t('accountDialog.iUnderstandThatThisAccountCannot')}
            </label>
          </SettingsForm>
        </Tabs.Content>
      </Tabs.Root>
    </>
  );
}
