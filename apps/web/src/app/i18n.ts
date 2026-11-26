import { createInstance } from 'i18next';
import { initReactI18next } from 'react-i18next';
import { language } from './language.ts';
import en from './locales/en.json' with { type: 'json' };
import ja from './locales/ja.json' with { type: 'json' };
import ko from './locales/ko.json' with { type: 'json' };
import zhTw from './locales/zh-tw.json' with { type: 'json' };
import zh from './locales/zh.json' with { type: 'json' };
import type { LanguageCode } from './language.ts';

type MessageKey = keyof typeof zh;
type Value = string | number | boolean | bigint | undefined | null;
const catalogs = { zh, 'zh-tw': zhTw, en, ja, ko } satisfies Record<
  LanguageCode,
  Record<MessageKey, string>
>;

export const i18n = createInstance();
void i18n.use(initReactI18next).init({
  lng: language,
  load: 'currentOnly',
  lowerCaseLng: true,
  fallbackLng: false,
  keySeparator: false,
  initAsync: false,
  interpolation: { escapeValue: false },
  resources: Object.fromEntries(
    Object.entries(catalogs).map(([code, translation]) => [code, { translation }]),
  ),
});

// Every document uses one language. The menu reloads the same URL with the chosen preference.
export function t(key: MessageKey, ...values: Value[]): string {
  return i18n.t(
    key,
    Object.fromEntries(values.map((value, index) => [`arg${index}`, value ?? ''])),
  );
}
