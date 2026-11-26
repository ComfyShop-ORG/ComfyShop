import { t } from '../../app/i18n.ts';
import { useId, useRef, useState } from 'react';
import type { ComponentProps, ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  ChevronDownIcon,
  ExclamationTriangleIcon,
  MixerHorizontalIcon,
} from '@radix-ui/react-icons';
import {
  Button,
  Checkbox,
  Collapsible,
  Dialog,
  DialogClose,
  DialogContent,
  Disclosure,
  Field,
  SearchField,
  Select,
  Switch,
} from '@comfyshop/ui';
import type { InputValue, WorkflowForm } from '@comfyshop/api-client';
import { useDialogFocus } from '../../components/use-dialog-focus';
import { InputField } from './input-field';
import { applyInputPatch } from './form-values';
import type { InputPatch } from './form-values';
import { RatioSizePreview } from './output-size';
import { placementEditorFor } from './placement-fields';
import { cropEditorFor } from './crop-box';
import { outpaintEditorFor } from './outpaint-fields';
import { maskEditorFor } from './mask-fields';
import { isAssetInput } from './parameter-layout';
import type { ParameterRow } from './parameter-layout';
import { runParameterState, sameInputValue } from './run-parameter-state';
import { useRunParameters } from './run-assets';
import type { workflowFormQuery } from './workflow-form-query';

const sections = [
  { id: 'assets', title: t('runParameterDialog.assets') },
  { id: 'prompts', title: t('runParameterDialog.prompt') },
  { id: 'sizes', title: t('runParameterDialog.outputSettings') },
  { id: 'common', title: t('runParameterDialog.commonParameters') },
  { id: 'advanced', title: t('runForm.advancedParameters') },
  { id: 'hidden', title: t('runParameterDialog.hiddenParameters') },
] as const;

type Section = (typeof sections)[number]['id'];
type Values = Record<string, InputValue>;
type RatioSize = Extract<WorkflowForm['outputSizes'][number], { kind: 'ratio' }>;
export type RunParameterDialogMode = 'all' | 'issues' | 'hidden-changed' | null;
type PanelProps = {
  mode: RunParameterDialogMode;
  platformManaged: boolean;
  issueCount: number;
  disabled: boolean;
  initialMachineId: string;
  machines: ComponentProps<typeof Select>['options'];
  initialDraft: Values | null;
  initialHiddenDraft: Values;
  readForm: (machineId: string) => ReturnType<typeof workflowFormQuery>;
  onApply: (machineId: string, patch: InputPatch, hiddenPatch: InputPatch) => void;
  onOpenChange: (mode: RunParameterDialogMode) => void;
};

function readonlyValue(row: ParameterRow, value: InputValue) {
  if (value === null) return t('runParameterDialog.empty');
  if (typeof value === 'boolean') return value ? t('recordedInputs.on') : t('recordedInputs.off');
  if (typeof value === 'object') return value.assetId;
  const text = String(value);
  const labels = row.presentation?.choiceLabels;
  return labels && Object.hasOwn(labels, text) ? labels[text] : text;
}

export default function RunParameterDialog({
  mode,
  issueCount,
  disabled,
  onOpenChange,
  ...props
}: PanelProps) {
  return (
    <Dialog.Root open={mode !== null} onOpenChange={(open) => onOpenChange(open ? 'all' : null)}>
      <Dialog.Trigger asChild>
        <Button size="large" disabled={disabled}>
          <MixerHorizontalIcon />
          {t('runParameterDialog.runParameters')}
          {issueCount > 0 && (
            <span className="run-parameter-issue-count">
              {t('runParameterDialog.issues', issueCount)}
            </span>
          )}
        </Button>
      </Dialog.Trigger>
      {mode && (
        <RunParameterContent
          {...props}
          mode={mode}
          onApply={(machineId, patch, hiddenPatch) => {
            props.onApply(machineId, patch, hiddenPatch);
            onOpenChange(null);
          }}
        />
      )}
    </Dialog.Root>
  );
}

