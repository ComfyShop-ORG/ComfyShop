import { readdir, readFile } from 'node:fs/promises';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import postcss from 'postcss';
import valueParser from 'postcss-value-parser';
import { PurgeCSS } from 'purgecss';
import ts from 'typescript';

const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const sourceRoots = ['apps/web/src', 'packages/ui/src', 'packages/media/src'];
const radixVariables = new Set([
  '--radix-select-trigger-width',
  '--radix-select-content-available-width',
  '--radix-select-content-available-height',
  '--radix-select-content-transform-origin',
  '--radix-dropdown-menu-content-transform-origin',
  '--radix-tooltip-content-transform-origin',
  '--radix-popover-content-transform-origin',
  '--radix-collapsible-content-height',
  '--radix-toast-swipe-move-x',
  '--radix-toast-swipe-end-x',
]);

function location(node) {
  const source = node.getSourceFile();
  const { line } = source.getLineAndCharacterOfPosition(node.getStart());
  return `${source.fileName}:${line + 1}`;
}

function variableReferences(value) {
  const names = [];
  valueParser(value).walk((node) => {
    if (node.type !== 'function' || node.value.toLowerCase() !== 'var') return;
    const name = node.nodes.find((child) => child.type !== 'space' && child.type !== 'comment');
    if (name?.type === 'word' && name.value.startsWith('--')) names.push(name.value);
  });
  return names;
}

function visit(source, callback) {
  const walk = (node) => {
    callback(node);
    ts.forEachChild(node, walk);
  };
  walk(source);
}

function templateValues(node, checker) {
  let values = [node.head.text];
  for (const span of node.templateSpans) {
    const type = checker.getTypeAtLocation(span.expression);
    const types = type.isUnion() ? type.types : [type];
    if (!types.every((item) => item.isStringLiteral() || item.isNumberLiteral())) return [];
    if (values.length * types.length > 64) return [];
    values = values.flatMap((prefix) =>
      types.map((item) => `${prefix}${item.value}${span.literal.text}`),
    );
  }
  return values;
}

export async function inspectCss({ css, sources, checker, html = '' }) {
  const templates = [];
  for (const source of sources)
    visit(source, (node) => {
      if (ts.isTemplateExpression(node)) templates.push(...templateValues(node, checker));
    });
  const results = await new PurgeCSS().purge({
    content: [
      ...sources.map((source) => ({ raw: source.text, extension: 'tsx' })),
      { raw: `${html}\n${templates.join('\n')}`, extension: 'html' },
    ],
    css: css.map(({ file, text }) => ({ raw: text, name: file })),
    rejected: true,
    keyframes: true,
    // Radix writes these attributes after render; Dialog.Title renders h2.
    // Native select reset rules belong to the shared stylesheet contract.
    // Radix also sets role on tab panels and data-swipe on toasts while they are dragged.
    dynamicAttributes: [
      'data-state',
      'data-highlighted',
      'data-disabled',
      'data-swipe',
      'data-scroll-locked',
      'role',
      'tabindex',
    ],
    safelist: ['html', 'body', 'select', 'h2'],
  });
  const issues = [];
  for (const [index, result] of results.entries()) {
    const original = postcss.parse(css[index].text, { from: css[index].file });
    const removed = new Set(result.rejected);
    original.walkRules((rule) => {
      for (const selector of rule.selectors)
        if (removed.has(selector))
          issues.push(`${css[index].file}:${rule.source.start.line}: 未引用选择器 ${selector}`);
    });
    const remaining = new Set();
    postcss.parse(result.css).walkAtRules(/^(?:-\w+-)?keyframes$/i, (rule) => {
      remaining.add(rule.params);
    });
    original.walkAtRules(/^(?:-\w+-)?keyframes$/i, (rule) => {
      if (!remaining.has(rule.params))
        issues.push(`${css[index].file}:${rule.source.start.line}: 未引用动画 ${rule.params}`);
    });
  }
  return issues;
}

