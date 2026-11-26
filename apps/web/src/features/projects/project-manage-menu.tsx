import { useRef, useState } from 'react';
import { useNavigate } from 'react-router';
import { DotsHorizontalIcon } from '@radix-ui/react-icons';
import { DropdownMenu, IconButton } from '@comfyshop/ui';
import type { Project } from '@comfyshop/api-client';
import { t } from '../../app/i18n';
import { useWorkspace } from '../../app/use-workspace';
import { projectsPath } from '../../app/workspace-scope';
import { ActionConfirmation } from '../../components/action-confirmation';
import type { ConfirmationAction } from '../../components/action-confirmation';
import { DeleteButton } from '../../components/delete-button';
import { useNotify } from '../../components/notify';
import { useAction } from '../../components/use-action';
import { ProjectFormDialog } from './project-form-dialog';
import { useProjectCache } from './project-queries';

type ProjectAction = 'edit' | 'archive' | 'unarchive' | 'delete';

export function ProjectManageMenu({ project }: { project: Project }) {
  const { api, workspaceScope, canEditWorkspace, canManageWorkspace } = useWorkspace();
  const navigate = useNavigate();
  const notify = useNotify();
  const cache = useProjectCache();
  const trigger = useRef<HTMLButtonElement>(null);
  const requested = useRef<ProjectAction | null>(null);
  const [action, setAction] = useState<ProjectAction | null>(null);
  const { busy, error, run, clearError } = useAction();
  const archived = project.archivedAt !== null;
  const canEdit = canEditWorkspace && !archived;
  if (!canEdit && !canManageWorkspace) return null;

  const close = () => setAction(null);
  const restoreFocus = () => trigger.current?.focus({ preventScroll: true });
  let confirmation: ConfirmationAction | undefined;
  if (action === 'archive' || action === 'unarchive') {
    const archive = action === 'archive';
    confirmation = {
      label: t(archive ? 'projects.archive' : 'projects.unarchive'),
      prompt: t(archive ? 'projects.archivePrompt' : 'projects.unarchivePrompt', project.name),
      description: t(archive ? 'projects.archiveDescription' : 'projects.unarchiveDescription'),
      source: null,
      execute: async () => {
        await cache.save(await api.setProjectArchived(project.id, archive));
        notify(t(archive ? 'projects.archivedNotice' : 'projects.unarchivedNotice'));
      },
    };
  }

  return (
    <>
      <DropdownMenu.Root>
        <DropdownMenu.Trigger asChild>
          <IconButton ref={trigger} label={t('projects.actions')} size="normal">
            <DotsHorizontalIcon aria-hidden="true" />
          </IconButton>
        </DropdownMenu.Trigger>
        <DropdownMenu.Portal>
          <DropdownMenu.Content
            className="ui-menu"
            align="end"
            sideOffset={8}
            onCloseAutoFocus={(event) => {
              if (!requested.current) return;
              event.preventDefault();
              clearError();
              setAction(requested.current);
              requested.current = null;
            }}
          >
            {canEdit && (
              <DropdownMenu.Item
                className="ui-menu-item"
                onSelect={() => (requested.current = 'edit')}
              >
                {t('projects.edit')}
              </DropdownMenu.Item>
            )}
            {canManageWorkspace && (
              <>
                <DropdownMenu.Item
                  className="ui-menu-item"
                  onSelect={() => (requested.current = archived ? 'unarchive' : 'archive')}
                >
                  {t(archived ? 'projects.unarchive' : 'projects.archive')}
                </DropdownMenu.Item>
                <DropdownMenu.Item
                  className="ui-menu-item"
                  onSelect={() => (requested.current = 'delete')}
                >
                  {t('projects.delete')}
                </DropdownMenu.Item>
              </>
            )}
          </DropdownMenu.Content>
        </DropdownMenu.Portal>
      </DropdownMenu.Root>
      {action === 'edit' && (
        <ProjectFormDialog
          project={project}
          onClose={close}
          onSaved={close}
          restoreFocus={restoreFocus}
        />
      )}
      <ActionConfirmation
        action={confirmation}
        busy={busy}
        error={error}
        run={run}
        onClose={close}
        restoreFocus={restoreFocus}
      />
      {action === 'delete' && (
        <DeleteButton
          standalone={{ onClose: close, restoreFocus }}
          label={t('projects.delete')}
          description={t('projects.deleteDescription', project.name)}
          done={t('projects.deletedNotice')}
          undo={() => ({
            label: t('executionDialog.undo'),
            run: async () => {
              await cache.save(await api.restoreProject(project.id));
            },
          })}
          onDelete={() => api.deleteProject(project.id)}
          onDeleted={() => {
            void navigate(
              { pathname: projectsPath(workspaceScope), search: archived ? '?archived=1' : '' },
              { replace: true },
            );
            void cache.remove(project.id);
          }}
        />
      )}
    </>
  );
}
