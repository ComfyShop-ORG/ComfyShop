/** 确认新增或重新连接工作机，等待它取得密钥。 */
import { locale } from '../../app/language.ts';
import { t } from '../../app/i18n.ts';
import { useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { useNavigate, useSearchParams } from 'react-router';
import { queryOptions, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowRightIcon, CheckIcon, ChevronDownIcon, DesktopIcon } from '@radix-ui/react-icons';
import { ApiError } from '@comfyshop/api-client';
import { Button, Dialog, DialogClose, DialogContent, Field, Input, Select } from '@comfyshop/ui';
import { useMachines, useWorkspace } from '../../app/use-workspace';
import { workspaceKey } from '../../app/workspace-scope';
import { relativeTime } from '../../data/relative-time';

function linkUnavailable(error: Error | null) {
  return error instanceof ApiError && (error.status === 404 || error.status === 409);
}

export default function MachineLinkDialog({
  openSpaceSwitcher,
}: {
  openSpaceSwitcher: (source: HTMLElement) => void;
}) {
  const {
    api,
    canManageWorkspace,
    workspaceTeam,
    workspaceScope,
    state: { userId },
  } = useWorkspace();
  const queries = useQueryClient();
  const machines = useMachines();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const code = params.get('code') ?? '';
  const field = useRef<HTMLInputElement>(null);
  const [typed, setTyped] = useState('');
  const [name, setName] = useState<string>();
  const [target, setTarget] = useState<string>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const linkOptions = queryOptions({
    queryKey: ['machine-link', userId, code, ...workspaceKey(workspaceScope)],
    enabled: !!userId && !!code,
    staleTime: 0,
    retry: false,
    queryFn: ({ signal }) => api.machineLink(code, signal),
    refetchInterval: ({ state }) =>
      state.data?.status === 'approved' && !linkUnavailable(state.error) ? 1000 : false,
  });
  const link = useQuery(linkOptions);
  const application = linkUnavailable(link.error) ? undefined : link.data;
  const linked = application?.status === 'linked';
  const waiting = application?.status === 'approved';
  useEffect(() => {
    if (linked) void queries.invalidateQueries({ queryKey: ['machines'] });
  }, [linked, queries]);

  const machineName = name ?? (application?.name || t('app.workMachines'));
  const newName = machineName.trim();
  const existing =
    machines.data?.items.filter(
      ({ revoked, worker }) => !revoked && worker.connection === 'machine',
    ) ?? [];
  const selected = existing.find(({ id }) => id === target);
  const chooseTarget = existing.length > 0 || (!!target && target !== 'new');
  const creating = target === 'new' || !chooseTarget;
  const canReconnect = selected && !selected.online && !selected.busy;
  const approval = canReconnect
    ? { body: { machineId: selected.id }, name: selected.name }
    : creating && newName
      ? { body: { name: newName }, name: newName }
      : undefined;
  const canApprove = canManageWorkspace && !!application && machines.isSuccess && !!approval;
  const close = () => void navigate('/machines', { replace: true });

  let body: ReactNode;
  let footer: ReactNode;
  let submit: () => void;
  if (linked || waiting) {
    body = (
      <div className="dialog-notice" role="status">
        <span className="dialog-notice-icon" aria-hidden="true">
          {linked ? <CheckIcon /> : <DesktopIcon />}
        </span>
        <div>
          {linked ? (
            <p>{t('machineLinkDialog.connected', application.name)}</p>
          ) : (
            <>
              <p>{t('machineLinkDialog.confirmedWaitingForTheWorkMachine')}</p>
              <p className="form-hint">{t('machineLinkDialog.keepTheWorkMachineRunning')}</p>
            </>
          )}
        </div>
      </div>
    );
    footer = (
      <Button type="submit" variant="primary" className="dialog-submit">
        {linked ? t('emailConfirmDialog.done') : t('machineLinkDialog.backToWorkMachines')}
        {linked && <CheckIcon />}
      </Button>
    );
    submit = close;
  } else if (!code || (!application && link.isError)) {
    body = (
      <>
        <p className="form-hint login-lead">
          {t('machineLinkDialog.enterTheCharacterCodeShownBy')}
        </p>
        <Field label={t('machineLinkDialog.connectionCode')} htmlFor="machine-link-code">
          <Input
            ref={field}
            id="machine-link-code"
            className="machine-link-code"
            autoComplete="off"
            autoCapitalize="characters"
            spellCheck={false}
            placeholder="XXXX-XXXX"
            maxLength={16}
            value={typed}
            onChange={(event) => setTyped(event.target.value)}
            aria-invalid={link.isError ? true : undefined}
            required
          />
        </Field>
        {link.isError && (
          <p className="form-error" role="alert">
            {link.error.message}
          </p>
        )}
      </>
    );
    footer = (
      <Button type="submit" variant="primary" className="dialog-submit">
        {t('machineLinkDialog.continue')}
        <ArrowRightIcon />
      </Button>
    );
    submit = () => {
      const nextCode = typed.trim();
      if (!nextCode) return;
      setName(undefined);
      setTarget(undefined);
      setError('');
      if (nextCode === code) void link.refetch();
      else setParams({ code: nextCode }, { replace: true });
    };
  } else {
    body = application ? (
      <>
        <div className="dialog-notice">
          <span className="dialog-notice-icon" aria-hidden="true">
            <DesktopIcon />
          </span>
          <div>
            <p>
              {t('machineLinkDialog.workMachine')}
              <strong>{application.name || t('machineLinkDialog.unnamed')}</strong>
              {workspaceTeam
                ? t('machineLinkDialog.isRequestingAccessToTeam', workspaceTeam.name)
                : t('machineLinkDialog.isRequestingAccessToYourAccount')}
            </p>
            <p className="form-hint">
              {t(
                workspaceTeam
                  ? 'machineLinkDialog.confirmOwnMachine'
                  : 'machineLinkDialog.thisMachineWillReceiveAndRun',
              )}
            </p>
          </div>
        </div>
        <dl className="machine-facts">
          <div>
            <dt>{t('machineLinkDialog.requestedAt')}</dt>
            <dd title={new Date(application.requestedAt).toLocaleString(locale)}>
              {relativeTime(application.requestedAt)}
            </dd>
          </div>
          <div>
            <dt>{t('machineLinkDialog.sourceAddress')}</dt>
            <dd>{application.source || t('machineLinkDialog.unknown')}</dd>
          </div>
        </dl>
        {/* 来源未知或无从比较时不提示，只在确知不同时提醒。 */}
        {application.sameNetwork === false && (
          <p className="machine-link-warning" role="note">
            {t('machineLinkDialog.theWorkMachineAndBrowserAre')}
          </p>
        )}
        {machines.isPending && (
          <p className="form-hint" role="status">
            {t('machineLinkDialog.loadingWorkMachines')}
          </p>
        )}
        {machines.isError && (
          <div className="inline-status" role="alert">
            {machines.error.message}
            <Button size="small" onClick={() => void machines.refetch()}>
              {t('app.retry')}
            </Button>
          </div>
        )}
        {machines.isSuccess && chooseTarget && (
          <Field label={t('machineLinkDialog.connectionMethod')} htmlFor="machine-link-target">
            <Select
              label={t('machineLinkDialog.connectionMethod')}
              id="machine-link-target"
              placeholder={t('machineLinkDialog.chooseHowToConnect')}
              disabled={busy}
              value={creating ? 'new' : (selected?.id ?? '')}
              onValueChange={(value) => {
                setTarget(value);
                setError('');
              }}
              options={[
                ...existing.map((machine) => ({
                  value: machine.id,
                  label: t(
                    'machineLinkDialog.reconnect',
                    machine.name,
                    machine.online
                      ? t('machinesPage.online')
                      : machine.busy
                        ? t('machineLinkDialog.activeTask')
                        : machine.keyPrefix,
                    machine.id === machines.data.defaultMachineId
                      ? t('machineLinkDialog.defaultSuffix')
                      : '',
                  ),
                  disabled: machine.online || machine.busy,
                })),
                { value: 'new', label: t('machineLinkDialog.addANewWorkMachine') },
              ]}
            />
            {!creating && (
              <span className="form-hint">
                {canReconnect
                  ? t('machineLinkDialog.thisReplacesTheKeyQueuedTasks')
                  : t('machineLinkDialog.selectTheOriginalMachineAfterReinstalling')}
              </span>
            )}
          </Field>
        )}
        {machines.isSuccess && creating && (
          <Field label={t('machineLinkDialog.workMachineName')} htmlFor="machine-link-name">
            <Input
              ref={field}
              id="machine-link-name"
              maxLength={80}
              value={machineName}
              onChange={(event) => setName(event.target.value)}
              required
              disabled={busy}
            />
          </Field>
        )}
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
      </>
    ) : (
      <p className="form-hint" role="status">
        {t('machineLinkDialog.loadingConnectionRequest')}
      </p>
    );
    footer = (
      <>
        <Button variant="ghost" className="text-button" disabled={busy} onClick={close}>
          {t('machineLinkDialog.decline')}
        </Button>
        <Button
          type="submit"
          variant="primary"
          className="dialog-submit"
          disabled={busy || !canApprove}
        >
          {busy
            ? t('machineLinkDialog.confirming')
            : canReconnect
              ? t('machineLinkDialog.reconnect2')
              : t('machineLinkDialog.confirmConnection')}
          {!busy && <CheckIcon />}
        </Button>
      </>
    );
    submit = () => {
      if (busy || !canApprove || !approval) return;
      void (async () => {
        setBusy(true);
        setError('');
        try {
          await api.approveMachineLink(code, approval.body);
          await queries.cancelQueries({ queryKey: linkOptions.queryKey, exact: true });
          queries.setQueryData(linkOptions.queryKey, (current) =>
            current?.status === 'pending'
              ? { ...current, name: approval.name, status: 'approved' as const }
              : current,
          );
        } catch (error) {
          setError(
            error instanceof Error ? error.message : t('machineLinkDialog.connectionFailed'),
          );
          if (error instanceof ApiError && (error.status === 0 || error.status === 404)) {
            void link.refetch();
          }
          if (error instanceof ApiError && error.status === 409) void machines.refetch();
        } finally {
          setBusy(false);
        }
      })();
    };
  }

  return (
    <Dialog.Root
      open
      onOpenChange={(open) => {
        if (!open && !busy) close();
      }}
    >
      <DialogContent
        size="form"
        className="login-dialog"
        onOpenAutoFocus={(event) => {
          if (field.current) {
            event.preventDefault();
            field.current.focus();
          }
        }}
      >
        <header className="login-heading">
          <DesktopIcon className="machine-link-icon" aria-hidden="true" />
          <Dialog.Title>{t('machineLinkDialog.connectAWorkMachine')}</Dialog.Title>
          <DialogClose label={t('common.close')} disabled={busy} />
        </header>
        <form
          noValidate
          onSubmit={(event) => {
            event.preventDefault();
            submit();
          }}
        >
          {!waiting && !linked && (
            <dl className="machine-facts machine-link-space">
              <dt>{t('machineLinkDialog.connectionSpace')}</dt>
              <dd>
                <Button
                  size="small"
                  variant="ghost"
                  aria-haspopup="dialog"
                  disabled={busy}
                  onClick={(event) => openSpaceSwitcher(event.currentTarget)}
                >
                  <span>{workspaceTeam?.name ?? t('app.workspace')}</span>
                  <ChevronDownIcon aria-hidden="true" />
                </Button>
              </dd>
            </dl>
          )}
          {!canManageWorkspace && !waiting && !linked && (
            <p className="form-hint">{t('machineLinkDialog.noSpacePermission')}</p>
          )}
          {body}
          <div className="dialog-actions">{footer}</div>
        </form>
      </DialogContent>
    </Dialog.Root>
  );
}
