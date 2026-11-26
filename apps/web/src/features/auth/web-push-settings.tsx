import { useQuery } from '@tanstack/react-query';
import { Button } from '@comfyshop/ui';
import { isAppleMobileBrowser, isStandalone, browserWorker } from '../../app/browser-app';
import { t } from '../../app/i18n';
import { useWorkspace } from '../../app/use-workspace';
import { useAction } from '../../components/use-action';

function applicationKey(encoded: string) {
  return Uint8Array.from(atob(encoded.replaceAll('-', '+').replaceAll('_', '/')), (char) =>
    char.charCodeAt(0),
  );
}

function matchesKey(subscription: PushSubscription, key: Uint8Array) {
  const buffer = subscription.options.applicationServerKey;
  if (!buffer || buffer.byteLength !== key.length) return false;
  return new Uint8Array(buffer).every((byte, index) => byte === key[index]);
}

export function WebPushSettings() {
  const { state, identityApi: api } = useWorkspace();
  const action = useAction();
  const needsInstallation = isAppleMobileBrowser() && !isStandalone();
  const supported =
    !needsInstallation &&
    window.isSecureContext &&
    'PushManager' in window &&
    'Notification' in window &&
    !!navigator.serviceWorker;
  const query = useQuery({
    queryKey: ['web-push', state.userId],
    enabled: supported && !!state.userId,
    staleTime: 0,
    retry: false,
    refetchOnWindowFocus: true,
    queryFn: async ({ signal }) => {
      const [preference, browser] = await Promise.all([
        api.webPushPreference(signal),
        browserWorker()
          ?.then(async (registration) => ({
            registration,
            subscription: await registration.pushManager.getSubscription(),
          }))
          .catch(() => undefined),
      ]);
      return {
        preference,
        browser,
        permission:
          (await navigator.permissions?.query({ name: 'notifications' }).then(
            ({ state }) => state,
            () => undefined,
          )) ?? Notification.permission,
      };
    },
  });
  const data = query.data;
  const encoded = data?.preference.publicKey;
  const key = encoded ? applicationKey(encoded) : undefined;
  const browser = data?.browser;
  const subscription = browser?.subscription;
  const enabled = !!(
    data?.preference.enabled &&
    subscription &&
    key &&
    matchesKey(subscription, key)
  );
  const denied = data?.permission === 'denied';
  const unavailable = needsInstallation
    ? t('webPush.installFirst')
    : !supported
      ? t('webPush.unavailable')
      : data && !key
        ? t('webPush.serverDisabled')
        : denied
          ? t('webPush.permissionDenied')
          : data && !browser
            ? t('webPush.unavailable')
            : '';

  async function toggle() {
    if (!data) return;
    if (data.preference.enabled && (enabled || unavailable)) {
      await api.disableWebPush();
      await subscription?.unsubscribe().catch(() => undefined);
      await query.refetch();
      return;
    }
    if (!key || !browser) return;
    try {
      const sameKey = subscription && matchesKey(subscription, key);
      if (subscription && !sameKey) await subscription.unsubscribe();
      const next = sameKey
        ? subscription
        : await browser.registration.pushManager.subscribe({
            applicationServerKey: Uint8Array.from(key),
            userVisibleOnly: true,
          });
      const { p256dh, auth } = next.toJSON().keys ?? {};
      if (!p256dh || !auth) throw new Error(t('webPush.unavailable'));
      await api.enableWebPush({
        endpoint: next.endpoint,
        auth,
        p256dh,
        expiresAt: next.expirationTime,
      });
    } catch (error) {
      if (error instanceof DOMException) {
        throw new Error(
          t(error.name === 'NotAllowedError' ? 'webPush.permissionDenied' : 'webPush.unavailable'),
          { cause: error },
        );
      }
      throw error;
    } finally {
      await query.refetch();
    }
  }

  return (
    <div className="account-form">
      <p className="form-hint">{t('webPush.description')}</p>
      {unavailable && <p className="form-hint">{unavailable}</p>}
      {supported && query.isPending && <p role="status">{t('common.loading')}</p>}
      {data && (
        <>
          <p className="form-hint" role="status">
            {t(enabled ? 'webPush.on' : 'webPush.off')}
          </p>
          <div className="account-form-footer">
            <Button
              variant={enabled || unavailable ? 'secondary' : 'primary'}
              disabled={
                action.busy || query.isFetching || (!!unavailable && !data.preference.enabled)
              }
              onClick={() => void action.run(toggle)}
            >
              {t(
                enabled || (unavailable && data.preference.enabled)
                  ? 'webPush.turnOff'
                  : 'webPush.turnOn',
              )}
            </Button>
          </div>
        </>
      )}
      {(action.error || query.error) && (
        <p className="form-error" role="alert">
          {action.error || query.error?.message}
        </p>
      )}
    </div>
  );
}
