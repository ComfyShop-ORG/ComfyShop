import { readFile, mkdir, writeFile } from 'node:fs/promises';

const source = JSON.parse(await readFile(new URL('./src/tokens.json', import.meta.url), 'utf8'));
const apiDirectory = new URL('../../apps/api/src/comfyshop_api/', import.meta.url);
const paletteFile = new URL('design_tokens.py', apiDirectory);
const palette = [
  '"""由 packages/tokens/src/tokens.json 生成。运行 pnpm tokens 更新，请勿手工修改。"""',
  '',
  'COLORS = {',
  ...Object.entries(source.color).map(
    ([name, value]) => `    ${JSON.stringify(name)}: ${JSON.stringify(value)},`,
  ),
  '}',
  '',
].join('\n');

const brandDirectory = new URL('./src/brand/', import.meta.url);
const brandAssets = await Promise.all(
  ['comfyshop-logo.svg', 'comfyshop-wordmark.svg'].map(async (name) => {
    const file = new URL(name, brandDirectory);
    const current = await readFile(file, 'utf8');
    const themed = current.replace(
      /data-color-token="([a-z-]+)" (color|fill)="[^"]*"/g,
      (_, token, attribute) => {
        if (!Object.hasOwn(source.color, token)) throw new Error(`未知的品牌颜色 token：${token}`);
        return `data-color-token="${token}" ${attribute}="${source.color[token]}"`;
      },
    );
    return { file, current, themed };
  }),
);
const publicDirectory = new URL('../../apps/web/public/', import.meta.url);
const faviconFile = new URL('favicon.svg', publicDirectory);
const currentFavicon = await readFile(faviconFile, 'utf8').catch((error) => {
  if (error.code === 'ENOENT') return null;
  throw error;
});
const favicon = {
  file: faviconFile,
  current: currentFavicon,
  themed: '<!-- Generated from the ComfyShop icon and design tokens. -->\n' + brandAssets[0].themed,
};
const outdatedBrands = [...brandAssets, favicon].filter(
  ({ current, themed }) => current !== themed,
);

if (process.argv.includes('--check')) {
  const current = await readFile(paletteFile, 'utf8').catch((error) => {
    if (error.code === 'ENOENT') return null;
    throw error;
  });
  if (current !== palette) {
    console.error('邮件调色板与 tokens 不一致，请运行 pnpm tokens 并提交生成文件。');
    process.exitCode = 1;
  }
  if (outdatedBrands.length) {
    console.error('SVG 品牌颜色与 tokens 不一致，请运行 pnpm tokens。');
    process.exitCode = 1;
  }
} else {
  const declarations = Object.entries(source).flatMap(([group, values]) =>
    Object.entries(values).map(([name, value]) => `  --${group}-${name}: ${value};`),
  );
  await mkdir(new URL('./dist/', import.meta.url), { recursive: true });
  await writeFile(
    new URL('./dist/tokens.css', import.meta.url),
    `/* Generated from src/tokens.json. */\n:root {\n${declarations.join('\n')}\n}\n`,
  );
  await mkdir(apiDirectory, { recursive: true });
  await writeFile(paletteFile, palette);
  await mkdir(publicDirectory, { recursive: true });
  await Promise.all(outdatedBrands.map(({ file, themed }) => writeFile(file, themed)));
}
