/** 确认新增或重新连接工作机，等待它取得密钥。 */
import { useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { useNavigate, useSearchParams } from 'react-router';
import { queryOptions, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowRightIcon, CheckIcon, DesktopIcon } from '@radix-ui/react-icons';
import { ApiError } from '@comfyshop/api-client';
import { Button, Dialog, DialogClose, DialogContent, Field, Input, Select } from '@comfyshop/ui';
import { useMachines, useWorkspace } from '../../app/use-workspace';
import { relativeTime } from '../../data/relative-time';

function linkUnavailable(error: Error | null) {
  return error instanceof ApiError && (error.status === 404 || error.status === 409);
}

export default function MachineLinkDialog() {
  const {
    api,
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
    queryKey: ['machine-link', userId, code],
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

  const machineName = name ?? (application?.name || '工作机');
  const newName = machineName.trim();
  const existing = machines.data?.items.filter(({ revoked }) => !revoked) ?? [];
  const selected = existing.find(({ id }) => id === target);
  const chooseTarget = existing.length > 0 || (!!target && target !== 'new');
  const creating = target === 'new' || !chooseTarget;
  const canReconnect = selected && !selected.online && !selected.busy;
  const approval = canReconnect
    ? { body: { machineId: selected.id }, name: selected.name }
    : creating && newName
      ? { body: { name: newName }, name: newName }
      : undefined;
  const canApprove = !!application && machines.isSuccess && !!approval;
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
            <p>
              已接入 <strong>{application.name}</strong>。
            </p>
          ) : (
            <>
              <p>已确认，等待工作机接入。</p>
              <p className="form-hint">请保持工作机启动窗口运行。</p>
            </>
          )}
        </div>
      </div>
    );
    footer = (
      <>
        <span />
        <Button type="submit" variant="primary" size="small" className="dialog-submit">
          {linked ? '完成' : '返回工作机列表'}
          {linked && <CheckIcon />}
        </Button>
      </>
    );
    submit = close;
  } else if (!code || (!application && link.isError)) {
    body = (
      <>
        <p className="form-hint login-lead">输入工作机窗口里显示的 8 位接入代码。</p>
        <Field label="接入代码" htmlFor="machine-link-code">
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
      <>
        <span />
        <Button type="submit" variant="primary" size="small" className="dialog-submit">
          继续
          <ArrowRightIcon />
        </Button>
      </>
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
              工作机 <strong>{application.name || '未命名'}</strong> 请求接入你的账号。
            </p>
            <p className="form-hint">
              确认后它会接收并执行你提交的任务。只确认你自己启动的工作机。
            </p>
          </div>
        </div>
        <dl className="machine-link-facts">
          <div>
            <dt>申请时间</dt>
            <dd title={new Date(application.requestedAt).toLocaleString('zh-CN')}>
              {relativeTime(application.requestedAt)}
            </dd>
          </div>
          <div>
            <dt>来源地址</dt>
            <dd>{application.source || '未知'}</dd>
          </div>
        </dl>
        {/* 来源未知或无从比较时不提示，只在确知不同时提醒。 */}
        {application.sameNetwork === false && (
          <p className="machine-link-warning" role="note">
            工作机与浏览器的来源地址不同，请核对。
          </p>
        )}
        {machines.isPending && (
          <p className="form-hint" role="status">
            正在读取工作机列表…
          </p>
        )}
        {machines.isError && (
          <div className="inline-status" role="alert">
            {machines.error.message}
            <Button size="small" onClick={() => void machines.refetch()}>
              重试
            </Button>
          </div>
        )}
        {machines.isSuccess && chooseTarget && (
          <Field label="接入方式" htmlFor="machine-link-target">
            <Select
              label="接入方式"
              id="machine-link-target"
              placeholder="选择接入方式"
              disabled={busy}
              value={creating ? 'new' : (selected?.id ?? '')}
              onValueChange={(value) => {
                setTarget(value);
                setError('');
              }}
              options={[
                ...existing.map((machine) => ({
                  value: machine.id,
                  label: `重新连接 ${machine.name} · ${machine.online ? '在线' : machine.busy ? '任务未结束' : machine.keyPrefix}${machine.id === machines.data.defaultMachineId ? ' · 默认' : ''}`,
                  disabled: machine.online || machine.busy,
                })),
                { value: 'new', label: '新增工作机' },
              ]}
            />
            {!creating && (
              <span className="form-hint">
                {canReconnect
                  ? '将换发密钥，排队任务继续等待这台工作机。'
                  : '重装时请选择原工作机。原工作机离线且空闲后可选。'}
              </span>
            )}
          </Field>
        )}
        {machines.isSuccess && creating && (
          <Field label="工作机名称" htmlFor="machine-link-name">
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
        正在读取接入申请…
      </p>
    );
    footer = (
      <>
        <Button
          variant="ghost"
          size="small"
          className="text-button"
          disabled={busy}
          onClick={close}
        >
          不接入
        </Button>
        <Button
          type="submit"
          variant="primary"
          size="small"
          className="dialog-submit"
          disabled={busy || !canApprove}
        >
          {busy ? '确认中' : canReconnect ? '重新连接' : '确认接入'}
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
          setError(error instanceof Error ? error.message : '接入失败');
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
        compact
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
          <Dialog.Title>接入工作机</Dialog.Title>
          <DialogClose disabled={busy} />
        </header>
        <form
          noValidate
          onSubmit={(event) => {
            event.preventDefault();
            submit();
          }}
        >
          {body}
          <div className="dialog-actions">{footer}</div>
        </form>
      </DialogContent>
    </Dialog.Root>
  );
}
