import { useEffect, useState } from 'react';
import { Dialog, DialogClose, DialogContent } from '@comfyshop/ui';
import { t } from './i18n';
import { useMediaQuery } from './use-media-query';

type InstallPrompt = Event & { prompt: () => Promise<{ outcome: 'accepted' | 'dismissed' }> };
const appleMobile =
  /iPhone|iPad|iPod/.test(navigator.userAgent) ||
  (/Macintosh/.test(navigator.userAgent) && navigator.maxTouchPoints > 1);
const desktopSafari =
  /Macintosh.*Safari/.test(navigator.userAgent) &&
  !/Chrome|Chromium|Edge|Edg\//.test(navigator.userAgent);

export function isAppleMobileBrowser() {
  return appleMobile;
}

export function isStandalone() {
  return (
    matchMedia('(display-mode: standalone)').matches ||
    (navigator as Navigator & { standalone?: boolean }).standalone === true
  );
}

let worker: Promise<ServiceWorkerRegistration> | undefined;

export function browserWorker() {
  if (!window.isSecureContext || !navigator.serviceWorker) return;
  worker ??= navigator.serviceWorker
    .register('/service-worker.js', { updateViaCache: 'none' })
    .then((registration) => (registration.active ? registration : navigator.serviceWorker.ready))
    .catch((error: unknown) => {
      worker = undefined;
      throw error;
    });
  return worker;
}

export function useBrowserInstall() {
  const displayStandalone = useMediaQuery('(display-mode: standalone)');
  const [prompt, setPrompt] = useState<InstallPrompt>();
  const [installed, setInstalled] = useState(false);
  const [open, setOpen] = useState(false);
  useEffect(() => {
    function capture(event: Event) {
      event.preventDefault();
      setPrompt(event as InstallPrompt);
    }
    function finish() {
      setInstalled(true);
      setPrompt(undefined);
    }
    window.addEventListener('beforeinstallprompt', capture);
    window.addEventListener('appinstalled', finish);
    void browserWorker()?.catch(() => undefined);
    return () => {
      window.removeEventListener('beforeinstallprompt', capture);
      window.removeEventListener('appinstalled', finish);
    };
  }, []);
  function install() {
    if (!prompt) {
      setOpen(true);
      return;
    }
    setPrompt(undefined);
    void prompt.prompt().then(
      ({ outcome }) => {
        if (outcome === 'accepted') setInstalled(true);
      },
      () => setOpen(true),
    );
  }
  return {
    available:
      !displayStandalone &&
      !isStandalone() &&
      !installed &&
      (!!prompt || appleMobile || desktopSafari),
    install,
    open,
    setOpen,
  };
}

export function BrowserInstallDialog({
  open,
  onOpenChange,
  restoreFocus,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  restoreFocus: () => void;
}) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <DialogContent
        size="compact"
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          restoreFocus();
        }}
      >
        <div className="compact-dialog-heading">
          <Dialog.Title>{t('browserApp.install')}</Dialog.Title>
          <DialogClose label={t('common.close')} />
        </div>
        <Dialog.Description className="form-hint">
          {t(
            appleMobile
              ? 'browserApp.installHomeScreen'
              : desktopSafari
                ? 'browserApp.installDock'
                : 'browserApp.installBrowserMenu',
          )}
        </Dialog.Description>
      </DialogContent>
    </Dialog.Root>
  );
}
