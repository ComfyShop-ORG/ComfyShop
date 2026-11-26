import { execFileSync } from 'node:child_process';
import { cp, rm } from 'node:fs/promises';

await rm(new URL('../dist/', import.meta.url), { recursive: true, force: true });
await cp(new URL('../apps/web/dist/', import.meta.url), new URL('../dist/', import.meta.url), {
  recursive: true,
});
for (const script of ['build-worker.py', 'build-skill.py']) {
  execFileSync('uv', ['run', '--no-project', 'python', `tooling/${script}`], {
    cwd: new URL('../', import.meta.url),
    stdio: 'inherit',
  });
}
