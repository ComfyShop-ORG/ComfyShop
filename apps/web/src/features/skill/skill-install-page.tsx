import { t } from '../../app/i18n.ts';
import { useRef, useState } from 'react';
import { Button, Field, Select, TextArea } from '@comfyshop/ui';
import { copyText } from '../../data/clipboard';

const clients = [
  { value: 'codex', label: 'Codex' },
  { value: 'claude-code', label: 'Claude Code' },
];
const terminals = [
  { value: 'sh', label: 'macOS / Linux' },
  { value: 'powershell', label: 'PowerShell' },
];

function installCommand(origin: string, client: string, terminal: string): string {
  const url = `${origin}/downloads/install-comfyshop-skill.py`;
  if (terminal === 'powershell') {
    const quote = (value: string) => `'${value.replaceAll("'", "''")}'`;
    return [
      '$comfyshopInstaller = New-TemporaryFile;',
      `try { Invoke-WebRequest -UseBasicParsing -ErrorAction Stop -Uri ${quote(url)} -OutFile $comfyshopInstaller.FullName;`,
      `py -3 $comfyshopInstaller.FullName --server ${quote(origin)} install ${client} }`,
      'finally { Remove-Item -LiteralPath $comfyshopInstaller.FullName }',
    ].join(' ');
  }
  const quote = (value: string) => `'${value.replaceAll("'", "'\\''")}'`;
  return [
    '( comfyshop_installer=$(mktemp)',
    'trap \'unlink "$comfyshop_installer"\' EXIT',
    `curl -fsS -o "$comfyshop_installer" ${quote(url)}`,
    `python3 "$comfyshop_installer" --server ${quote(origin)} install ${client} )`,
  ].join(' && ');
}

export function SkillInstallPage() {
  const [client, setClient] = useState('codex');
  const [terminal, setTerminal] = useState(
    /Windows/.test(navigator.userAgent) ? 'powershell' : 'sh',
  );
  const [status, setStatus] = useState('');
  const commandField = useRef<HTMLTextAreaElement>(null);
  const command = installCommand(window.location.origin, client, terminal);
  const invocation = client === 'codex' ? '$comfyshop' : '/comfyshop';

  async function copyCommand() {
    if (await copyText(command)) {
      setStatus(t('skillInstallPage.installCommandCopied'));
    } else {
      commandField.current?.focus();
      commandField.current?.select();
      setStatus(t('skillInstallPage.commandSelectedCopyItManually'));
    }
  }

  return (
    <main className="page">
      <section className="skill-install" aria-labelledby="skill-install-title">
        <h1 id="skill-install-title">{t('app.installSkill')}</h1>
        <div className="skill-install-options">
          <Field label={t('skillInstallPage.client')} htmlFor="skill-client">
            <Select
              id="skill-client"
              label={t('skillInstallPage.client')}
              options={clients}
              value={client}
              onValueChange={(value) => {
                setClient(value);
                setStatus('');
              }}
            />
          </Field>
          <Field label={t('skillInstallPage.terminal')} htmlFor="skill-terminal">
            <Select
              id="skill-terminal"
              label={t('skillInstallPage.terminal')}
              options={terminals}
              value={terminal}
              onValueChange={(value) => {
                setTerminal(value);
                setStatus('');
              }}
            />
          </Field>
        </div>
        <Field label={t('skillInstallPage.installCommand')} htmlFor="skill-command">
          <TextArea
            id="skill-command"
            className="skill-install-command"
            ref={commandField}
            value={command}
            rows={5}
            readOnly
            spellCheck={false}
            aria-describedby="skill-install-help"
          />
          <p id="skill-install-help" className="form-hint">
            {t('skillInstallPage.pythonOrLaterIsRequiredRun')}
          </p>
        </Field>
        <div className="skill-install-actions">
          <Button variant="primary" onClick={() => void copyCommand()}>
            {t('skillInstallPage.copyCommand')}
          </Button>
          <Button asChild>
            <a href="/downloads/comfyshop-skill.zip" download>
              {t('skillInstallPage.downloadSkill')}
            </a>
          </Button>
          {status && (
            <span className="form-hint" role="status">
              {status}
            </span>
          )}
        </div>
        <div>
          <p className="form-hint">{t('skillInstallPage.onceTheSessionStartsEnter')}</p>
          <code>{t('skillInstallPage.findWorkflowsForGeneratingPortraits', invocation)}</code>
        </div>
      </section>
    </main>
  );
}
