import { t } from './i18n.ts';
import { useState } from 'react';
import type { Ref } from 'react';
import {
  CheckIcon,
  DownloadIcon,
  GearIcon,
  GlobeIcon,
  MoonIcon,
  SunIcon,
} from '@radix-ui/react-icons';
import { DropdownMenu, IconButton } from '@comfyshop/ui';
import { chooseLanguage, language, menuLanguages } from './language';
import { useMediaQuery } from './use-media-query';

type DisplayToggle = 'glass' | 'fullWidth' | 'workflowFullscreen';

function rememberDisplayPreference(key: DisplayToggle | 'theme', value: string) {
  try {
    localStorage.setItem(`comfyshop.${key}`, value);
  } catch {
    // 浏览器禁止保存时，切换仍在当前页面生效。
  }
}

export function HeaderPreferences({
  install,
  installOpen,
  installTrigger,
}: {
  install?: () => void;
  installOpen?: boolean;
  installTrigger?: Ref<HTMLButtonElement>;
}) {
  const compact = useMediaQuery('(max-width: 700px)');
  const [theme, setTheme] = useState(() =>
    document.documentElement.dataset.theme === 'light' ? 'light' : 'dark',
  );
  const nextTheme = theme === 'dark' ? 'light' : 'dark';

  function toggleTheme() {
    document.documentElement.dataset.theme = nextTheme;
    document.querySelector('meta[name="color-scheme"]')?.setAttribute('content', nextTheme);
    setTheme(nextTheme);
    rememberDisplayPreference('theme', nextTheme);
  }

  const themeLabel =
    nextTheme === 'light' ? t('themeToggle.switchToLightMode') : t('themeToggle.switchToDarkMode');
  const languageItems =
    menuLanguages.length > 1 &&
    menuLanguages.map(([code, target]) => (
      <DropdownMenu.Item
        className="ui-menu-item"
        key={code}
        lang={target.locale}
        aria-current={code === language ? 'true' : undefined}
        onSelect={() => chooseLanguage(code)}
      >
        {target.label}
      </DropdownMenu.Item>
    ));

  if (compact)
    return (
      <DropdownMenu.Root>
        <DropdownMenu.Trigger asChild>
          <IconButton ref={installTrigger} size="normal" label={t('app.displayPreferences')}>
            <GearIcon />
          </IconButton>
        </DropdownMenu.Trigger>
        <DropdownMenu.Portal>
          <DropdownMenu.Content
            className="ui-menu"
            sideOffset={8}
            align="end"
            onCloseAutoFocus={(event) => {
              if (installOpen) event.preventDefault();
            }}
          >
            <DropdownMenu.Item className="ui-menu-item" onSelect={toggleTheme}>
              {themeLabel}
            </DropdownMenu.Item>
            {languageItems && (
              <DropdownMenu.Group aria-label={t('app.language')}>
                {languageItems}
              </DropdownMenu.Group>
            )}
            {install && (
              <DropdownMenu.Item className="ui-menu-item" onSelect={install}>
                {t('browserApp.install')}
              </DropdownMenu.Item>
            )}
          </DropdownMenu.Content>
        </DropdownMenu.Portal>
      </DropdownMenu.Root>
    );

  return (
    <>
      <IconButton size="normal" label={themeLabel} onClick={toggleTheme}>
        {nextTheme === 'light' ? <SunIcon /> : <MoonIcon />}
      </IconButton>
      {install && (
        <IconButton ref={installTrigger} label={t('browserApp.install')} onClick={install}>
          <DownloadIcon />
        </IconButton>
      )}
      {languageItems && (
        <DropdownMenu.Root>
          <DropdownMenu.Trigger asChild>
            <IconButton size="normal" label={t('app.language')}>
              <GlobeIcon />
            </IconButton>
          </DropdownMenu.Trigger>
          <DropdownMenu.Portal>
            <DropdownMenu.Content className="ui-menu" sideOffset={8} align="end">
              {languageItems}
            </DropdownMenu.Content>
          </DropdownMenu.Portal>
        </DropdownMenu.Root>
      )}
    </>
  );
}

export function DisplayPreferenceItem({
  preference,
  label,
}: {
  preference: DisplayToggle;
  label: string;
}) {
  const [enabled, setEnabled] = useState(
    () => document.documentElement.dataset[preference] === 'on',
  );

  function changePreference(checked: boolean) {
    const value = checked ? 'on' : 'off';
    document.documentElement.dataset[preference] = value;
    setEnabled(checked);
    rememberDisplayPreference(preference, value);
  }

  return (
    <DropdownMenu.CheckboxItem
      className="ui-menu-item"
      checked={enabled}
      onCheckedChange={changePreference}
    >
      {label}
      <DropdownMenu.ItemIndicator>
        <CheckIcon aria-hidden="true" />
      </DropdownMenu.ItemIndicator>
    </DropdownMenu.CheckboxItem>
  );
}