function RunParameterContent({
  initialMachineId,
  platformManaged,
  machines,
  initialDraft,
  initialHiddenDraft,
  readForm,
  onApply,
  mode,
}: Pick<
  PanelProps,
  | 'platformManaged'
  | 'initialMachineId'
  | 'machines'
  | 'initialDraft'
  | 'initialHiddenDraft'
  | 'readForm'
  | 'onApply'
> & {
  mode: NonNullable<RunParameterDialogMode>;
}) {
  const id = useId();
  const { titleRef, focusProps } = useDialogFocus();
  const editHiddenRef = useRef<HTMLButtonElement>(null);
  const [machineId, setMachineId] = useState(initialMachineId);
  const [patch, setPatch] = useState<InputPatch>({});
  const [hiddenPatch, setHiddenPatch] = useState<InputPatch>({});
  const [editHidden, setEditHidden] = useState(false);
  const [collapsed, setCollapsed] = useState<ReadonlySet<Section>>(() => new Set());
  const [query, setQuery] = useState('');
  const [onlyChanged, setOnlyChanged] = useState(mode === 'hidden-changed');
  const [onlyIssues, setOnlyIssues] = useState(mode === 'issues');
  const [focusField, setFocusField] = useState<string | null>(null);
  const [uploading, setUploading] = useState<ReadonlySet<string>>(() => new Set());
  const machine = machines.find(({ value }) => value === machineId);
  const machineAvailable = platformManaged || (!!machine && !machine.disabled);
  const canReadForm = platformManaged || !!machine;
  const schema = useQuery({ ...readForm(machineId), enabled: canReadForm, staleTime: 0 });
  const form = canReadForm && !schema.isError ? schema.data : undefined;
  const hiddenValues = applyInputPatch(initialHiddenDraft, hiddenPatch);
  const { groups, rows, values, locked, issues, changedHidden, sharedAssets, visibleRows } =
    useRunParameters(form, applyInputPatch(initialDraft, patch), { hiddenValues, editHidden });
  const hasHiddenChanges = changedHidden.size > 0;
  const hiddenNote = editHidden
    ? t('runParameterDialog.changesMayCauseGenerationErrorsLow')
    : hasHiddenChanges
      ? t('runParameterDialog.changesRetained')
      : t('runParameterDialog.theseParametersAreReadOnlyBy');
  const initial = runParameterState(form, initialDraft);
  const terms = query.normalize('NFKC').toLowerCase().trim().split(/\s+/).filter(Boolean);
  const filtering = terms.length > 0 || onlyChanged || onlyIssues;
  const hidden = new Set(groups.hidden.map((row) => row.id));
  const advanced = new Set(groups.advanced.map((row) => row.id));
  const prompts = new Set<string>();
  const dimensions = new Set<string>();
  const ratioSizes = new Map<string, RatioSize>();
  for (const size of form?.outputSizes ?? []) {
    if (size.kind === 'automatic') {
      dimensions.add(size.widthFieldId);
      dimensions.add(size.heightFieldId);
    } else {
      dimensions.add(size.ratioFieldId);
      dimensions.add(size.megapixelsFieldId);
      if (size.promptFieldId) prompts.add(size.promptFieldId);
      ratioSizes.set(size.megapixelsFieldId, size);
    }
  }
  for (const timeline of form?.referenceTimelines ?? []) dimensions.add(timeline.durationFieldId);

  const changed = new Set(
    rows.filter((row) => !sameInputValue(values[row.id], row.default)).map(({ id }) => id),
  );
  const updates: InputPatch = {};
  const hiddenUpdates: InputPatch = {};
  for (const row of rows) {
    const fieldId = row.id;
    if (Object.hasOwn(patch, fieldId)) {
      const value = patch[fieldId];
      if (
        value === undefined
          ? Object.hasOwn(initialDraft ?? {}, fieldId)
          : !initial.locked.has(fieldId) && !sameInputValue(value, initial.values[fieldId])
      ) {
        updates[fieldId] = value;
      }
    }
    if (
      hidden.has(fieldId) &&
      Object.hasOwn(hiddenPatch, fieldId) &&
      !sameInputValue(hiddenPatch[fieldId], initialHiddenDraft[fieldId])
    ) {
      hiddenUpdates[fieldId] = hiddenPatch[fieldId];
    }
  }
  const matches = new Set(
    rows
      .filter((row) => {
        if ((onlyChanged && !changed.has(row.id)) || (onlyIssues && !issues.has(row.id)))
          return false;
        if (!terms.length) return true;
        const text = [row.displayName, row.label, row.inputName, row.nodeTitle, row.help]
          .filter(Boolean)
          .join(' ')
          .normalize('NFKC')
          .toLowerCase();
        return terms.every((term) => text.includes(term));
      })
      .map(({ id }) => id),
  );

  const grouped: Record<Section, ParameterRow[]> = {
    assets: [],
    prompts: [],
    sizes: [],
    common: [],
    advanced: [],
    hidden: [],
  };
  for (const row of rows) {
    if (hidden.has(row.id)) grouped.hidden.push(row);
    else if (isAssetInput(row.kind)) grouped.assets.push(row);
    else if (dimensions.has(row.id)) grouped.sizes.push(row);
    else if (
      prompts.has(row.id) ||
      (row.kind === 'string' &&
        (row.primary || (row.control === 'textarea' && !advanced.has(row.id))))
    )
      grouped.prompts.push(row);
    else if (advanced.has(row.id)) grouped.advanced.push(row);
    else grouped.common.push(row);
  }

  function changeSection(section: Section, open: boolean) {
    setCollapsed((prior) => {
      const next = new Set(prior);
      if (open) next.delete(section);
      else next.add(section);
      return next;
    });
  }
  function changeInputs(changes: InputPatch) {
    setPatch((prior) => ({ ...prior, ...changes }));
  }

  function changeValue(row: ParameterRow, value: InputValue) {
    if (!hidden.has(row.id) || (!editHidden && !Object.hasOwn(hiddenValues, row.id))) {
      changeInputs({ [row.id]: value });
      return;
    }
    const restored = sameInputValue(value, row.default);
    setHiddenPatch((prior) => ({ ...prior, [row.id]: restored ? undefined : value }));
    if (restored) changeInputs({ [row.id]: undefined });
  }
  function resetHidden() {
    const reset = Object.fromEntries(groups.hidden.map(({ id }) => [id, undefined]));
    changeInputs(reset);
    setHiddenPatch((prior) => ({ ...prior, ...reset }));
    setFocusField(null);
    (onlyChanged || onlyIssues ? titleRef : editHiddenRef).current?.focus({ preventScroll: true });
  }
  function uploadState(fieldId: string, busy: boolean) {
    setUploading((prior) => {
      const next = new Set(prior);
      if (busy) next.add(fieldId);
      else next.delete(fieldId);
      return next;
    });
  }
  const canApply =
    !!form &&
    (machineAvailable || machineId === initialMachineId) &&
    !schema.isFetching &&
    uploading.size === 0 &&
    (machineId !== initialMachineId ||
      Object.keys(updates).length > 0 ||
      Object.keys(hiddenUpdates).length > 0);
  const visibleSections =
    mode === 'hidden-changed'
      ? [sections[sections.length - 1], ...sections.slice(0, -1)]
      : sections;
  return (
    <DialogContent className="run-parameter-dialog" {...focusProps}>
      <div className="compact-dialog-heading">
        <Dialog.Title ref={titleRef} tabIndex={-1}>
          {t('runParameterDialog.runParameters')}
        </Dialog.Title>
        <DialogClose label={t('common.close')} />
      </div>
      <div className="run-parameter-toolbar">
        <Field label={t('runParameterDialog.searchParameters')} htmlFor={`${id}-search`}>
          <SearchField
            id={`${id}-search`}
            value={query}
            placeholder={t('runParameterDialog.labelFieldNameOrHelpText')}
            clearLabel={t('app.clearSearch')}
            onValueChange={(value) => {
              setQuery(value);
              setFocusField(null);
            }}
          />
        </Field>
        {!platformManaged && (
          <Field label={t('runForm.workMachineForThisRun')} htmlFor={`${id}-machine`}>
            <Select
              id={`${id}-machine`}
              label={t('runForm.workMachineForThisRun')}
              value={machineAvailable ? machineId : ''}
              placeholder={t('runForm.selectAnOnlineWorkMachine')}
              options={machines}
              disabled={uploading.size > 0}
              onValueChange={(next) => {
                setMachineId(next);
                setFocusField(null);
              }}
            />
          </Field>
        )}
        <div className="run-parameter-filters">
          <label htmlFor={`${id}-changed`}>
            <Checkbox
              id={`${id}-changed`}
              checked={onlyChanged}
              onCheckedChange={(checked) => {
                setOnlyChanged(checked === true);
                setFocusField(null);
              }}
            />
            {t('runParameterDialog.modifiedOnly')}
          </label>
          <label htmlFor={`${id}-issues`}>
            <Checkbox
              id={`${id}-issues`}
              checked={onlyIssues}
              onCheckedChange={(checked) => {
                setOnlyIssues(checked === true);
                setFocusField(null);
              }}
            />
            {t('runParameterDialog.issuesOnly')}
          </label>
          {form && (
            <span role="status">
              {matches.size}
              {t('runParameterDialog.parameters')}
              {issues.size > 0 ? t('runParameterDialog.issues2', issues.size) : ''}
            </span>
          )}
        </div>
      </div>
      <div className="run-parameter-results">
        {!machineAvailable && (
          <p className="form-hint" role="status">
            {t('runParameterDialog.selectAnOnlineWorkMachine')}
          </p>
        )}
        {!form && schema.error && (
          <div className="form-error" role="alert">
            {schema.error.message}
            {canReadForm && (
              <Button size="small" variant="ghost" onClick={() => void schema.refetch()}>
                {t('runForm.refresh')}
              </Button>
            )}
          </div>
        )}
        {!form && schema.isFetching && (
          <p className="form-hint" role="status">
            {t('recordedInputs.loadingParameters')}
          </p>
        )}
        {form?.issues.map((issue) => (
          <p className="form-error" role="alert" key={issue}>
            {issue}
          </p>
        ))}
        {form && matches.size === 0 && !focusField && (
          <p className="form-hint">{t('runParameterDialog.noParametersMatch')}</p>
        )}
        {visibleSections.map(({ id: section, title }) => {
          const shown = grouped[section].filter(
            (row) => matches.has(row.id) || uploading.has(row.id) || focusField === row.id,
          );
          if (!shown.length) return null;
          return (
            <RunParameterSection
              key={section}
              title={title}
              expandable={section === 'advanced' || section === 'hidden'}
              forceOpen={filtering}
              expanded={!collapsed.has(section)}
              onExpandedChange={(open) => changeSection(section, open)}
              actions={
                section === 'hidden' && (
                  <label className="run-parameter-hidden-switch" htmlFor={`${id}-edit-hidden`}>
                    <Switch
                      ref={editHiddenRef}
                      id={`${id}-edit-hidden`}
                      checked={editHidden}
                      aria-describedby={`${id}-hidden-note`}
                      onCheckedChange={(checked) => {
                        setEditHidden(checked);
                        if (checked) changeSection('hidden', true);
                      }}
                    />
                    {t('runParameterDialog.allowEditing')}
                  </label>
                )
              }
              notice={
                section === 'hidden' && (
                  <div className="run-parameter-hidden-meta">
                    <p id={`${id}-hidden-note`} className="run-parameter-hidden-note" role="status">
                      {editHidden && <ExclamationTriangleIcon aria-hidden="true" />}
                      <span>
                        {hiddenNote}
                        {(editHidden || hasHiddenChanges) && (
                          <span className="run-parameter-hidden-note-scope">
                            {editHidden
                              ? t('runParameterDialog.appliesToThisRun')
                              : t('runParameterDialog.applyTheChangesToUseThem')}
                          </span>
                        )}
                      </span>
                    </p>
                    {hasHiddenChanges && (
                      <Button size="small" variant="ghost" onClick={resetHidden}>
                        {t('runParameterDialog.restoreInitialValues')}
                      </Button>
                    )}
                  </div>
                )
              }
            >
              {shown.map((row) => {
                const value = values[row.id];
                const issue = issues.get(row.id)?.message;
                const size = ratioSizes.get(row.id);
                return (
                  <li
                    key={row.id}
                    className="run-parameter-row"
                    hidden={!matches.has(row.id) && focusField !== row.id}
                    onFocusCapture={() => setFocusField(row.id)}
                    onBlurCapture={(event) => {
                      if (event.relatedTarget && !event.currentTarget.contains(event.relatedTarget))
                        setFocusField(null);
                    }}
                  >
                    {locked.has(row.id) ? (
                      <Field
                        label={row.displayName || row.label}
                        detail={t('runParameterDialog.readOnly')}
                        help={row.help ?? undefined}
                        helpLabel={t('common.fieldHelp', row.label)}
                      >
                        <Disclosure
                          className="run-parameter-readonly"
                          label={t('runParameterDialog.currentValue')}
                          defaultOpen
                        >
                          <pre>{readonlyValue(row, value)}</pre>
                        </Disclosure>
                        {issue && (
                          <p className="form-error" role="alert">
                            {issue}
                          </p>
                        )}
                      </Field>
                    ) : (
                      <InputField
                        field={{ ...row, primary: true }}
                        id={`${id}-input-${row.id}`}
                        value={value}
                        issue={issue}
                        linkedAspect={prompts.has(row.id)}
                        sharedAsset={
                          value && typeof value === 'object'
                            ? sharedAssets.get(value.assetId)
                            : undefined
                        }
                        crops={form?.imageCrops?.[row.id]}
                        crop={cropEditorFor(row, visibleRows, values, changeInputs)}
                        outpaint={outpaintEditorFor(row, visibleRows, values, changeInputs)}
                        placement={placementEditorFor(row, visibleRows, values, sharedAssets, changeInputs)}
                        mask={maskEditorFor(row, visibleRows, values, sharedAssets, changeInputs)}
                        maxAssetBytes={form?.maxAssetBytes}
                        onChange={(value) => changeValue(row, value)}
                        onBusy={uploadState}
                      />
                    )}
                    {size && (
                      <RatioSizePreview
                        ratio={values[size.ratioFieldId]}
                        megapixels={value}
                        multiple={values[size.multipleFieldId]}
                        roundTo={size.roundTo}
                        latentMultiple={size.latentMultiple}
                        modelMultiple={size.modelMultiple}
                      />
                    )}
                    {changed.has(row.id) && (
                      <span className="form-hint">{t('runParameterDialog.modified')}</span>
                    )}
                  </li>
                );
              })}
            </RunParameterSection>
          );
        })}
      </div>
      <div className="compact-dialog-footer">
        <Dialog.Close asChild>
          <Button>{t('deleteButton.cancel')}</Button>
        </Dialog.Close>
        <Button
          variant="primary"
          disabled={!canApply}
          onClick={() => onApply(machineId, updates, hiddenUpdates)}
        >
          {t('runParameterDialog.apply')}
        </Button>
      </div>
    </DialogContent>
  );
}

