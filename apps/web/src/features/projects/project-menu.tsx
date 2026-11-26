import { useState } from 'react';
import { useNavigate } from 'react-router';
import { HamburgerMenuIcon } from '@radix-ui/react-icons';
import type { Project } from '@comfyshop/api-client';
import { DropdownMenu, IconButton } from '@comfyshop/ui';
import { t } from '../../app/i18n';
import { useWorkspace } from '../../app/use-workspace';
import { projectsPath } from '../../app/workspace-scope';
import { ProjectOptionsMenu, useProjectOptions } from './project-options-menu';

export function ProjectMenu({ project, tab }: { project: Project; tab: string }) {
  const [open, setOpen] = useState(false);
  const { workspaceScope } = useWorkspace();
  const navigate = useNavigate();
  const options = useProjectOptions(open, project.archivedAt !== null);
  const label = t('projects.switch');

  return (
    <DropdownMenu.Root onOpenChange={setOpen}>
      <DropdownMenu.Trigger asChild>
        <IconButton label={label} size="normal">
          <HamburgerMenuIcon aria-hidden="true" />
        </IconButton>
      </DropdownMenu.Trigger>
      <ProjectOptionsMenu
        {...options}
        label={label}
        pinned={project}
        value={project.id}
        onValueChange={(id) => {
          if (id === project.id) return;
          void navigate({
            pathname: projectsPath(workspaceScope, id),
            search: tab === 'results' ? '' : new URLSearchParams({ tab }).toString(),
          });
        }}
      />
    </DropdownMenu.Root>
  );
}
