import { execFileSync, spawn } from 'node:child_process';

for (const script of ['build-worker.py', 'build-skill.py']) {
  execFileSync('uv', ['run', '--no-project', 'python', `tooling/${script}`], {
    stdio: 'inherit',
  });
}

const migration = spawn(
  'uv',
  ['run', '--package', 'comfyshop-api', 'alembic', '-c', 'apps/api/alembic.ini', 'upgrade', 'head'],
  { stdio: 'inherit' },
);
const result = await new Promise((resolve) => migration.on('exit', resolve));
if (result !== 0) process.exit(result ?? 1);
const children = [
  spawn(
    'uv',
    [
      'run',
      '--package',
      'comfyshop-api',
      'fastapi',
      'dev',
      'apps/api/src/comfyshop_api/main.py',
      '--host',
      '0.0.0.0',
      '--port',
      '8688',
    ],
    { stdio: 'inherit' },
  ),
  spawn('pnpm', ['--filter', '@comfyshop/web', 'dev'], { stdio: 'inherit' }),
];
let stopping = false;
function stop(code = 0) {
  if (stopping) return;
  stopping = true;
  for (const child of children) child.kill('SIGTERM');
  process.exitCode = code;
}
process.on('SIGINT', () => stop());
process.on('SIGTERM', () => stop());
for (const child of children) {
  child.on('error', (error) => {
    console.error(error.message);
    stop(1);
  });
  child.on('exit', (code) => stop(code ?? 0));
}
