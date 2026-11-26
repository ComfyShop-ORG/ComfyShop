import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router';
import { I18nextProvider } from 'react-i18next';
import '@comfyshop/tokens/styles.css';
import '@comfyshop/ui/styles.css';
import '@comfyshop/media/styles.css';
import './styles/index.css';
import { App } from './app/app';
import { MotionRoot } from './motion';
import { WorkspaceProvider } from './app/workspace-provider';
import { locale } from './app/language';
import { i18n, t } from './app/i18n';

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 60_000, retry: 1, refetchOnWindowFocus: false } },
});
document.documentElement.lang = locale;
document.querySelector('meta[name="description"]')?.setAttribute('content', t('app.description'));

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <I18nextProvider i18n={i18n}>
      <QueryClientProvider client={queryClient}>
        <WorkspaceProvider>
          <BrowserRouter>
            <MotionRoot>
              <App />
            </MotionRoot>
          </BrowserRouter>
        </WorkspaceProvider>
      </QueryClientProvider>
    </I18nextProvider>
  </StrictMode>,
);
