import { readdir, readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';

const root = new URL('../', import.meta.url);
const violations = [];
async function walk(relative) {
  for (const entry of await readdir(new URL(relative, root), { withFileTypes: true })) {
    const path = `${relative}/${entry.name}`;
    if (entry.isDirectory()) await walk(path);
    else if (/\.(css|tsx?)$/.test(path)) {
      const text = await readFile(new URL(path, root), 'utf8');
      if (path.endsWith('.css') && /#[\da-f]{3,8}\b|\brgba?\(|\bhsla?\(/i.test(text))
        violations.push(`${path}: color must come from tokens`);
      if (path.endsWith('.css') && /border-radius\s*:\s*(?!var\(--radius-none\))[1-9]/.test(text))
        violations.push(`${path}: corners must stay square`);
      if (path.startsWith('apps/web/src') && /from ['"]radix-ui['"]/.test(text))
        violations.push(`${path}: consume Radix through @comfyshop/ui`);
      if (path.startsWith('apps/web/src') && /<(?:select|input|textarea|button)\b/.test(text))
        violations.push(`${path}: use shared controls`);
    }
  }
}
for (const path of ['apps/web/src', 'packages/ui/src', 'packages/media/src']) await walk(path);
if (violations.length) throw new Error(violations.join('\n'));
console.log(`Design boundaries verified in ${fileURLToPath(root)}`);
