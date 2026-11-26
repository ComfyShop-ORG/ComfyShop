import { useId, useState } from 'react';
import { ChevronDownIcon, ChevronUpIcon } from '@radix-ui/react-icons';
import { useInfiniteQuery, useQueryClient } from '@tanstack/react-query';
import { Button, Collapsible, Field, Input } from '@comfyshop/ui';
import { t } from '../../app/i18n';
import { useWorkspace } from '../../app/use-workspace';
import { useAction } from '../../components/use-action';
import { PaginatedListFeedback } from '../../components/collection-status';

export function OfficialImportGrants() {
  const { api, state } = useWorkspace();
  const queries = useQueryClient();
  const [open, setOpen] = useState(false);
  const [username, setUsername] = useState('');
  const id = useId();
  const { busy, error, run } = useAction();
  const queryKey = ['official-import-grants', state.userId];
  const grants = useInfiniteQuery({
    queryKey,
    enabled: open && state.canManageOfficialImportGrants,
    initialPageParam: null as string | null,
    queryFn: ({ pageParam, signal }) => api.officialImportGrants(pageParam, signal),
    getNextPageParam: (page) => page.nextCursor ?? undefined,
  });
  const accounts = grants.data?.pages.flatMap((page) => page.items) ?? [];
  function change(account: string, granted: boolean) {
    void run(async () => {
      await api.setOfficialImportGrant(account, granted);
      if (granted) setUsername('');
      await queries.invalidateQueries({ queryKey });
    });
  }
  return (
    <Collapsible.Root open={open} onOpenChange={setOpen}>
      <Collapsible.Trigger asChild>
        <Button size="small" variant="ghost">
          {t('workflowImport.manageGrants')}
          {open ? <ChevronUpIcon /> : <ChevronDownIcon />}
        </Button>
      </Collapsible.Trigger>
      <Collapsible.Content className="machine-setup-panel">
        <p className="form-hint">{t('workflowImport.grantHelp')}</p>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            if (username.trim()) change(username.trim(), true);
          }}
        >
          <Field label={t('loginDialog.username')} htmlFor={id}>
            <div className="field-with-action">
              <Input
                id={id}
                required
                maxLength={32}
                value={username}
                disabled={busy}
                onChange={(event) => setUsername(event.target.value)}
              />
              <Button type="submit" disabled={busy || !username.trim()}>
                {t('workflowImport.grant')}
              </Button>
            </div>
          </Field>
        </form>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <PaginatedListFeedback query={grants} plain>
          {accounts.length > 0 && (
            <ul className="account-grants" aria-label={t('workflowImport.grantedAccounts')}>
              {accounts.map((account) => (
                <li key={account}>
                  <span id={id + '-' + account}>{account}</span>
                  <Button
                    size="small"
                    aria-describedby={id + '-' + account}
                    disabled={busy}
                    onClick={() => change(account, false)}
                  >
                    {t('workflowImport.revoke')}
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </PaginatedListFeedback>
      </Collapsible.Content>
    </Collapsible.Root>
  );
}
