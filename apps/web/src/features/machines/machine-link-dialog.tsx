/** 工作机首次启动时打开的确认弹框：登录账号确认后，那台工作机取得密钥并接入。 */
import { useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { useNavigate, useSearchParams } from 'react-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowRightIcon, CheckIcon, DesktopIcon } from '@radix-ui/react-icons';
import { Button, Dialog, DialogClose, DialogContent, Field, Input } from '@comfyshop/ui';
import { useWorkspace } from '../../app/use-workspace';
import { relativeTime } from '../../data/relative-time';

export default function MachineLinkDialog() {
  const { api } = useWorkspace();
  const queries = useQueryClient();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const code = params.get('code') ?? '';
  const field = useRef<HTMLInputElement>(null);
  const [typed, setTyped] = useState('');
  const [name, setName] = useState<string>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [linked, setLinked] = useState('');
  const link = useQuery({
    queryKey: ['machine-link', code],
    enabled: !!code && !linked,
    retry: false,
    queryFn: ({ signal }) => api.machineLink(code, signal),
  });
  const machineName = name ?? (link.data?.name || '工作机');
  const close = () => void navigate('/machines', { replace: true });

  let body: ReactNode;
  let footer: ReactNode;
  let submit: () => void;
  if (linked) {
    body = (
      <div className="dialog-notice" role="status">
        <span className="dialog-notice-icon" aria-hidden="true">
          <CheckIcon />
        </span>
        <div>
          <p>
            已接入 <strong>{linked}</strong>。
          </p>
          <p className="form-hint">回到工作机窗口，它会自动连接并开始接收你的任务。</p>
        </div>
      </div>
    );
    footer = (
      <>
        <span />
        <Button type="submit" variant="primary" size="small" className="dialog-submit">
          完成
          <CheckIcon />
        </Button>
      </>
    );
    submit = close;
  } else if (!code || link.isError) {
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
      if (typed.trim()) setParams({ code: typed.trim() }, { replace: true });
    };
  } else {
    body = link.data ? (
      <>
        <div className="dialog-notice">
          <span className="dialog-notice-icon" aria-hidden="true">
            <DesktopIcon />
          </span>
          <div>
            <p>
              设备 <strong>{link.data.name || '未命名设备'}</strong> 请求接入你的账号。
            </p>
            <p className="form-hint">
              确认后它会接收并执行你提交的任务。只确认你自己启动的工作机。
            </p>
          </div>
        </div>
        <dl className="machine-link-facts">
          <div>
            <dt>申请时间</dt>
            <dd title={new Date(link.data.requestedAt).toLocaleString('zh-CN')}>
              {relativeTime(link.data.requestedAt)}
            </dd>
          </div>
          <div>
            <dt>来源地址</dt>
            <dd>{link.data.source || '未知'}</dd>
          </div>
        </dl>
        {/* 来源未知或无从比较时不提示，只在确知不同时提醒。 */}
        {link.data.sameNetwork === false && (
          <p className="machine-link-warning" role="note">
            来源地址与当前浏览器不同。只有你自己在其他网络启动了这台工作机时才确认接入。
          </p>
        )}
        <Field label="工作机名称" htmlFor="machine-link-name">
          <Input
            ref={field}
            id="machine-link-name"
            maxLength={80}
            value={machineName}
            onChange={(event) => setName(event.target.value)}
            required
          />
        </Field>
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
          disabled={busy || !link.data || !machineName.trim()}
        >
          {busy ? '接入中' : '确认接入'}
          {!busy && <CheckIcon />}
        </Button>
      </>
    );
    submit = () => {
      void (async () => {
        setBusy(true);
        setError('');
        try {
          await api.approveMachineLink(code, machineName.trim());
          await queries.invalidateQueries({ queryKey: ['machines'] });
          setLinked(machineName.trim());
        } catch (error) {
          setError(error instanceof Error ? error.message : '接入失败');
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
          event.preventDefault();
          field.current?.focus();
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
