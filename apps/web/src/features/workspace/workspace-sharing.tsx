import { useId, useState } from 'react';
import type { ReactNode } from 'react';
import { ChevronRightIcon, Link2Icon } from '@radix-ui/react-icons';
import { useInfiniteQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router';
import { Button, Dialog, DialogClose, DialogContent, Field, Input } from '@comfyshop/ui';
import { t } from '../../app/i18n';
import { useWorkspace } from '../../app/use-workspace';
import { workspacePath } from '../../app/workspace-scope';
import { CopyLink } from '../../components/copy-link';
import { PaginatedListFeedback } from '../../components/collection-status';
import { ProfileAvatar } from '../../components/profile-avatar';
import { useAction } from '../../components/use-action';

type Direction = 'sent' | 'received';
type Account = { id: string; username: string };

function useShares(direction: Direction) {
  const { api, state } = useWorkspace();
  return useInfiniteQuery({
    queryKey: ['workspace-shares', state.userId, direction],
    refetchOnMount: 'always',
    initialPageParam: null as string | null,
    queryFn: ({ pageParam, signal }) =>
      api.workspaceShares({ direction, cursor: pageParam }, signal),
    getNextPageParam: (page) => page.nextCursor ?? undefined,
  });
}

function ShareList({
  title,
  empty,
  query,
  row,
  action,
  children,
}: {
  title: string;
  empty: string;
  query: ReturnType<typeof useShares>;
  row: (account: Account) => ReactNode;
  action?: ReactNode;
  children?: ReactNode;
}) {
  const id = useId();
  const items = query.data?.pages.flatMap((page) => page.items) ?? [];
  return (
    <section className="workspace-share-section" aria-labelledby={id}>
      <div className="workspace-share-heading">
        <h3 id={id}>{title}</h3>
        {action}
      </div>
      <PaginatedListFeedback query={query}>
        {items.length > 0 && (
          <ul className="workspace-entry-list" aria-labelledby={id}>
            {items.map((account) => (
              <li key={account.id}>{row(account)}</li>
            ))}
          </ul>
        )}
        {!items.length && query.isSuccess && (
          <p className="form-hint workspace-share-empty">{empty}</p>
        )}
      </PaginatedListFeedback>
      {children}
    </section>
  );
}

function SharingSettings({ onClose }: { onClose: () => void }) {
  const { api, state } = useWorkspace();
  const id = useId();
  const [username, setUsername] = useState('');
  const sent = useShares('sent');
  const received = useShares('received');
  const queries = useQueryClient();
  const { busy, error, run } = useAction();
  const refresh = () =>
    queries.invalidateQueries({ queryKey: ['workspace-shares', state.userId, 'sent'] });
  const account = username.trim();
  return (
    <DialogContent size="form" className="workspace-share-dialog" aria-describedby={id + '-help'}>
      <div className="compact-dialog-heading">
        <Dialog.Title>{t('workspaceSharing.title')}</Dialog.Title>
        <DialogClose label={t('common.close')} />
      </div>
      <Dialog.Description className="form-hint" id={id + '-help'}>
        {t('workspaceSharing.description')}
      </Dialog.Description>
      <ShareList
        title={t('workspaceSharing.sent')}
        empty={t('workspaceSharing.noSent')}
        query={sent}
        action={
          state.userId &&
          sent.data?.pages.some((page) => page.items.length > 0) && (
            <CopyLink
              href={workspacePath({ kind: 'shared', id: state.userId })}
              title={t('workspaceSharing.title')}
              size="normal"
              variant="secondary"
            >
              <Link2Icon aria-hidden="true" />
              {t('workspaceSharing.copy')}
            </CopyLink>
          )
        }
        row={({ id: viewerId, username: viewer }) => (
          <div className="workspace-share-account">
            <ProfileAvatar name={viewer} className="workspace-entry-icon" />
            <span className="workspace-entry-name">{viewer}</span>
            <Button
              size="small"
              variant="ghost"
              aria-label={t('workspaceSharing.revokeFor', viewer)}
              disabled={busy}
              onClick={() =>
                void run(async () => {
                  await api.revokeWorkspaceShare(viewerId);
                  await refresh();
                })
              }
            >
              {t('workflowImport.revoke')}
            </Button>
          </div>
        )}
      >
        <form
          className="workspace-share-form"
          onSubmit={(event) => {
            event.preventDefault();
            if (account.length < 2) return;
            void run(async () => {
              await api.grantWorkspaceShare(account);
              setUsername('');
              await refresh();
            });
          }}
        >
          <Field label={t('loginDialog.username')} htmlFor={id}>
            <div className="field-with-action">
              <Input
                id={id}
                placeholder={t('workspaceSharing.accountPlaceholder')}
                required
                minLength={2}
                maxLength={32}
                autoComplete="off"
                disabled={busy}
                value={username}
                onChange={(event) => setUsername(event.currentTarget.value)}
              />
              <Button type="submit" variant="primary" disabled={busy || account.length < 2}>
                {t('workspaceSharing.grant')}
              </Button>
            </div>
          </Field>
        </form>
        {error && (
          <p role="alert" className="form-error">
            {error}
          </p>
        )}
      </ShareList>
      <ShareList
        title={t('workspaceSharing.received')}
        empty={t('workspaceSharing.noReceived')}
        query={received}
        row={({ id: ownerId, username: owner }) => (
          <Button asChild variant="ghost" className="workspace-entry-link">
            <Link
              to={workspacePath({ kind: 'shared', id: ownerId })}
              aria-label={owner}
              aria-describedby={id + ownerId}
              onClick={onClose}
            >
              <ProfileAvatar name={owner} className="workspace-entry-icon" />
              <span className="workspace-entry-name" title={owner}>
                {owner}
              </span>
              <span id={id + ownerId} className="workspace-access-label">
                {t('workspaceSharing.readOnly')}
              </span>
              <ChevronRightIcon aria-hidden="true" />
            </Link>
          </Button>
        )}
      />
    </DialogContent>
  );
}

export function WorkspaceSharing() {
  const [open, setOpen] = useState(false);
  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Trigger asChild>
        <Button>{t('workspaceSharing.title')}</Button>
      </Dialog.Trigger>
      {open && <SharingSettings onClose={() => setOpen(false)} />}
    </Dialog.Root>
  );
}
