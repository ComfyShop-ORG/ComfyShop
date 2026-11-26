import { createApiClient } from '@comfyshop/api-client';
import manifest from '../../../api/src/comfyshop_api/core/languages.json' with { type: 'json' };

export type LanguageCode = keyof typeof manifest.languages;
export const languages = manifest.languages;

function isLanguage(code: string): code is LanguageCode {
  return Object.hasOwn(languages, code);
}

const root = typeof document === 'undefined' ? undefined : document.documentElement;
// FastAPI writes the resolved language into the page. Vite uses the same negotiation endpoint.
const presentation =
  root && !root.dataset.language && import.meta.env?.MODE !== 'test'
    ? await createApiClient()
        .presentation()
        .catch(() => undefined)
    : undefined;
const current = root?.dataset.language ?? presentation?.language ?? manifest.default;
export const language = isLanguage(current) ? current : (manifest.default as LanguageCode);
export const locale = languages[language].locale;

export const menuLanguages = (
  root?.dataset.menuLanguages?.split(',') ??
  presentation?.menu ??
  Object.keys(languages)
)
  .filter(isLanguage)
  .map((code) => [code, languages[code]] as const);

export function chooseLanguage(code: LanguageCode) {
  document.cookie = `comfyshop.language=${code}; Path=/; Max-Age=31536000; SameSite=Lax${location.protocol === 'https:' ? '; Secure' : ''}`;
  if (code !== language) window.location.reload();
}
