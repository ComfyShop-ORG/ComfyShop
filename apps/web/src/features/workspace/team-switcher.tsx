import { useId, useRef, useState } from 'react';
import { CheckIcon, ChevronRightIcon, PersonIcon, PlusIcon } from '@radix-ui/react-icons';
import { useInfiniteQuery, useQueryClient } from '@tanstack/react-query';
import { Button, Dialog, DialogClose, DialogContent, Field, Input } from '@comfyshop/ui';
import type { Team } from '@comfyshop/api-client';
import { t } from '../../app/i18n';
import { useWorkspace } from '../../app/use-workspace';
import { useAction } from '../../components/use-action';
import { ProfileAvatar } from '../../components/profile-avatar';
import { useNotify } from '../../components/notify';
import { PaginatedListFeedback } from '../../components/collection-status';
import { ArchivedTeams } from './archived-teams';
import { TeamRoleLabel } from './team-role-label';

function useTeamPages() {
  const { identityApi, state } = useWorkspace();
  return useInfiniteQuery({
    queryKey: ['teams', state.userId],
    enabled: !!state.userId,
    refetchOnMount: 'always',
    initialPageParam: null as string | null,
    queryFn: ({ pageParam, signal }) => identityApi.teams(pageParam, signal),
    getNextPageParam: (page) => page.nextCursor ?? undefined,
  });
}

function TeamChoices({
  teamId,
  onSelect,
  onClose,
  restoreFocus,
}: {
  teamId?: string;
  onSelect: (id?: string) => void;
  onClose: () => void;
  restoreFocus: () => void;
}) {
  const { identityApi, state } = useWorkspace();
  const query = useTeamPages();
  const queries = useQueryClient();
  const id = useId();
  const [name, setName] = useState('');
  const [creating, setCreating] = useState(false);
  const createTrigger = useRef<HTMLButtonElement>(null);
  const { busy, error, run, clearError } = useAction();

  function cancelCreate() {
    setCreating(false);
    clearError();
    requestAnimationFrame(() => createTrigger.current?.focus());
  }

  function selectSpace(id?: string) {
    onSelect(id);
    onClose();
  }

  return (
    <DialogContent
      size="form"
      className="team-dialog team-switch-dialog"
      data-inline-notifications=""
      onCloseAutoFocus={(event) => {
        event.preventDefault();
        restoreFocus();
      }}
      onEscapeKeyDown={(event) => {
        if (creating) {
          event.preventDefault();
          if (!busy) cancelCreate();
        }
      }}
      onInteractOutside={(event) => {
        if (busy) event.preventDefault();
      }}
    >
      <div className="compact-dialog-heading">
        <Dialog.Title>{t('teams.switcher')}</Dialog.Title>
        <DialogClose label={t('common.close')} disabled={busy} />
      </div>
      <ul className="workspace-entry-list">
        <li>
          <Button
            variant="ghost"
            className="workspace-entry-link"
            aria-current={teamId ? undefined : 'true'}
            disabled={busy}
            onClick={() => selectSpace()}
          >
            <span className="workspace-entry-icon">
              <PersonIcon aria-hidden="true" />
            </span>
            <span className="workspace-entry-name">{t('app.workspace')}</span>
            {teamId ? <ChevronRightIcon aria-hidden="true" /> : <CheckIcon aria-hidden="true" />}
          </Button>
        </li>
        {query.data?.pages
          .flatMap((page) => page.items)
          .map((choice) => (
            <li key={choice.id}>
              <Button
                variant="ghost"
                className="workspace-entry-link"
                aria-current={teamId === choice.id ? 'true' : undefined}
                disabled={busy}
                aria-label={choice.name}
                aria-describedby={id + choice.id}
                onClick={() => selectSpace(choice.id)}
              >
                <ProfileAvatar
                  name={choice.name}
                  src={choice.avatarUrl}
                  className="workspace-entry-icon"
                />
                <span className="workspace-entry-name" title={choice.name}>
                  {choice.name}
                </span>
                <TeamRoleLabel role={choice.role} id={id + choice.id} />
                {teamId === choice.id ? (
                  <CheckIcon aria-hidden="true" />
                ) : (
                  <ChevronRightIcon aria-hidden="true" />
                )}
              </Button>
            </li>
          ))}
      </ul>
      <PaginatedListFeedback query={query} />
      {creating ? (
        <form
          onSubmit={(event) => {
            event.preventDefault();
            if (!name.trim()) return;
            void run(async () => {
              const created = await identityApi.createTeam(name.trim());
              await queries.invalidateQueries({ queryKey: ['teams', state.userId] });
              selectSpace(created.id);
            });
          }}
        >
          <Field htmlFor={id} label={t('teams.name')}>
            <div className="field-with-action">
              <Input
                id={id}
                maxLength={80}
                required
                autoFocus
                value={name}
                disabled={busy}
                onChange={(event) => setName(event.currentTarget.value)}
              />
              <Button type="submit" variant="primary" disabled={busy || !name.trim()}>
                {t('teams.create')}
              </Button>
            </div>
          </Field>
          <Button
            className="team-create-cancel"
            size="small"
            variant="ghost"
            disabled={busy}
            onClick={cancelCreate}
          >
            {t('deleteButton.cancel')}
          </Button>
        </form>
      ) : (
        <Button
          ref={createTrigger}
          className="team-create-trigger"
          onClick={() => setCreating(true)}
        >
          <PlusIcon aria-hidden="true" />
          {t('teams.create')}
        </Button>
      )}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      <ArchivedTeams disabled={busy} />
    </DialogContent>
  );
}

