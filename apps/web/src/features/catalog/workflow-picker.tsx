import { useDeferredValue, useRef, useState } from 'react';
import { Button, SearchField, Select } from '@comfyshop/ui';
import { t } from '../../app/i18n';
import { PageToolbar } from '../../components/page-toolbar';
import { PickerDialog } from '../../components/picker-dialog';
import type { Workflow } from '../../domain/types';
import { WorkflowCollection } from './workflow-collection';

export type OpenWorkflow = (workflow: Workflow, source: HTMLElement) => void;

const sources = [
  { value: 'public', label: t('workflowCollection.publicWorkflows') },
  { value: 'mine', label: t('projects.workspaceWorkflows') },
] as const;

export function WorkflowChoices({
  scrollRoot,
  onSelect,
  initialScope = 'public',
  inpaintArtifactId,
}: {
  scrollRoot: HTMLDivElement;
  initialScope?: (typeof sources)[number]['value'];
  inpaintArtifactId?: string;
  onSelect: (workflow: Workflow) => void;
}) {
  const [text, setText] = useState('');
  const [scope, setScope] = useState(initialScope);
  const search = useDeferredValue(text.trim());
  return (
    <>
      <PageToolbar className="project-workflow-tools" standalone>
        <Select
          label={t('projects.workflowSource')}
          options={sources}
          value={scope}
          onValueChange={(value) => setScope(value === 'mine' ? 'mine' : 'public')}
        />
        <SearchField
          aria-label={t('app.searchWorkflows')}
          placeholder={t('app.searchWorkflows')}
          clearLabel={t('app.clearSearch')}
          maxLength={120}
          value={text}
          onValueChange={setText}
        />
      </PageToolbar>
      <WorkflowCollection
        scope={scope}
        search={search}
        scrollRoot={scrollRoot}
        inpaintArtifactId={inpaintArtifactId}
        onReset={() => setText('')}
        onSelect={onSelect}
      />
    </>
  );
}

export function WorkflowPicker({
  label,
  primary,
  disabled,
  onSelect,
}: {
  label: string;
  primary?: boolean;
  disabled?: boolean;
  onSelect: OpenWorkflow;
}) {
  const trigger = useRef<HTMLButtonElement>(null);
  const picked = useRef<Workflow | undefined>(undefined);
  return (
    <PickerDialog
      title={label}
      trigger={
        <Button ref={trigger} variant={primary ? 'primary' : 'secondary'} disabled={disabled}>
          {label}
        </Button>
      }
      onCloseAutoFocus={(event) => {
        if (!picked.current || !trigger.current) return;
        event.preventDefault();
        const workflow = picked.current;
        picked.current = undefined;
        trigger.current.focus({ preventScroll: true });
        onSelect(workflow, trigger.current);
      }}
    >
      {(scrollRoot, close) => (
        <WorkflowChoices
          scrollRoot={scrollRoot}
          onSelect={(workflow) => {
            picked.current = workflow;
            close();
          }}
        />
      )}
    </PickerDialog>
  );
}
