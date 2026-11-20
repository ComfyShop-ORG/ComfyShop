import { useState } from 'react';
import { MoonIcon, SunIcon } from '@radix-ui/react-icons';
import { IconButton } from '@comfyshop/ui';

export function ThemeToggle() {
  const [theme, setTheme] = useState(() =>
    document.documentElement.dataset.theme === 'light' ? 'light' : 'dark',
  );
  const nextTheme = theme === 'dark' ? 'light' : 'dark';

  function toggleTheme() {
    document.documentElement.dataset.theme = nextTheme;
    document.querySelector('meta[name="color-scheme"]')?.setAttribute('content', nextTheme);
    setTheme(nextTheme);
    try {
      localStorage.setItem('comfyshop.theme', nextTheme);
    } catch {
      // 浏览器禁止保存时，切换仍在当前页面生效。
    }
  }

  return (
    <IconButton
      className="theme-toggle"
      label={nextTheme === 'light' ? '切换为浅色' : '切换为深色'}
      onClick={toggleTheme}
    >
      {nextTheme === 'light' ? <SunIcon /> : <MoonIcon />}
    </IconButton>
  );
}
