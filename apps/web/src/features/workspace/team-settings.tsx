import { useId, useRef, useState } from 'react';
import { DotsHorizontalIcon } from '@radix-ui/react-icons';
import { useInfiniteQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router';
import {
  Button,
  Dialog,
  DialogClose,
  DialogContent,
  DropdownMenu,
  Field,
  IconButton,
  Input,
  Select,
} from '@comfyshop/ui';
import { ApiError } from '@comfyshop/api-client';
import type { Team, TeamMember, TeamMemberRole, TeamRole } from '@comfyshop/api-client';
import { t } from '../../app/i18n';
import { locale } from '../../app/language';
import { useWorkspace } from '../../app/use-workspace';
import { workspacePath } from '../../app/workspace-scope';
import { useNotify } from '../../components/notify';
import { ProfileAvatar } from '../../components/profile-avatar';
import { useAction } from '../../components/use-action';
import { PaginatedListFeedback } from '../../components/collection-status';
import { ActionConfirmation } from '../../components/action-confirmation';
import type { ConfirmationAction } from '../../components/action-confirmation';
import { refreshTeamAvailability } from './archived-teams';
import { TeamRoleLabel } from './team-role-label';

const editRoles = ['reader', 'editor', 'manager'] as const;
const rosterOrder: TeamRole[] = ['owner', 'manager', 'editor', 'reader'];

function MemberRow({
  member,
  current,
  actions,
  busy,
  confirming,
  onConfirm,
}: {
  member: TeamMember;
  current: boolean;
  actions?: {
    roles: readonly { value: TeamMemberRole; label: string }[];
    changeRole: (role: TeamMemberRole) => void;
    remove: () => Promise<void>;
    transfer?: () => Promise<void>;
  };
  busy: boolean;
  confirming: boolean;
  onConfirm: (action: ConfirmationAction) => void;
}) {
  const menu = useRef<HTMLButtonElement>(null);
  const name = member.nickname ?? member.username;
  const transfer = actions?.transfer;
  return (
    <li>
      <div className="team-member-identity">
        <ProfileAvatar className="team-member-avatar" name={name} src={member.avatarUrl} />
        <div className="team-member-name">
          <div>
            <strong title={name}>{name}</strong>
            {current && <span>{t('teams.you')}</span>}
          </div>
          {member.nickname && <span title={member.username}>@{member.username}</span>}
        </div>
      </div>
      {actions ? (
        <div className="team-member-controls">
          <Select
            size="small"
            label={t('teams.memberRole', member.username)}
            options={actions.roles}
            value={member.role}
            disabled={busy}
            onValueChange={(next) => actions.changeRole(next as TeamMemberRole)}
          />
          <DropdownMenu.Root>
            <DropdownMenu.Trigger asChild>
              <IconButton
                ref={menu}
                label={t('teams.memberActions', member.username)}
                disabled={busy}
              >
                <DotsHorizontalIcon />
              </IconButton>
            </DropdownMenu.Trigger>
            <DropdownMenu.Portal>
              <DropdownMenu.Content
                className="ui-menu"
                align="end"
                sideOffset={8}
                onCloseAutoFocus={(event) => {
                  if (confirming) event.preventDefault();
                }}
              >
                {transfer && (
                  <DropdownMenu.Item
                    className="ui-menu-item"
                    onSelect={() =>
                      onConfirm({
                        label: t('teams.transfer'),
                        prompt: t('teams.transferTo', member.username),
                        description: t('teams.transferConfirm'),
                        execute: transfer,
                        source: menu.current,
                      })
                    }
                  >
                    {t('teams.transfer')}
                  </DropdownMenu.Item>
                )}
                <DropdownMenu.Item
                  className="ui-menu-item"
                  onSelect={() =>
                    onConfirm({
                      label: t('teams.remove'),
                      prompt: t('teams.removeConfirm', member.username),
                      description: t('teams.removeHelp'),
                      execute: actions.remove,
                      source: menu.current,
                      destructive: true,
                    })
                  }
                >
                  {t('teams.remove')}
                </DropdownMenu.Item>
              </DropdownMenu.Content>
            </DropdownMenu.Portal>
          </DropdownMenu.Root>
        </div>
      ) : (
        <TeamRoleLabel role={member.role} />
      )}
    </li>
  );
}

function Members({
  team,
  onClose,
  onExitTeam,
}: {
  team: Team;
  onClose: () => void;
  onExitTeam: () => void;
}) {
  const { identityApi, state } = useWorkspace();
  const queries = useQueryClient();
  const navigate = useNavigate();
  const notify = useNotify();
  const id = useId();
  const closeButton = useRef<HTMLButtonElement>(null);
  const [username, setUsername] = useState('');
  const [role, setRole] = useState<TeamMemberRole>('reader');
  const [confirmation, setConfirmation] = useState<ConfirmationAction>();
  const [archiveBlocked, setArchiveBlocked] = useState(false);
  const { busy, error, run, clearError } = useAction();
  const queryKey = ['team-members', state.userId, team.id];
  const members = useInfiniteQuery({
    queryKey,
    refetchOnMount: 'always',
    initialPageParam: null as string | null,
    queryFn: ({ pageParam, signal }) => identityApi.teamMembers(team.id, pageParam, signal),
    getNextPageParam: (page) => page.nextCursor ?? undefined,
  });
  const roster = members.data?.pages
    .flatMap((page) => page.items)
    .sort(
      (a, b) =>
        rosterOrder.indexOf(a.role) - rosterOrder.indexOf(b.role) ||
        (a.nickname ?? a.username).localeCompare(b.nickname ?? b.username, locale),
    );
  const owner = team.role === 'owner';
  const canManage = owner || team.role === 'manager';
  const options = editRoles
    .filter((role) => owner || role !== 'manager')
    .map((value) => ({ value, label: t(`teams.${value}`) }));
  const account = username.trim();
  const exitLabel = t(owner ? 'teams.archive' : 'teams.leave');

  function refresh() {
    return Promise.all([
      queries.invalidateQueries({ queryKey }),
      queries.invalidateQueries({ queryKey: ['teams', state.userId] }),
      queries.invalidateQueries({
        queryKey: ['workspace-access', state.userId, { kind: 'team', id: team.id }],
      }),
    ]);
  }

  function confirm(action: ConfirmationAction) {
    clearError();
    setArchiveBlocked(false);
    setConfirmation(action);
  }

  function closeConfirmation() {
    clearError();
    setConfirmation(undefined);
  }

  async function exit() {
    if (owner) {
      try {
        await identityApi.archiveTeam(team.id);
      } catch (error) {
        if (error instanceof ApiError && error.status === 409) setArchiveBlocked(true);
        throw error;
      }
      notify(t('teams.archived', team.name));
    } else {
      await identityApi.removeTeamMember(team.id, state.userId!);
    }
    onExitTeam();
    void navigate('/workspace', { replace: true });
    await (owner ? refreshTeamAvailability(queries, state.userId, team.id) : refresh());
  }

  return (
    <DialogContent
      size="form"
      className="team-dialog team-members-dialog"
      data-inline-notifications=""
      onEscapeKeyDown={(event) => {
        if (busy) event.preventDefault();
      }}
      onInteractOutside={(event) => {
        if (busy) event.preventDefault();
      }}
    >
      <div className="compact-dialog-heading">
        <Dialog.Title>{t('teams.settings', team.name)}</Dialog.Title>
        <DialogClose ref={closeButton} label={t('common.close')} disabled={busy} />
      </div>
      <PaginatedListFeedback query={members}>
        {roster && (
          <ul className="workspace-entry-list team-roster" aria-label={t('teams.members')}>
            {roster.map((member) => {
              const manageable =
                canManage && member.role !== 'owner' && (owner || member.role !== 'manager');
              return (
                <MemberRow
                  key={member.id}
                  member={member}
                  current={member.id === state.userId}
                  busy={busy}
                  confirming={!!confirmation}
                  onConfirm={confirm}
                  actions={
                    manageable
                      ? {
                          roles: options,
                          changeRole: (next) =>
                            void run(async () => {
                              await identityApi.setTeamMember(team.id, member.username, next);
                              await refresh();
                            }),
                          remove: async () => {
                            await identityApi.removeTeamMember(team.id, member.id);
                            await refresh();
                          },
                          transfer: owner
                            ? async () => {
                                await identityApi.transferTeam(team.id, member.id);
                                await refresh();
                              }
                            : undefined,
                        }
                      : undefined
                  }
                />
              );
            })}
          </ul>
        )}
      </PaginatedListFeedback>
      {canManage && (
        <form
          onSubmit={(event) => {
            event.preventDefault();
            if (account.length < 2) return;
            void run(async () => {
              await identityApi.setTeamMember(team.id, account, role);
              setUsername('');
              await refresh();
            });
          }}
        >
          <Field htmlFor={id} label={t('teams.memberAccount')}>
            <div className="team-invite-controls">
              <Input
                id={id}
                required
                minLength={2}
                maxLength={32}
                value={username}
                placeholder={t('teams.accountPlaceholder')}
                autoComplete="off"
                disabled={busy}
                onChange={(event) => setUsername(event.currentTarget.value)}
              />
              <Select
                label={t('teams.role')}
                options={options}
                value={role}
                disabled={busy}
                onValueChange={(next) => setRole(next as TeamMemberRole)}
              />
              <Button type="submit" variant="primary" disabled={busy || account.length < 2}>
                {t('teams.addMember')}
              </Button>
            </div>
          </Field>
        </form>
      )}
      {error && !confirmation && (
        <p role="alert" className="form-error">
          {error}
        </p>
      )}
      <div className="team-dialog-footer">
        <Button
          size="small"
          variant="ghost"
          disabled={busy}
          onClick={(event) =>
            confirm({
              label: exitLabel,
              prompt: t(owner ? 'teams.archiveConfirm' : 'teams.leaveConfirm', team.name),
              description: t(owner ? 'teams.archiveHelp' : 'teams.leaveHelp'),
              execute: exit,
              source: event.currentTarget,
              destructive: true,
            })
          }
        >
          {exitLabel}
        </Button>
      </div>
      <ActionConfirmation
        action={confirmation}
        busy={busy}
        error={error}
        run={run}
        onClose={closeConfirmation}
        restoreFocus={() => closeButton.current?.focus()}
        primaryAction={
          archiveBlocked && error ? (
            <Button
              variant="primary"
              disabled={busy}
              onClick={() => {
                closeConfirmation();
                onClose();
                void navigate(workspacePath(undefined, 'tasks'));
              }}
            >
              {t('teams.openTasks')}
            </Button>
          ) : undefined
        }
      />
    </DialogContent>
  );
}

export function TeamSettings({ team, onExitTeam }: { team: Team; onExitTeam: () => void }) {
  const [open, setOpen] = useState(false);
  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Trigger asChild>
        <Button>{t('teams.members')}</Button>
      </Dialog.Trigger>
      {open && <Members team={team} onClose={() => setOpen(false)} onExitTeam={onExitTeam} />}
    </Dialog.Root>
  );
}