export function inspectTokens({ tokens, css, sources, checker }) {
  const definitions = new Map();
  const tokenNames = new Set();
  const references = [];
  const roots = new Set();
  const issues = [];
  const define = (name) => {
    if (!definitions.has(name)) definitions.set(name, new Set());
  };
  const reference = (name, site, owner) => {
    references.push({ name, site });
    if (owner) definitions.get(owner).add(name);
    else roots.add(name);
  };
  for (const [group, values] of Object.entries(tokens)) {
    const prefix = group === 'lightColor' ? 'color' : group;
    for (const [key, value] of Object.entries(values)) {
      const name = `--${prefix}-${key}`;
      tokenNames.add(name);
      define(name);
      for (const dependency of variableReferences(String(value)))
        reference(dependency, `tokens.json: ${name}`, name);
    }
  }
  for (const { file, text } of css) {
    const sheet = postcss.parse(text, { from: file });
    sheet.walkDecls((declaration) => {
      const owner = declaration.prop.startsWith('--') ? declaration.prop : undefined;
      if (owner) define(owner);
      for (const name of variableReferences(declaration.value))
        reference(name, `${file}:${declaration.source.start.line}`, owner);
    });
    sheet.walkAtRules((rule) => {
      for (const name of variableReferences(rule.params))
        reference(name, `${file}:${rule.source.start.line}`);
    });
  }

  const bindings = new Map();
  for (const source of sources) {
    for (const statement of source.statements) {
      if (
        !ts.isImportDeclaration(statement) ||
        statement.moduleSpecifier.text !== '@comfyshop/tokens'
      )
        continue;
      const imports = statement.importClause?.namedBindings;
      if (imports && ts.isNamespaceImport(imports))
        bindings.set(checker.getSymbolAtLocation(imports.name), []);
      else if (imports && ts.isNamedImports(imports))
        for (const specifier of imports.elements)
          bindings.set(checker.getSymbolAtLocation(specifier.name), [
            (specifier.propertyName ?? specifier.name).text,
          ]);
    }
  }
  const tokenPath = (node) => {
    if (ts.isIdentifier(node)) return bindings.get(checker.getSymbolAtLocation(node));
    if (ts.isPropertyAccessExpression(node)) {
      const base = tokenPath(node.expression);
      return base && [...base, node.name.text];
    }
    if (ts.isElementAccessExpression(node)) {
      const base = tokenPath(node.expression);
      if (!base) return undefined;
      const key = checker.getTypeAtLocation(node.argumentExpression);
      // A dynamic key or a group passed elsewhere may read any member.
      return key.isStringLiteral() || key.isNumberLiteral() ? [...base, String(key.value)] : base;
    }
    return undefined;
  };
  for (const source of sources) {
    visit(source, (node) => {
      if (
        ts.isStringLiteralLike(node) ||
        ts.isTemplateHead(node) ||
        ts.isTemplateMiddle(node) ||
        ts.isTemplateTail(node)
      ) {
        for (const name of variableReferences(node.text)) reference(name, location(node));
        if (node.text.startsWith('--') && /^--[\w-]+$/.test(node.text))
          reference(node.text, location(node));
      }
      const parent = node.parent;
      if (
        parent &&
        (ts.isImportSpecifier(parent) ||
          ts.isNamespaceImport(parent) ||
          ((ts.isPropertyAccessExpression(parent) || ts.isElementAccessExpression(parent)) &&
            parent.expression === node))
      )
        return;
      const path = tokenPath(node);
      if (!path) return;
      if (path.length >= 2) reference(`--${path[0]}-${path[1]}`, location(node));
      else
        for (const name of tokenNames)
          if (path.length === 0 || name.startsWith(`--${path[0]}-`))
            reference(name, location(node));
    });
  }

  for (const { name, site } of references)
    if (!definitions.has(name) && !radixVariables.has(name))
      issues.push(`${site}: 未定义变量 ${name}`);

  const visited = new Set();
  const active = new Set();
  const checkCycle = (name, trail) => {
    if (active.has(name)) {
      issues.push(`变量循环引用 ${[...trail.slice(trail.indexOf(name)), name].join(' → ')}`);
      return;
    }
    if (visited.has(name)) return;
    visited.add(name);
    active.add(name);
    for (const dependency of definitions.get(name) ?? []) checkCycle(dependency, [...trail, name]);
    active.delete(name);
  };
  for (const name of definitions.keys()) checkCycle(name, []);
  const used = new Set();
  const markUsed = (name) => {
    if (used.has(name)) return;
    used.add(name);
    for (const dependency of definitions.get(name) ?? []) markUsed(dependency);
  };
  for (const name of roots) markUsed(name);
  for (const name of tokenNames)
    if (!used.has(name)) issues.push(`tokens.json: 未引用 token ${name}`);
  return [...new Set(issues)];
}

async function main(mode) {
  if (!['css', 'tokens'].includes(mode))
    throw new Error('用法：node tooling/check-styles.mjs css|tokens');
  const files = [];
  async function walk(directory) {
    for (const entry of await readdir(directory, { withFileTypes: true })) {
      const file = join(directory, entry.name);
      if (entry.isDirectory()) await walk(file);
      else if (/\.(css|tsx?)$/.test(file) && !/\.(test\.[^.]+|d\.ts)$/.test(file)) files.push(file);
    }
  }
  for (const directory of sourceRoots) await walk(join(projectRoot, directory));
  const configPath = join(projectRoot, 'tsconfig.json');
  const config = ts.readConfigFile(configPath, ts.sys.readFile);
  if (config.error)
    throw new Error(ts.flattenDiagnosticMessageText(config.error.messageText, '\n'));
  const parsed = ts.parseJsonConfigFileContent(config.config, ts.sys, projectRoot);
  const program = ts.createProgram(parsed.fileNames, parsed.options);
  const sources = files
    .filter((file) => !file.endsWith('.css'))
    .map((file) => program.getSourceFile(file));
  if (sources.some((source) => !source)) throw new Error('TypeScript 配置未覆盖全部样式消费文件');
  const css = await Promise.all(
    files
      .filter((file) => file.endsWith('.css'))
      .map(async (file) => ({ file, text: await readFile(file, 'utf8') })),
  );
  const checker = program.getTypeChecker();
  const tokens = JSON.parse(
    await readFile(join(projectRoot, 'packages/tokens/src/tokens.json'), 'utf8'),
  );
  const issues =
    mode === 'css'
      ? await inspectCss({
          css,
          sources,
          checker,
          html: await readFile(join(projectRoot, 'apps/web/index.html'), 'utf8'),
        })
      : inspectTokens({ tokens, css, sources, checker });
  if (issues.length) {
    console.error(issues.join('\n'));
    process.exitCode = 1;
  } else console.log(mode === 'css' ? `CSS 检查通过（${css.length} 个文件）` : 'Token 检查通过');
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href)
  await main(process.argv[2]);