export function TeamSwitcher(props: Parameters<typeof TeamChoices>[0]) {
  return (
    <Dialog.Root open onOpenChange={(open) => !open && props.onClose()}>
      <TeamChoices {...props} />
    </Dialog.Root>
  );
}

type CopySource = { assetId: string } | { workflowId: string; versionId: string };

function TeamCopyDialog({ source, onClose }: { source: CopySource; onClose: () => void }) {
  const { identityApi } = useWorkspace();
  const queries = useQueryClient();
  const list = useTeamPages();
  const { busy, error, run } = useAction();
  const notify = useNotify();
  const id = useId();
  const choices = list.data?.pages
    .flatMap((page) => page.items)
    .filter((team) => team.role !== 'reader');

  function copy(team: Team) {
    void run(async () => {
      if ('assetId' in source) await identityApi.copyAssetToTeam(team.id, source.assetId);
      else await identityApi.copyWorkflowToTeam(team.id, source.workflowId, source.versionId);
      await queries.invalidateQueries({
        queryKey: ['assetId' in source ? 'asset-library' : 'workflows'],
      });
      notify(t('teams.copied', team.name));
      onClose();
    });
  }
  return (
    <DialogContent size="form" className="team-dialog" aria-describedby={id}>
      <div className="compact-dialog-heading">
        <Dialog.Title>{t('teams.copy')}</Dialog.Title>
        <DialogClose label={t('common.close')} />
      </div>
      <Dialog.Description id={id} className="form-hint">
        {t('assetId' in source ? 'teams.copyAssetHelp' : 'teams.copyWorkflowHelp')}
      </Dialog.Description>
      {choices && choices.length > 0 && (
        <ul className="account-grants">
          {choices.map((team) => (
            <li key={team.id}>
              <span>{team.name}</span>
              <Button
                size="small"
                aria-label={t('teams.copyTo', team.name)}
                disabled={busy}
                onClick={() => copy(team)}
              >
                {t('teams.copyAction')}
              </Button>
            </li>
          ))}
        </ul>
      )}
      {list.isSuccess && !list.hasNextPage && !choices?.length && (
        <p className="form-hint">{t('teams.noEditableTeams')}</p>
      )}
      <PaginatedListFeedback query={list} />
      {error && (
        <p role="alert" className="form-error">
          {error}
        </p>
      )}
    </DialogContent>
  );
}

export function CopyToTeam({ source }: { source: CopySource }) {
  const [open, setOpen] = useState(false);
  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Trigger asChild>
        <Button size="small">{t('teams.copy')}</Button>
      </Dialog.Trigger>
      {open && <TeamCopyDialog source={source} onClose={() => setOpen(false)} />}
    </Dialog.Root>
  );
}
