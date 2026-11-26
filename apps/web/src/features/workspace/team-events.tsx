import { useDeferredValue, useRef, useState } from 'react';
import { useInfiniteQuery } from '@tanstack/react-query';
import { Dialog, DialogClose, SearchField, Select } from '@comfyshop/ui';
import { DatePicker } from '@comfyshop/ui/date-picker';
import type { Team, TeamEvent } from '@comfyshop/api-client';
import { i18n, t } from '../../app/i18n';
import { locale } from '../../app/language';
import { useWorkspace } from '../../app/use-workspace';
import { EmptyState, PaginatedListFeedback } from '../../components/collection-status';
import { FilterToolbar } from '../../components/page-toolbar';
import { localDayBounds } from '../../data/local-day';

const categories = [
  'team',
  'project',
  'member',
  'machine',
  'workflow',
  'favorite',
  'task',
  'execution',
  'artifact',
  'work',
  'asset',
] as const;

type ActionKey = Extract<Parameters<typeof t>[0], `teamEvents.action.${string}`>;

function EventRow({ event }: { event: TeamEvent }) {
  const [kind, action] = event.action.split('.');
  const category = categories.find((item) => item === kind);
  const actionKey = `teamEvents.action.${action}` as ActionKey;
  const timestamp = new Date(event.created);
  return (
    <li className="team-event-entry">
      <div>
        <strong>
          {category && `${t(`teamEvents.category.${category}`)} · `}
          {i18n.exists(actionKey) ? t(actionKey) : t('teamEvents.unknownAction')}
        </strong>
        <span title={event.recordId}>{event.target ?? event.recordId}</span>
      </div>
      <div>
        <span>
          {event.actorName ?? t('teamEvents.deletedAccount')}
          {event.actorUsername && event.actorUsername !== event.actorName && (
            <> · @{event.actorUsername}</>
          )}
        </span>
        <time dateTime={timestamp.toISOString()}>{timestamp.toLocaleString(locale)}</time>
      </div>
    </li>
  );
}

export function TeamEvents({ team }: { team: Team }) {
  const { identityApi, state } = useWorkspace();
  const [actor, setActor] = useState('');
  const [kind, setKind] = useState('all');
  const [date, setDate] = useState<Date>();
  const actorInput = useRef<HTMLInputElement>(null);
  const search = useDeferredValue(actor.trim());
  const category = categories.find((item) => item === kind);
  const filters = { actor: search, category, ...(date && localDayBounds(date)) };
  const query = useInfiniteQuery({
    queryKey: ['team-events', state.userId, team.id, filters],
    refetchOnMount: 'always',
    initialPageParam: null as string | null,
    queryFn: ({ pageParam, signal }) =>
      identityApi.teamEvents(team.id, { ...filters, cursor: pageParam }, signal),
    getNextPageParam: (page) => page.nextCursor ?? undefined,
  });
  const events = query.data?.pages.flatMap((page) => page.items) ?? [];
  const filtered = !!(actor || category || date);
  function clear() {
    setActor('');
    setKind('all');
    setDate(undefined);
  }
  return (
    <section className="team-dialog team-events">
      <header className="compact-dialog-heading">
        <Dialog.Title>{t('teamEvents.title', team.name)}</Dialog.Title>
        <DialogClose label={t('common.close')} />
      </header>
      <FilterToolbar onClear={filtered ? clear : undefined} focusOnClear={actorInput} standalone>
        <SearchField
          ref={actorInput}
          aria-label={t('teamEvents.actor')}
          placeholder={t('teamEvents.actor')}
          clearLabel={t('app.clearSearch')}
          maxLength={64}
          value={actor}
          onValueChange={setActor}
        />
        <Select
          label={t('teamEvents.category')}
          value={kind}
          onValueChange={setKind}
          options={[
            { value: 'all', label: t('teamEvents.all') },
            ...categories.map((value) => ({ value, label: t(`teamEvents.category.${value}`) })),
          ]}
        />
        <DatePicker
          label={t('teamEvents.date')}
          todayLabel={t('workspaceResults.today')}
          clearLabel={t('workspaceResults.clearDate')}
          locale={locale}
          value={date}
          onValueChange={setDate}
        />
      </FilterToolbar>
      <PaginatedListFeedback query={query}>
        {events.length > 0 ? (
          <ol className="team-event-list" role="list">
            {events.map((event) => (
              <EventRow key={event.id} event={event} />
            ))}
          </ol>
        ) : (
          query.isSuccess && (
            <EmptyState label={t(filtered ? 'teamEvents.noMatches' : 'teamEvents.empty')} />
          )
        )}
      </PaginatedListFeedback>
    </section>
  );
}
