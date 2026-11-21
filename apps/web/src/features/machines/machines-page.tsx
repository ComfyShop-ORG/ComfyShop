/** 工作机列表、添加入口及密钥重置和撤销。 */
import { useEffect, useId, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import {
  CheckIcon,
  DesktopIcon,
  DotsHorizontalIcon,
  DownloadIcon,
  PlusIcon,
} from '@radix-ui/react-icons';
import {
  AlertDialog,
  AlertDialogContent,
  Button,
  Dialog,
  DialogClose,
  DialogContent,
  DropdownMenu,
  Field,
  IconButton,
  Input,
} from '@comfyshop/ui';
import type { Machine, MachineKey } from '@comfyshop/api-client';
import { useMachines, useWorkspace } from '../../app/use-workspace';
import { EmptyState } from '../../components/collection-status';
import { StatusMark } from '../../components/status-mark';
import { relativeTime } from '../../data/relative-time';
import { MachineSetup, workerPackage } from './machine-setup';
import { ListItem, ListPresence } from '../../motion';

type MachineChange = { machine: Machine; kind: 'rotate' | 'revoke' };

function updateStatus(machine: Machine) {
  const update = machine.update;
  if (!update) return null;
  if (update.status === 'pending') return '等待更新到最新版';
  if (update.status === 'updating') {
    return update.release ? `正在更新到 ${update.release.version}` : '正在更新';
  }
  if (update.status === 'failed') return update.error || '更新失败';
  return null;
}

export default function MachinesPage() {
  const { api, workspace } = useWorkspace();
  const machines = useMachines();
  const queries = useQueryClient();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState('');
  const [result, setResult] = useState<MachineKey | null>(null);
  const [confirmation, setConfirmation] = useState<MachineChange | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const descriptionId = useId();
  const addButton = useRef<HTMLButtonElement>(null);
  const nameInput = useRef<HTMLInputElement>(null);
  const title = useRef<HTMLHeadingElement>(null);
  const menuButtons = useRef(new Map<string, HTMLButtonElement>());
  const returnFocus = useRef<HTMLButtonElement | null>(null);
  useEffect(() => {
    if (result) title.current?.focus();
  }, [result]);
  async function action<Result>(run: () => Promise<Result>) {
    setBusy(true);
    setError('');
    try {
      const result = await run();
      await queries.invalidateQueries({ queryKey: ['machines'] });
      return { result };
    } catch (error) {
      setError(error instanceof Error ? error.message : '操作失败');
      return null;
    } finally {
      setBusy(false);
    }
  }
  function requestChange(machine: Machine, kind: MachineChange['kind']) {
    returnFocus.current = menuButtons.current.get(machine.id) ?? null;
    setError('');
    setConfirmation({ machine, kind });
  }
  function restoreFocus() {
    (returnFocus.current?.isConnected ? returnFocus.current : addButton.current)?.focus();
  }
  async function confirmChange(change: MachineChange) {
    const outcome = await action(async () => {
      if (change.kind === 'rotate') return api.rotateMachine(change.machine.id);
      await api.revokeMachine(change.machine.id);
      return null;
    });
    if (!outcome) return;
    setConfirmation(null);
    if (outcome.result) {
      setResult(outcome.result);
      setOpen(true);
    }
    void Promise.all(
      ['tasks', 'task-activity', 'task-progress'].map((key) =>
        queries.invalidateQueries({ queryKey: [key] }),
      ),
    );
  }
  const rotating = confirmation?.kind === 'rotate';
  const setupMachine = result && machines.data?.items.find(({ id }) => id === result.machine.id);
  const available = machines.data?.workerRelease;
  return (
    <main className="page machines-page">
      <div className="section-heading page-toolbar">
        <div>
          <h1>工作机</h1>
          {available && <span className="form-hint">最新可用版本 {available.version}</span>}
        </div>
        <DropdownMenu.Root>
          <DropdownMenu.Trigger asChild>
            <Button ref={addButton} size="small">
              <PlusIcon />
              添加工作机
            </Button>
          </DropdownMenu.Trigger>
          <DropdownMenu.Portal>
            <DropdownMenu.Content className="ui-menu" align="end" sideOffset={8}>
              <DropdownMenu.Item className="ui-menu-item" asChild>
                <a href={workerPackage} download>
                  下载工作机，启动后在浏览器确认
                </a>
              </DropdownMenu.Item>
              <DropdownMenu.Item
                className="ui-menu-item"
                onSelect={() => {
                  returnFocus.current = addButton.current;
                  setResult(null);
                  setName('');
                  setError('');
                  setOpen(true);
                }}
              >
                手动添加，下载含密钥的配置
              </DropdownMenu.Item>
            </DropdownMenu.Content>
          </DropdownMenu.Portal>
        </DropdownMenu.Root>
      </div>
      <div className="machine-list">
        <ListPresence>
          {machines.data?.items.map((machine) => (
            <ListItem className="machine-item" key={machine.id}>
              <DesktopIcon className="machine-icon" />
              <div className="machine-identity">
                <strong>{machine.name}</strong>
                <span className="muted">{machine.device || `${machine.keyPrefix}…`}</span>
                <span className="muted" title={machine.runtime?.build ?? undefined}>
                  {machine.runtime ? `版本 ${machine.runtime.version}` : '版本未知'}
                  {machine.updateAvailable && available && ` · 可更新至 ${available.version}`}
                </span>
                {updateStatus(machine) && (
                  <span
                    className={machine.update?.status === 'failed' ? 'form-error' : 'muted'}
                    role="status"
                  >
                    {updateStatus(machine)}
                  </span>
                )}
              </div>
              <span className="machine-state">
                <StatusMark
                  tone={
                    machine.revoked || !machine.online
                      ? 'idle'
                      : machine.busy
                        ? 'active'
                        : 'success'
                  }
                />
                {machine.revoked
                  ? '已撤销'
                  : machine.online
                    ? machine.busy
                      ? '忙碌'
                      : '在线'
                    : machine.lastSeen === null
                      ? '未连接'
                      : `离线 · ${relativeTime(machine.lastSeen)}在线`}
              </span>
              <span className="machine-nodes muted">
                {machine.lastSeen === null ? '—' : `${machine.nodeCount} 节点`}
              </span>
              <Button
                size="small"
                variant="ghost"
                disabled={machine.revoked || busy || machines.data.defaultMachineId === machine.id}
                onClick={() => void action(() => workspace.setDefaultMachine(machine.id))}
              >
                {machines.data.defaultMachineId === machine.id ? (
                  <>
                    <CheckIcon />
                    默认
                  </>
                ) : (
                  '设为默认'
                )}
              </Button>
              <DropdownMenu.Root>
                <DropdownMenu.Trigger asChild>
                  <IconButton
                    ref={(button) => {
                      if (button) menuButtons.current.set(machine.id, button);
                      else menuButtons.current.delete(machine.id);
                    }}
                    label={`${machine.name} 操作`}
                    disabled={busy}
                  >
                    <DotsHorizontalIcon />
                  </IconButton>
                </DropdownMenu.Trigger>
                <DropdownMenu.Portal>
                  <DropdownMenu.Content
                    className="ui-menu"
                    align="end"
                    sideOffset={8}
                    onCloseAutoFocus={(event) => {
                      if (confirmation) event.preventDefault();
                    }}
                  >
                    {machine.updateAvailable && (
                      <DropdownMenu.Item
                        className="ui-menu-item"
                        onSelect={() => void action(() => api.updateMachine(machine.id))}
                      >
                        更新到最新版
                      </DropdownMenu.Item>
                    )}
                    <DropdownMenu.Item
                      className="ui-menu-item"
                      onSelect={() => requestChange(machine, 'rotate')}
                    >
                      重置密钥
                    </DropdownMenu.Item>
                    {!machine.revoked && (
                      <DropdownMenu.Item
                        className="ui-menu-item"
                        onSelect={() => requestChange(machine, 'revoke')}
                      >
                        撤销工作机
                      </DropdownMenu.Item>
                    )}
                  </DropdownMenu.Content>
                </DropdownMenu.Portal>
              </DropdownMenu.Root>
            </ListItem>
          ))}
        </ListPresence>
      </div>
      {!machines.isPending && !machines.isError && !machines.data?.items.length && (
        <EmptyState
          label="生成在你自己的 ComfyUI 上运行。下载工作机，解压后运行启动文件，在浏览器里确认接入。"
          action={
            <Button asChild size="small" variant="primary">
              <a href={workerPackage} download>
                <DownloadIcon />
                下载工作机
              </a>
            </Button>
          }
        />
      )}
      {machines.isError && (
        <div className="inline-status" role="alert">
          {machines.error.message}
          <Button size="small" onClick={() => void machines.refetch()}>
            重试
          </Button>
        </div>
      )}
      {error && !open && !confirmation && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      <AlertDialog.Root
        open={!!confirmation}
        onOpenChange={(value) => {
          if (!value && !busy) setConfirmation(null);
        }}
      >
        <AlertDialogContent
          className="machine-confirmation"
          onCloseAutoFocus={(event) => {
            event.preventDefault();
            if (!open) restoreFocus();
          }}
        >
          <div className="compact-dialog-heading">
            <AlertDialog.Title>{rotating ? '重置密钥' : '撤销工作机'}</AlertDialog.Title>
          </div>
          <AlertDialog.Description className="form-hint">
            「{confirmation?.machine.name}」的旧密钥将立即失效，执行中的任务会标记为失败。
            {rotating
              ? '排队的任务继续等待，用新密钥重新连接后领取。'
              : '排队的任务同样标记为失败，工作机将无法领取新任务。'}
          </AlertDialog.Description>
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          <div className="compact-dialog-footer">
            <AlertDialog.Cancel asChild>
              <Button disabled={busy}>取消</Button>
            </AlertDialog.Cancel>
            <Button
              variant="primary"
              disabled={busy}
              onClick={() => {
                if (confirmation && !busy) void confirmChange(confirmation);
              }}
            >
              {busy ? '处理中' : rotating ? '确认重置' : '确认撤销'}
            </Button>
          </div>
        </AlertDialogContent>
      </AlertDialog.Root>
      <Dialog.Root
        open={open}
        onOpenChange={(value) => {
          if (!busy) {
            setOpen(value);
            if (!value) setResult(null);
          }
        }}
      >
        <DialogContent
          compact
          className={result ? 'machine-dialog machine-setup-dialog' : 'machine-dialog'}
          aria-describedby={descriptionId}
          onOpenAutoFocus={(event) => {
            event.preventDefault();
            if (result) title.current?.focus();
            else nameInput.current?.focus();
          }}
          onCloseAutoFocus={(event) => {
            event.preventDefault();
            restoreFocus();
          }}
        >
          <div className="compact-dialog-heading">
            <Dialog.Title ref={title} tabIndex={-1}>
              {result ? '安装与连接工作机' : '手动添加工作机'}
            </Dialog.Title>
            <DialogClose disabled={busy} />
          </div>
          <Dialog.Description id={descriptionId} className="form-hint">
            {result
              ? `「${result.machine.name}」的配置含 API Key，仅在此处提供。`
              : '创建后可下载工作机和配置，并查看是否连接成功。'}
          </Dialog.Description>
          {result ? (
            <MachineSetup
              result={result}
              machine={setupMachine ?? result.machine}
              statusUnavailable={machines.isError}
            />
          ) : (
            <form
              className="machine-create-form"
              onSubmit={(event) => {
                event.preventDefault();
                if (!busy && name.trim()) {
                  void action(async () => setResult(await api.createMachine(name.trim())));
                }
              }}
            >
              <Field label="名称" htmlFor="machine-name">
                <Input
                  ref={nameInput}
                  id="machine-name"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  maxLength={80}
                  required
                  autoComplete="off"
                />
              </Field>
              <div className="compact-dialog-footer">
                <Button type="submit" variant="primary" disabled={busy || !name.trim()}>
                  {busy ? '创建中' : '创建'}
                </Button>
              </div>
            </form>
          )}
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
        </DialogContent>
      </Dialog.Root>
    </main>
  );
}
