/** 作者在弹框内调整参数的展示和默认值，保存时才提交。 */
import { t } from '../../app/i18n.ts';
import { useId, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { DragDropProvider, useDroppable } from '@dnd-kit/react';
import { useSortable } from '@dnd-kit/react/sortable';
import { move } from '@dnd-kit/helpers';
import {
  ArrowDownIcon,
  ArrowUpIcon,
  ChevronDownIcon,
  DragHandleDots2Icon,
} from '@radix-ui/react-icons';
import {
  Button,
  Collapsible,
  Dialog,
  DialogClose,
  DialogContent,
  Field,
  IconButton,
  Input,
  Select,
} from '@comfyshop/ui';
import type { WorkflowParameterDisplay } from '@comfyshop/api-client';
import { DialogActions } from '../../components/dialog-actions';
import { useDialogFocus } from '../../components/use-dialog-focus';
import { ParameterValueField } from './parameter-value-field';
import { canHideParameter, parameterSections } from './parameter-layout';
import type { ParameterGroups, ParameterRow, ParameterSection } from './parameter-layout';

const allParameterTypes = ['parameter', 'asset'];
const acceptedTypes = (section: ParameterSection) =>
  section === 'hidden' ? 'parameter' : allParameterTypes;

const parameterTypeLabels: Record<ParameterRow['kind'], string> = {
  string: t('parameterEditor.text'),
  integer: t('parameterEditor.integer'),
  number: t('parameterEditor.decimal'),
  boolean: t('parameterEditor.boolean'),
  choice: t('parameterEditor.options'),
  image: t('parameterEditor.image'),
  video: t('mediaCards.video'),
  audio: t('mediaCards.audio'),
  '3d': t('workflowCategories.dModels'),
};

const controlLabels: Record<NonNullable<ParameterRow['control']>, string> = {
  text: t('parameterEditor.singleLineInput'),
  textarea: t('parameterEditor.multilineInput'),
  slider: t('parameterEditor.slider'),
  checkbox: t('parameterEditor.checkbox'),
  radio: t('parameterEditor.radioButtons'),
};

type EditorProps = {
  groups: ParameterGroups;
  onSave: (layout: WorkflowParameterDisplay[]) => Promise<void>;
};

export default function ParameterEditor({
  groups,
  onSave,
  disabled,
}: EditorProps & { disabled: boolean }) {
  const [open, setOpen] = useState(false);
  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Trigger asChild>
        <Button size="small" disabled={disabled}>
          {t('parameterEditor.editParameters')}
        </Button>
      </Dialog.Trigger>
      {open && (
        <ParameterEditorContent groups={groups} onSave={onSave} onSaved={() => setOpen(false)} />
      )}
    </Dialog.Root>
  );
}

