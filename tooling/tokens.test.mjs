import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { copyFile, cp, mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';

test('token edits regenerate CSS, brand colors and the packaged mail palette; checks never overwrite drift', async (t) => {
  const root = await mkdtemp(join(tmpdir(), 'comfyshop-token-build-'));
  t.after(() => rm(root, { recursive: true, force: true }));
  const directory = join(root, 'packages/tokens');
  const input = join(directory, 'src/tokens.json');
  await mkdir(join(directory, 'src'), { recursive: true });
  await copyFile(
    new URL('../packages/tokens/build.mjs', import.meta.url),
    join(directory, 'build.mjs'),
  );
  await cp(new URL('../packages/tokens/src/', import.meta.url), join(directory, 'src'), {
    recursive: true,
  });
  const brand = join(directory, 'src/brand/comfyshop-logo.svg');
  const favicon = join(root, 'apps/web/public/favicon.svg');
  const palette = join(root, 'apps/api/src/comfyshop_api/design_tokens.py');
  const css = join(directory, 'dist/tokens.css');
  const run = (...args) =>
    spawnSync(process.execPath, [join(directory, 'build.mjs'), ...args], { encoding: 'utf8' });
  assert.equal(run().status, 0);
  assert.equal(run('--check').status, 0);
  const originalPalette = await readFile(palette, 'utf8');
  const originalCss = await readFile(css, 'utf8');
  const originalBrand = await readFile(brand, 'utf8');
  const originalFavicon = await readFile(favicon, 'utf8');

  const tokens = JSON.parse(await readFile(input, 'utf8'));
  tokens.color.canvas = tokens.color.canvas === '#010203' ? '#112233' : '#010203';
  tokens.color.accent = tokens.color.canvas;
  await writeFile(input, JSON.stringify(tokens));
  const stale = run('--check');
  assert.equal(stale.status, 1);
  assert.match(stale.stderr, /pnpm tokens/);
  assert.equal(await readFile(palette, 'utf8'), originalPalette);
  assert.equal(await readFile(css, 'utf8'), originalCss);
  assert.equal(await readFile(brand, 'utf8'), originalBrand);
  assert.equal(await readFile(favicon, 'utf8'), originalFavicon);

  assert.equal(run().status, 0);
  assert.equal(run('--check').status, 0);
  assert.ok((await readFile(palette, 'utf8')).includes(`"canvas": "${tokens.color.canvas}"`));
  assert.ok((await readFile(css, 'utf8')).includes(`--color-canvas: ${tokens.color.canvas};`));
  assert.ok((await readFile(brand, 'utf8')).includes(`color="${tokens.color.accent}"`));
  assert.ok((await readFile(favicon, 'utf8')).includes(await readFile(brand, 'utf8')));
});
