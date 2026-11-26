import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import { languages } from './language.ts';
import zh from './locales/zh.json' with { type: 'json' };

void test('each language translates every message with the same interpolation parameters', () => {
  const placeholders = (text: string) => text.match(/\{\w+\}/g)?.sort() ?? [];
  for (const language of Object.keys(languages)) {
    const file = new URL(`./locales/${language}.json`, import.meta.url);
    const messages = JSON.parse(readFileSync(file, 'utf8')) as Record<string, string>;
    assert.deepEqual(Object.keys(messages).sort(), Object.keys(zh).sort());
    for (const [key, source] of Object.entries(zh)) {
      assert.deepEqual(placeholders(messages[key]), placeholders(source), `${language} ${key}`);
    }
  }
});