function ParameterEditorContent({
  groups: initialGroups,
  onSave,
  onSaved,
}: EditorProps & { onSaved: () => void }) {
  const [initial] = useState(initialGroups);
  const [groups, setGroups] = useState(initial);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const beforeDrag = useRef<ParameterGroups | null>(null);
  const editorId = useId();
  const { titleRef, focusProps } = useDialogFocus();

  async function save() {
    if (saving || beforeDrag.current || groups === initial) return;
    setSaving(true);
    setError('');
    try {
      await onSave(
        parameterSections.flatMap(({ value: section }) =>
          groups[section].map((row) => ({
            fieldId: row.id,
            section,
            displayName: row.displayName?.trim() || null,
            help: row.help?.trim() || null,
            control: row.control ?? null,
            defaultValue: row.defaultValue ?? null,
          })),
        ),
      );
      onSaved();
    } catch (error) {
      setError(error instanceof Error ? error.message : t('parameterEditor.couldNotSave'));
    } finally {
      setSaving(false);
    }
  }

  function relocate(from: ParameterSection, index: number, to: ParameterSection, position: number) {
    const id = groups[from][index].id;
    setGroups((current) => {
      const source = [...current[from]];
      const [row] = source.splice(index, 1);
      const destination = from === to ? source : [...current[to]];
      destination.splice(position, 0, row);
      return { ...current, [from]: source, [to]: destination };
    });
    // 跨区后该行会重新挂载，将焦点交还给它的编辑按钮。
    requestAnimationFrame(() => document.getElementById(`${editorId}-${id}`)?.focus());
  }

  return (
    <DialogContent
      size="compact"
      className="parameter-dialog"
      {...focusProps}
      onEscapeKeyDown={(event) => {
        if (saving || beforeDrag.current) event.preventDefault();
      }}
      onInteractOutside={(event) => {
        if (saving || beforeDrag.current) event.preventDefault();
      }}
    >
      <div className="compact-dialog-heading">
        <Dialog.Title ref={titleRef} tabIndex={-1}>
          {t('parameterEditor.editParameters')}
        </Dialog.Title>
        <DialogClose label={t('common.close')} disabled={saving} />
      </div>
      <form
        className="parameter-editor"
        noValidate
        onSubmit={(event) => {
          event.preventDefault();
          void save();
        }}
      >
        <DragDropProvider
          onDragStart={() => {
            beforeDrag.current = groups;
          }}
          onDragOver={(event) => setGroups((current) => move(current, event))}
          onDragEnd={(event) => {
            if ((event.canceled || !event.operation.target) && beforeDrag.current)
              setGroups(beforeDrag.current);
            beforeDrag.current = null;
          }}
        >
          <div className="parameter-groups">
            {parameterSections.map(({ value: section, label }) => (
              <ParameterGroup key={section} section={section} label={label} disabled={saving}>
                {groups[section].map((row, index, rows) => (
                  <SortableParameter
                    key={row.id}
                    row={row}
                    section={section}
                    index={index}
                    count={rows.length}
                    triggerId={`${editorId}-${row.id}`}
                    disabled={saving}
                    onEdit={(patch) =>
                      setGroups((current) => ({
                        ...current,
                        [section]: current[section].map((item) =>
                          item.id === row.id ? { ...item, ...patch } : item,
                        ),
                      }))
                    }
                    onMove={(targetSection, position) =>
                      relocate(
                        section,
                        index,
                        targetSection,
                        position ?? groups[targetSection].length,
                      )
                    }
                  />
                ))}
              </ParameterGroup>
            ))}
          </div>
        </DragDropProvider>
        <DialogActions busy={saving} error={error}>
          <Button type="submit" variant="primary" disabled={saving || groups === initial}>
            {saving ? t('avatarCropDialog.saving') : t('machinesPage.save')}
          </Button>
        </DialogActions>
      </form>
    </DialogContent>
  );
}

function ParameterGroup({
  section,
  label,
  disabled,
  children,
}: {
  section: ParameterSection;
  label: string;
  disabled: boolean;
  children: ReactNode;
}) {
  const { ref, isDropTarget } = useDroppable({
    id: section,
    accept: acceptedTypes(section),
    // 行和区域同时命中时优先按行定位。空区域和列表末尾也可以放入参数。
    collisionPriority: 1,
    disabled,
  });
  return (
    <section
      ref={ref}
      className="parameter-group"
      aria-label={label}
      data-drop-target={isDropTarget}
    >
      <h3>{label}</h3>
      <ul className="parameter-list">{children}</ul>
    </section>
  );
}

