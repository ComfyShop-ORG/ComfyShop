import { useId, useRef, useState } from 'react';
import { ArchiveIcon, ChevronDownIcon, ChevronUpIcon } from '@radix-ui/react-icons';
import { useInfiniteQuery, useQueryClient } from '@tanstack/react-query';
import type { QueryClient } from '@tanstack/react-query';
import { Button, Collapsible } from '@comfyshop/ui';
import type { ArchivedTeam } from '@comfyshop/api-client';
import { t } from '../../app/i18n';
import { locale } from '../../app/language';
import { refreshPublishedContent } from '../../app/publication-queries';
import { useWorkspace } from '../../app/use-workspace';
import { ActionConfirmation } from '../../components/action-confirmation';
import type { ConfirmationAction } from '../../components/action-confirmation';
import { PaginatedListFeedback } from '../../components/collection-status';
import { useNotify } from '../../components/notify';
import { useAction } from '../../components/use-action';

export async function refreshTeamAvailability(
  queries: QueryClient,
  userId: string | null,
  id: string,
) {
  await Promise.all([
    queries.invalidateQueries({ queryKey: ['teams', userId] }),
    queries.invalidateQueries({ queryKey: ['archived-teams', userId] }),
    queries.invalidateQueries({ queryKey: ['workspace-access', userId, { kind: 'team', id }] }),
    refreshPublishedContent(queries),
  ]);
}

export function ArchivedTeams({ disabled }: { disabled: boolean }) {
  const { identityApi, state } = useWorkspace();
  const queries = useQueryClient();
  const notify = useNotify();
  const id = useId();
  const disclosure = useRef<HTMLButtonElement>(null);
  const [expanded, setExpanded] = useState(false);
  const [confirmation, setConfirmation] = useState<ConfirmationAction>();
  const { busy, error, run, clearError } = useAction();
  const query = useInfiniteQuery({
    queryKey: ['archived-teams', state.userId],
    enabled: !!state.userId,
    refetchOnMount: 'always',
    initialPageParam: null as string | null,
    queryFn: ({ pageParam, signal }) => identityApi.archivedTeams(pageParam, signal),
    getNextPageParam: (page) => page.nextCursor ?? undefined,
  });
  const teams = query.data?.pages.flatMap((page) => page.items) ?? [];
  if (!expanded && !teams.length && !query.error) return null;

  function confirmRestore(team: ArchivedTeam, source: HTMLButtonElement) {
    clearError();
    setConfirmation({
      label: t('teams.restore'),
      prompt: t('teams.restoreConfirm', team.name),
      description:
        t('teams.restoreHelp') + (team.hasQueuedTasks ? ' ' + t('teams.restoreQueued') : ''),
      source,
      execute: async () => {
        await identityApi.restoreTeam(team.id);
        await refreshTeamAvailability(queries, state.userId, team.id);
        notify(t('teams.restored', team.name));
      },
    });
  }

  return (
    <Collapsible.Root className="archived-team-section" open={expanded} onOpenChange={setExpanded}>
      <Collapsible.Trigger asChild>
        <Button
          ref={disclosure}
          className="workspace-entry-link"
          variant="ghost"
          disabled={disabled || busy}
        >
          <ArchiveIcon aria-hidden="true" />
          <span className="workspace-entry-name">{t('teams.archivedTeams')}</span>
          {expanded ? <ChevronUpIcon aria-hidden="true" /> : <ChevronDownIcon aria-hidden="true" />}
        </Button>
      </Collapsible.Trigger>
      <Collapsible.Content>
        <PaginatedListFeedback query={query}>
          {teams.length ? (
            <ul className="workspace-entry-list" aria-label={t('teams.archivedTeams')}>
              {teams.map((team) => {
                const archived = new Date(team.archivedAt);
                return (
                  <li key={team.id} className="workspace-share-account">
                    <div className="archived-team-identity">
                      <strong className="workspace-entry-name" id={id + team.id} title={team.name}>
                        {team.name}
                      </strong>
                      <time className="form-hint" dateTime={archived.toISOString()}>
                        {t(
                          'teams.archivedOn',
                          archived.toLocaleString(locale, {
                            dateStyle: 'medium',
                            timeStyle: 'short',
                          }),
                        )}
                      </time>
                    </div>
                    <Button
                      aria-describedby={id + team.id}
                      disabled={disabled || busy}
                      onClick={(event) => confirmRestore(team, event.currentTarget)}
                    >
                      {t('teams.restore')}
                    </Button>
                  </li>
                );
              })}
            </ul>
          ) : query.isSuccess ? (
            <p className="form-hint">{t('teams.noArchivedTeams')}</p>
          ) : null}
        </PaginatedListFeedback>
      </Collapsible.Content>
      <ActionConfirmation
        action={confirmation}
        busy={busy}
        error={error}
        run={run}
        onClose={() => setConfirmation(undefined)}
        restoreFocus={() => disclosure.current?.focus()}
      />
    </Collapsible.Root>
  );
}
