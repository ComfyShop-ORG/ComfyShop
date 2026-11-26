const taskPath = /^\/workspace\/(?:teams\/[0-9a-f-]{36}\/)?tasks$/;

self.addEventListener('push', (event) => {
  if (!event.data) return;
  event.waitUntil(
    (async () => {
      let message;
      try {
        message = event.data.json();
      } catch {
        return;
      }
      if (
        typeof message?.title !== 'string' ||
        typeof message?.body !== 'string' ||
        typeof message?.url !== 'string' ||
        typeof message?.tag !== 'string'
      )
        return;
      const url = new URL(message.url, self.location.origin);
      if (url.origin !== self.location.origin || !taskPath.test(url.pathname)) return;
      await self.registration.showNotification(message.title, {
        body: message.body,
        icon: '/app-icon-192.png',
        tag: message.tag,
        data: { url: url.href },
      });
    })(),
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  event.waitUntil(
    (async () => {
      const address = event.notification.data?.url;
      if (typeof address !== 'string') return;
      const url = new URL(address);
      if (url.origin !== self.location.origin || !taskPath.test(url.pathname)) return;
      const windows = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
      const opened = windows.find((client) => client.url === url.href);
      if (opened) await opened.focus();
      else await self.clients.openWindow(url.href);
    })(),
  );
});