function RunParameterSection({
  title,
  expandable,
  forceOpen,
  expanded,
  onExpandedChange,
  actions,
  notice,
  children,
}: {
  title: string;
  expandable: boolean;
  forceOpen: boolean;
  expanded: boolean;
  onExpandedChange: (expanded: boolean) => void;
  actions?: ReactNode;
  notice?: ReactNode;
  children: ReactNode;
}) {
  return expandable ? (
    <Collapsible.Root
      open={forceOpen || expanded}
      onOpenChange={onExpandedChange}
      className="run-parameter-section"
    >
      <div className="run-parameter-section-heading">
        <h3>
          {forceOpen ? (
            <span>{title}</span>
          ) : (
            <Collapsible.Trigger asChild>
              <Button variant="ghost" className="run-parameter-section-trigger">
                {title}
                <ChevronDownIcon />
              </Button>
            </Collapsible.Trigger>
          )}
        </h3>
        {actions}
      </div>
      {notice}
      <Collapsible.Content>
        <ul className="run-parameter-list">{children}</ul>
      </Collapsible.Content>
    </Collapsible.Root>
  ) : (
    <section className="run-parameter-section" aria-label={title}>
      <h3>{title}</h3>
      <ul className="run-parameter-list">{children}</ul>
    </section>
  );
}
