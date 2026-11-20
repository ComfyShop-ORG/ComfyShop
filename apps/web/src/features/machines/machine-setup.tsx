/** 使用一次性密钥下载工作机配置，并展示平台收到的连接状态。 */
import { useEffect, useId, useRef, useState } from 'react';
import { CheckIcon, CopyIcon, DownloadIcon } from '@radix-ui/react-icons';
import { Button, Field, Input, Tabs } from '@comfyshop/ui';
import type { Machine, MachineKey } from '@comfyshop/api-client';
import { copyText } from '../../data/clipboard';
import { ActiveMark } from '../../motion';
import { StatusMark } from '../../components/status-mark';
import { downloadJson } from '../../data/download';

/** 附带平台地址的工作机启动包。解压后直接启动即可在浏览器里确认接入。 */
export const workerPackage = '/api/v1/worker/package';

/** 规范化连接地址。无效地址或含有凭据、查询参数、片段时抛出 TypeError。 */
function connectionUrl(value: string) {
  const url = new URL(value);
  if (
    !['http:', 'https:'].includes(url.protocol) ||
    url.username ||
    url.password ||
    url.href.includes('?') ||
    url.href.includes('#')
  ) {
    throw new TypeError('无效的工作机连接地址');
  }
  return url.href.replace(/\/+$/, '');
}

export function MachineSetup({
  result,
  machine,
  statusUnavailable,
}: {
  result: MachineKey;
  machine: Machine;
  statusUnavailable: boolean;
}) {
  const [tab, setTab] = useState('install');
  const [platform, setPlatform] = useState(() => window.location.origin);
  const [comfy, setComfy] = useState('http://127.0.0.1:8188');
  const [error, setError] = useState('');
  const [copied, setCopied] = useState(false);
  const [manualCopy, setManualCopy] = useState(false);
  const id = useId();
  const keyInput = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (manualCopy) {
      keyInput.current?.focus();
      keyInput.current?.select();
    }
  }, [manualCopy]);

  if (machine.revoked || machine.keyPrefix !== result.machine.keyPrefix) {
    return <p role="status">此配置的密钥已失效。请关闭弹窗，从工作机菜单重置密钥并下载新配置。</p>;
  }
  const status = statusUnavailable
    ? '暂时无法查询连接状态'
    : machine.online
      ? `已连接 · ${machine.nodeCount} 个节点`
      : machine.lastSeen === null
        ? '等待首次连接'
        : '工作机已离线';

  return (
    <form
      className="machine-setup"
      onSubmit={(event) => {
        event.preventDefault();
        try {
          downloadJson(
            {
              serverUrl: connectionUrl(platform),
              comfyUrl: connectionUrl(comfy),
              apiKey: result.apiKey,
            },
            'worker.json',
          );
          setError('');
        } catch {
          setError('地址需使用 HTTP 或 HTTPS，且不能包含账号、密码、查询参数或片段。');
          setTab('connection');
        }
      }}
    >
      <Tabs.Root value={tab} onValueChange={setTab}>
        <Tabs.List className="filter-group" aria-label="工作机安装">
          <Tabs.Trigger value="install" asChild>
            <Button size="small" variant="ghost">
              {tab === 'install' && <ActiveMark group="machine-setup" />}
              安装步骤
            </Button>
          </Tabs.Trigger>
          <Tabs.Trigger value="connection" asChild>
            <Button size="small" variant="ghost">
              {tab === 'connection' && <ActiveMark group="machine-setup" />}
              连接设置
            </Button>
          </Tabs.Trigger>
        </Tabs.List>
        <Tabs.Content value="install">
          <div className="machine-setup-panel">
            <p className="form-hint">
              先启动 ComfyUI。解压工作机，用下载的配置替换启动文件旁的 <code>worker.json</code>。
            </p>
            <dl className="machine-launchers">
              <dt className="muted">Windows x64</dt>
              <dd>
                双击 <code>start.cmd</code>
              </dd>
              <dt className="muted">macOS</dt>
              <dd>
                双击 <code>start.command</code>
              </dd>
              <dt className="muted">Linux</dt>
              <dd>
                运行 <code>sh ./start.sh</code>
              </dd>
            </dl>
            <p className="form-hint">
              <a
                href="https://docs.comfy.org/installation/desktop/overview"
                target="_blank"
                rel="noreferrer"
              >
                ComfyUI 安装指南
              </a>
              {' · 首次启动需联网'}
            </p>
          </div>
        </Tabs.Content>
        <Tabs.Content value="connection">
          <div className="machine-setup-panel">
            <Field
              label="平台地址"
              htmlFor={`${id}-platform`}
              detail={<span id={`${id}-platform-hint`}>跨设备时填工作机可访问的地址</span>}
            >
              <Input
                id={`${id}-platform`}
                type="url"
                autoComplete="off"
                spellCheck={false}
                aria-describedby={`${id}-platform-hint`}
                value={platform}
                onChange={(event) => setPlatform(event.target.value)}
                required
              />
            </Field>
            <Field label="ComfyUI 地址" htmlFor={`${id}-comfy`}>
              <Input
                id={`${id}-comfy`}
                type="url"
                autoComplete="off"
                spellCheck={false}
                value={comfy}
                onChange={(event) => setComfy(event.target.value)}
                required
              />
            </Field>
            <Field label="API Key" htmlFor={`${id}-key`} detail="手动安装见包内 README.md">
              <div className="machine-key">
                <Input
                  ref={keyInput}
                  id={`${id}-key`}
                  type={manualCopy ? 'text' : 'password'}
                  readOnly
                  spellCheck={false}
                  value={result.apiKey}
                />
                <Button
                  size="small"
                  onClick={() => {
                    void copyText(result.apiKey).then((success) => {
                      setCopied(success);
                      if (!success) {
                        if (manualCopy) {
                          keyInput.current?.focus();
                          keyInput.current?.select();
                        } else {
                          setManualCopy(true);
                        }
                      }
                    });
                  }}
                >
                  {copied ? <CheckIcon /> : <CopyIcon />}
                  {copied ? '已复制' : '复制密钥'}
                </Button>
              </div>
              {manualCopy && (
                <span className="form-hint" role="status">
                  无法自动复制，请手动复制密钥。
                </span>
              )}
            </Field>
            {error && (
              <p className="form-error" role="alert">
                {error}
              </p>
            )}
          </div>
        </Tabs.Content>
      </Tabs.Root>
      <div className="machine-setup-footer">
        <p
          role="status"
          className={
            machine.online && !statusUnavailable ? 'form-hint machine-online' : 'form-hint'
          }
        >
          {machine.online && !statusUnavailable && <StatusMark tone="success" />}
          {status}
        </p>
        <div className="machine-setup-actions">
          <Button asChild size="small">
            <a href={workerPackage} download>
              <DownloadIcon />
              下载工作机
            </a>
          </Button>
          <Button type="submit" size="small" variant="primary">
            <DownloadIcon />
            下载配置
          </Button>
        </div>
      </div>
    </form>
  );
}
