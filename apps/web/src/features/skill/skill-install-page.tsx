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
      setStatus('已复制安装命令');
    } else {
      commandField.current?.focus();
      commandField.current?.select();
      setStatus('已选中命令，请手动复制');
    }
  }

  return (
    <main className="page">
      <section className="skill-install" aria-labelledby="skill-install-title">
        <h1 id="skill-install-title">安装 Skill</h1>
        <div className="skill-install-options">
          <Field label="客户端" htmlFor="skill-client">
            <Select
              id="skill-client"
              label="客户端"
              options={clients}
              value={client}
              onValueChange={(value) => {
                setClient(value);
                setStatus('');
              }}
            />
          </Field>
          <Field label="终端" htmlFor="skill-terminal">
            <Select
              id="skill-terminal"
              label="终端"
              options={terminals}
              value={terminal}
              onValueChange={(value) => {
                setTerminal(value);
                setStatus('');
              }}
            />
          </Field>
        </div>
        <Field label="安装命令" htmlFor="skill-command">
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
            需要 Python 3.9 或更新版本。在自己的终端运行命令，按提示登录 ComfyShop。
          </p>
        </Field>
        <div className="skill-install-actions">
          <Button variant="primary" onClick={() => void copyCommand()}>
            复制命令
          </Button>
          <Button asChild>
            <a href="/downloads/comfyshop-skill.zip" download>
              下载 Skill
            </a>
          </Button>
          {status && (
            <span className="form-hint" role="status">
              {status}
            </span>
          )}
        </div>
        <div>
          <p className="form-hint">在客户端开始会话后输入</p>
          <code>{invocation} 查找适合生成人像的工作流</code>
        </div>
      </section>
    </main>
  );
}
