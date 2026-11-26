/** 使用一次性密钥下载工作机配置，并展示平台收到的连接状态。 */
import { t } from '../../app/i18n.ts';
import { useEffect, useId, useRef, useState } from 'react';
import { CheckIcon, CopyIcon, DownloadIcon } from '@radix-ui/react-icons';
import { Button, Field, Input, Tabs, TabsList } from '@comfyshop/ui';
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
    throw new TypeError(t('machineSetup.invalidWorkMachineUrl'));
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
    return <p role="status">{t('machineSetup.thisKeyHasBeenRevokedClose')}</p>;
  }
  const status = statusUnavailable
    ? t('machineSetup.couldNotCheckTheConnection')
    : machine.online
      ? t('machineSetup.connectedNodes', machine.nodeCount)
      : machine.lastSeen === null
        ? t('machineSetup.waitingForFirstConnection')
        : t('machineSetup.workMachineOffline');

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
          setError(t('machineSetup.useAnHttpOrHttpsUrl'));
          setTab('connection');
        }
      }}
    >
      <Tabs.Root value={tab} onValueChange={setTab}>
        <TabsList className="filter-group" aria-label={t('machineSetup.workMachineSetup')}>
          <Tabs.Trigger value="install" asChild>
            <Button variant="ghost">
              {tab === 'install' && <ActiveMark group="machine-setup" />}
              {t('machineSetup.setupSteps')}
            </Button>
          </Tabs.Trigger>
          <Tabs.Trigger value="connection" asChild>
            <Button variant="ghost">
              {tab === 'connection' && <ActiveMark group="machine-setup" />}
              {t('machineSetup.connectionSettings')}
            </Button>
          </Tabs.Trigger>
        </TabsList>
        <Tabs.Content value="install">
          <div className="machine-setup-panel">
            <p className="form-hint">
              {t('machineSetup.startComfyuiExtractTheWorkMachine')}
              <code>worker.json</code>
              {t('machineSetup.configurationName')}
            </p>
            <dl className="machine-launchers">
              <dt className="muted">Windows x64</dt>
              <dd>
                {t('machineSetup.doubleClick')}
                <code>start.cmd</code>
              </dd>
              <dt className="muted">macOS</dt>
              <dd>
                {t('machineSetup.doubleClick')}
                <code>start.command</code>
              </dd>
              <dt className="muted">Linux</dt>
              <dd>
                {t('machineSetup.run')}
                <code>sh ./start.sh</code>
              </dd>
            </dl>
            <p className="form-hint">
              <a
                href="https://docs.comfy.org/installation/desktop/overview"
                target="_blank"
                rel="noreferrer"
              >
                {t('machineSetup.comfyuiInstallationGuide')}
              </a>
              {t('machineSetup.internetRequiredOnFirstLaunch')}
            </p>
          </div>
        </Tabs.Content>
        <Tabs.Content value="connection">
          <div className="machine-setup-panel">
            <Field
              label={t('machineSetup.platformUrl')}
              htmlFor={`${id}-platform`}
              detail={
                <span id={`${id}-platform-hint`}>{t('machineSetup.useAUrlTheWorkMachine')}</span>
              }
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
            <Field label={t('machineSetup.comfyuiUrl')} htmlFor={`${id}-comfy`}>
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
            <Field
              label="API Key"
              htmlFor={`${id}-key`}
              detail={t('machineSetup.seeReadmeMdInThePackage')}
            >
              <div className="field-with-action machine-key">
                <Input
                  ref={keyInput}
                  id={`${id}-key`}
                  type={manualCopy ? 'text' : 'password'}
                  readOnly
                  spellCheck={false}
                  value={result.apiKey}
                />
                <Button
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
                  {copied ? t('machineSetup.copied') : t('machineSetup.copyKey')}
                </Button>
              </div>
              {manualCopy && (
                <span className="form-hint" role="status">
                  {t('machineSetup.copyTheKeyBelowManually')}
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
          <Button asChild>
            <a href={workerPackage} download>
              <DownloadIcon />
              {t('machineSetup.downloadWorkMachine')}
            </a>
          </Button>
          <Button type="submit" variant="primary">
            <DownloadIcon />
            {t('machineSetup.downloadConfiguration')}
          </Button>
        </div>
      </div>
    </form>
  );
}
