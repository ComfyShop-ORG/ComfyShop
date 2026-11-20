import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router';
import '@comfyshop/tokens/styles.css';
import '@comfyshop/ui/styles.css';
import '@comfyshop/media/styles.css';
import './styles/index.css';
import { App } from './app/app';
import { MotionRoot } from './motion';
import { WorkspaceProvider } from './app/workspace-provider';

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 60_000, retry: 1, refetchOnWindowFocus: false } },
});
createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <WorkspaceProvider>
        <BrowserRouter>
          <MotionRoot>
            <App />
          </MotionRoot>
        </BrowserRouter>
      </WorkspaceProvider>
    </QueryClientProvider>
  </StrictMode>,
);
