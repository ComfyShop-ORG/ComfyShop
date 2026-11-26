import assert from 'node:assert/strict';
import test from 'node:test';
import ts from 'typescript';
import { inspectCss, inspectTokens } from './check-styles.mjs';

function project(text = '') {
  const fileName = '/style-check-fixture.tsx';
  const options = { noLib: true, noResolve: true, strict: true, jsx: ts.JsxEmit.Preserve };
  const host = ts.createCompilerHost(options);
  host.getSourceFile = (name) =>
    name === fileName
      ? ts.createSourceFile(name, text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
      : undefined;
  const program = ts.createProgram([fileName], options, host);
  return { sources: [program.getSourceFile(fileName)], checker: program.getTypeChecker() };
}

const stylesheet = (text) => [{ file: 'styles.css', text }];

test('CSS keeps finite template variants and Radix states but reports unused selectors', async () => {
  const issues = await inspectCss({
    ...project(`
      function Button({variant}: {variant: 'primary' | 'ghost'}) {
        return <button className={\`ui-button ui-button--\${variant}\`}/>;
      }
    `),
    css: stylesheet(`
      .ui-button { display: flex; }
      .ui-button--primary { color: inherit; }
      .ui-button--ghost[data-state='on'] { color: inherit; }
      .orphan { display: none; }
    `),
  });
  assert.equal(issues.length, 1);
  assert.match(issues[0], /styles\.css:5: 未引用选择器 \.orphan$/);
});

test('CSS checks selectors inside media queries and unused keyframes', async () => {
  const issues = await inspectCss({
    ...project('const Card = () => <div className="card"/>;'),
    css: stylesheet(`
      .card { animation: pulse 1s; }
      @media (max-width: 600px) { .mobile-orphan { display: none; } }
      @keyframes pulse { to { opacity: .5; } }
      @keyframes unused { to { opacity: .2; } }
    `),
  });
  assert.equal(issues.length, 2);
  assert.ok(issues.some((issue) => issue.includes('未引用选择器 .mobile-orphan')));
  assert.ok(issues.some((issue) => issue.includes('未引用动画 unused')));
});

test('CSS preserves tags and item attributes rendered by Radix primitives', async () => {
  const issues = await inspectCss({
    ...project(
      `const Content = () => <div className="heading menu"><Dialog.Title>Title</Dialog.Title></div>;`,
    ),
    css: stylesheet(`
      .heading h2 { color: inherit; }
      .menu[data-highlighted] { color: inherit; }
      .menu[data-disabled] { opacity: .5; }
      .unknown h2 { color: inherit; }
    `),
  });
  assert.equal(issues.length, 1);
  assert.match(issues[0], /未引用选择器 \.unknown h2$/);
});

test('tokens combine CSS dependencies with aliased TypeScript imports', () => {
  const issues = inspectTokens({
    ...project(`
      import { layout as grid } from '@comfyshop/tokens';
      const gap = grid['gap'];
      // grid.unused must not count as a reference.
    `),
    tokens: {
      color: { base: '#fff', alias: 'var(--color-base)', unused: '#111' },
      layout: { gap: 12, unused: 6 },
    },
    css: stylesheet('.card { color: var(--color-alias); }'),
  });
  assert.deepEqual(issues, [
    'tokens.json: 未引用 token --color-unused',
    'tokens.json: 未引用 token --layout-unused',
  ]);
});

test('tokens recognize namespace imports and ignore locally shadowed names', () => {
  const issues = inspectTokens({
    ...project(`
      import * as tokens from '@comfyshop/tokens';
      const gap = tokens.layout.gap;
      function read(tokens: {layout: {unused: number}}) { return tokens.layout.unused; }
    `),
    tokens: { layout: { gap: 12, unused: 6 } },
    css: [],
  });
  assert.deepEqual(issues, ['tokens.json: 未引用 token --layout-unused']);
});

test('tokens inspect nested var fallbacks without flagging known Radix variables', () => {
  const issues = inspectTokens({
    ...project(),
    tokens: { color: { base: '#fff' } },
    css: stylesheet(`.card {
      color: var(--missing, var(--color-base));
      width: var(--radix-select-trigger-width);
    }`),
  });
  assert.deepEqual(issues, ['styles.css:2: 未定义变量 --missing']);
});

test('tokens follow local CSS variables and leave unused dependency chains unused', () => {
  const issues = inspectTokens({
    ...project(),
    tokens: { color: { used: '#fff', unused: '#111', alias: 'var(--color-unused)' } },
    css: stylesheet(`.card {
      --local: var(--color-used);
      --unused-local: var(--color-alias);
      color: var(--local);
    }`),
  });
  assert.deepEqual(issues, [
    'tokens.json: 未引用 token --color-unused',
    'tokens.json: 未引用 token --color-alias',
  ]);
});

test('tokens report cycles even when every member has an incoming reference', () => {
  const issues = inspectTokens({
    ...project(),
    tokens: { color: { a: 'var(--color-b)', b: 'var(--color-a)' } },
    css: stylesheet('.card { color: var(--color-a); }'),
  });
  assert.equal(issues.length, 1);
  assert.match(issues[0], /变量循环引用 --color-a → --color-b → --color-a$/);
});

test('tokens recognize inline styles and reject unknown JavaScript token members', () => {
  const issues = inspectTokens({
    ...project(`
      import { layout } from '@comfyshop/tokens';
      const Card = () => <div style={{ color: 'var(--color-base)' }} />;
      const gap = layout.missing;
    `),
    tokens: { color: { base: '#fff' } },
    css: [],
  });
  assert.equal(issues.length, 1);
  assert.match(issues[0], /未定义变量 --layout-missing$/);
});
