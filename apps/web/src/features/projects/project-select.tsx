import { useId, useRef, useState } from 'react';
import { ChevronDownIcon } from '@radix-ui/react-icons';
import { DropdownMenu, Field, SelectTrigger } from '@comfyshop/ui';
import { t } from '../../app/i18n';
import { ProjectFormDialog } from './project-form-dialog';
import { ProjectOptionsMenu, useProjectOptions } from './project-options-menu';
import { useProject } from './project-queries';

export function ProjectSelect({
  value,
  onChange,
  disabled,
}: {
  value: string | null;
  onChange: (id: string | null) => void;
  disabled?: boolean;
}) {
  const id = useId();
  const trigger = useRef<HTMLButtonElement>(null);
  const createRequested = useRef(false);
  const [creating, setCreating] = useState(false);
  const [open, setOpen] = useState(false);
  const options = useProjectOptions(open);
  const listed = options.projects.find(({ id }) => id === value);
  const selectedOutsidePage = !!value && !listed;
  const selected = useProject(value ?? undefined, selectedOutsidePage);
  const fieldLabel = t('projects.project');
  const project = listed ?? selected.data;
  const name =
    project?.archivedAt != null ? t('projects.archivedName', project.name) : project?.name;
  const label = value
    ? (name ?? t(selected.error ? 'projects.unavailable' : 'common.loading'))
    : t('projects.none');
  return (
    <>
      <Field label={fieldLabel} htmlFor={id}>
        <DropdownMenu.Root onOpenChange={setOpen}>
          <DropdownMenu.Trigger asChild>
            <SelectTrigger
              ref={trigger}
              id={id}
              aria-label={fieldLabel}
              aria-describedby={`${id}-value`}
              disabled={disabled}
            >
              <span id={`${id}-value`}>{label}</span>
              <ChevronDownIcon aria-hidden="true" />
            </SelectTrigger>
          </DropdownMenu.Trigger>
          <ProjectOptionsMenu
            {...options}
            label={fieldLabel}
            allowNone
            pinned={selectedOutsidePage && project ? { id: project.id, name: label } : undefined}
            value={value ?? 'none'}
            onValueChange={(next) => onChange(next === 'none' ? null : next)}
            onCloseAutoFocus={(event) => {
              if (!createRequested.current) return;
              createRequested.current = false;
              event.preventDefault();
              setCreating(true);
            }}
          >
            <DropdownMenu.Item
              className="ui-menu-item"
              onSelect={() => {
                createRequested.current = true;
              }}
            >
              {t('projects.create')}
            </DropdownMenu.Item>
          </ProjectOptionsMenu>
        </DropdownMenu.Root>
      </Field>
      {creating && (
        <ProjectFormDialog
          onClose={() => setCreating(false)}
          onSaved={(project) => {
            onChange(project.id);
            setCreating(false);
          }}
          restoreFocus={() => trigger.current?.focus({ preventScroll: true })}
        />
      )}
    </>
  );
}