function SortableParameter({
  row,
  section,
  index,
  count,
  triggerId,
  disabled,
  onEdit,
  onMove,
}: {
  row: ParameterRow;
  section: ParameterSection;
  index: number;
  count: number;
  triggerId: string;
  disabled: boolean;
  onEdit: (patch: Pick<ParameterRow, 'displayName' | 'help' | 'control' | 'defaultValue'>) => void;
  onMove: (section: ParameterSection, position?: number) => void;
}) {
  const canHide = canHideParameter(row);
  const { ref, handleRef, isDragging } = useSortable({
    id: row.id,
    index,
    group: section,
    type: canHide ? 'parameter' : 'asset',
    accept: acceptedTypes(section),
    disabled,
  });
  const inputId = useId();
  const label = row.displayName?.trim() || row.label;
  const controlOptions = row.controls?.options ?? [];
  return (
    <li ref={ref} className="parameter-row" data-dragging={isDragging}>
      <Collapsible.Root>
        <div className="parameter-row-heading">
          <IconButton
            ref={handleRef}
            label={t('parameterEditor.drag', label)}
            className="parameter-drag-handle"
            disabled={disabled}
          >
            <DragHandleDots2Icon />
          </IconButton>
          <Collapsible.Trigger asChild>
            <Button
              id={triggerId}
              variant="ghost"
              size="small"
              className="parameter-row-trigger"
              disabled={disabled}
            >
              <span>
                <strong>{label}</strong>
                <small>
                  {[parameterTypeLabels[row.kind], row.nodeTitle, row.inputName, row.nodeId]
                    .filter(Boolean)
                    .join(' · ')}
                </small>
              </span>
              <ChevronDownIcon />
            </Button>
          </Collapsible.Trigger>
        </div>
        <Collapsible.Content className="ui-collapsible parameter-row-fields">
          <Field label={t('parameterEditor.displayName')} htmlFor={inputId}>
            <Input
              id={inputId}
              value={row.displayName ?? ''}
              placeholder={row.label}
              maxLength={160}
              disabled={disabled}
              onChange={(event) => onEdit({ displayName: event.target.value })}
            />
          </Field>
          <Field label={t('parameterEditor.helpText')} htmlFor={`${inputId}-help`}>
            <Input
              id={`${inputId}-help`}
              value={row.help ?? ''}
              placeholder={t('parameterEditor.optionalShownViaTheHelpIcon')}
              maxLength={500}
              disabled={disabled}
              onChange={(event) => onEdit({ help: event.target.value })}
            />
          </Field>
          {(controlOptions.length > 0 || row.control) && (
            <Field label={t('parameterEditor.control')} htmlFor={`${inputId}-control`}>
              <Select
                id={`${inputId}-control`}
                label={t('parameterEditor.control')}
                value={row.control ?? 'auto'}
                disabled={disabled}
                options={[
                  { value: 'auto', label: t('parameterEditor.auto') },
                  ...controlOptions.map((value) => ({ value, label: controlLabels[value] })),
                  ...(row.control && !controlOptions.includes(row.control)
                    ? [
                        {
                          value: row.control,
                          label: t(
                            'parameterEditor.unavailableOnThisWorkMachine',
                            controlLabels[row.control],
                          ),
                          disabled: true,
                        },
                      ]
                    : []),
                ]}
                onValueChange={(next) =>
                  onEdit({ control: controlOptions.find((value) => value === next) ?? null })
                }
              />
            </Field>
          )}
          {row.originalDefault !== undefined && (
            <>
              <ParameterValueField
                id={`${inputId}-default`}
                field={{ ...row, label: t('parameterEditor.defaultValue'), primary: true }}
                value={row.defaultValue ?? row.originalDefault}
                disabled={disabled}
                onChange={(value) => {
                  if (value === null || typeof value !== 'object') onEdit({ defaultValue: value });
                }}
              />
              {row.defaultValue != null && (
                <Button
                  size="small"
                  variant="ghost"
                  disabled={disabled}
                  onClick={() => onEdit({ defaultValue: null })}
                >
                  {t('parameterEditor.restoreWorkflowDefault')}
                </Button>
              )}
            </>
          )}
          <div className="parameter-row-actions">
            <Select
              label={t('parameterEditor.move', label)}
              value={section}
              disabled={disabled}
              options={parameterSections.map((option) => ({
                ...option,
                disabled: option.value === 'hidden' && !canHide,
              }))}
              onValueChange={(next) => {
                const target = parameterSections.find(({ value }) => value === next);
                if (target && target.value !== section) onMove(target.value);
              }}
            />
            <IconButton
              label={t('parameterEditor.moveUp', label)}
              disabled={disabled || index === 0}
              onClick={() => onMove(section, index - 1)}
            >
              <ArrowUpIcon />
            </IconButton>
            <IconButton
              label={t('parameterEditor.moveDown', label)}
              disabled={disabled || index === count - 1}
              onClick={() => onMove(section, index + 1)}
            >
              <ArrowDownIcon />
            </IconButton>
          </div>
        </Collapsible.Content>
      </Collapsible.Root>
    </li>
  );
}
