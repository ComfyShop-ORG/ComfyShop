import { lazy, Suspense, useMemo, useState } from 'react';
import {
  ArrowLeftIcon,
  ArrowRightIcon,
  ChevronDownIcon,
  CircleIcon,
  EraserIcon,
  Pencil1Icon,
  TransparencyGridIcon,
  TrashIcon,
} from '@radix-ui/react-icons';
import { useQuery } from '@tanstack/react-query';
import {
  Button,
  Dialog,
  DialogContent,
  DropdownMenu,
  FieldHelp,
  IconButton,
  Popover,
  RangeSlider,
  ToggleGroup,
} from '@comfyshop/ui';
import type { Asset } from '@comfyshop/api-client';
import { t } from '../../app/i18n';
import { useWorkspace } from '../../app/use-workspace';
import { DialogActions } from '../../components/dialog-actions';
import { useDialogFocus } from '../../components/use-dialog-focus';
import { assetQuery } from '../assets/asset-queries';
import { useCanvasImage } from './canvas-viewport';
import { maskFile } from './mask-bitmap';
import type { MaskChange, MaskTool } from './mask-bitmap';
import type { MaskEditor } from './mask-fields';
import { useMaskSelection } from './use-mask-selection';

const MaskCanvas = lazy(() => import('./mask-canvas'));
const portraitParts = [
  ['hair', 1],
  ['face', 3],
  ['clothes', 4],
  ['background', 0],
] as const;

type Props = {
  source: Pick<Asset, 'media'>;
  editor: Pick<MaskEditor, 'assetId' | 'sharedAsset' | 'nativeAlpha'>;
  onSave: (file: File | null) => Promise<boolean>;
};

export function MaskDialog({ source, editor, onSave, close }: Props & { close: () => void }) {
  const { api, state, workspaceScope } = useWorkspace();
  const { titleRef, focusProps } = useDialogFocus();
  const [initial] = useState(() => ({ id: editor.assetId, shared: editor.sharedAsset }));
  const maskQuery = useQuery({
    ...assetQuery(api, state.userId, initial.id, workspaceScope),
    enabled: !!initial.id && !initial.shared,
  });
  const chosenMask = initial.shared ?? maskQuery.data;
  const image = useCanvasImage(source.media.src);
  const oldMask = useCanvasImage(chosenMask?.media.src);
  const matchingMask =
    image &&
    oldMask &&
    image.naturalWidth === oldMask.naturalWidth &&
    image.naturalHeight === oldMask.naturalHeight
      ? oldMask
      : undefined;
  const loadingMask = !!initial.id && !maskQuery.isError && oldMask === undefined;
  const sourceAlpha = editor.nativeAlpha && !initial.id;
  const original = sourceAlpha ? image || undefined : matchingMask;
  const [tool, setTool] = useState<MaskTool>('paint');
  const [brush, setBrush] = useState<number>();
  const [history, setHistory] = useState<{ items: MaskChange[]; index: number }>({
    items: [],
    index: 0,
  });
  const [drawing, setDrawing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const changes = useMemo(() => history.items.slice(0, history.index), [history]);
  const shortEdge = image ? Math.min(image.naturalWidth, image.naturalHeight) : 1;
  const maxBrush = Math.max(1, Math.floor(shortEdge / 2));
  const diameter = brush ?? Math.min(maxBrush, Math.max(8, Math.round(shortEdge * 0.07)));
  const disabled = saving || loadingMask || !image;
  const loading = image === undefined || loadingMask;
  const brushLabel = t('mask.brushSize');
  const canClear = changes.at(-1) !== 'clear' && (!!original || changes.length > 0);
  const selection = useMaskSelection(image, commit);

  function commit(change: MaskChange) {
    setError('');
    setHistory(({ items, index }) => ({
      items: [...items.slice(0, index), change],
      index: index + 1,
    }));
  }

  function navigate(direction: -1 | 1) {
    selection.cancel();
    setError('');
    setHistory(({ items, index }) => ({
      items,
      index: Math.max(0, Math.min(items.length, index + direction)),
    }));
  }

  async function apply() {
    if (!image || disabled || drawing || selection.busy || !changes.length) return;
    setSaving(true);
    setError('');
    try {
      let file: File | null = null;
      if (editor.nativeAlpha || changes.at(-1) !== 'clear') {
        try {
          file = await maskFile(image, original, changes, sourceAlpha);
        } catch {
          setError(t('mask.exportFailed'));
          return;
        }
      }
      if (await onSave(file)) close();
      else setError(t('mask.saveFailed'));
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : t('mask.saveFailed'));
    } finally {
      setSaving(false);
    }
  }

  const warning =
    oldMask && image && !matchingMask
      ? t('mask.sizeMismatch')
      : initial.id && (maskQuery.isError || oldMask === null)
        ? t('mask.cannotReadMask')
        : '';
  const status = error || (selection.status && t(`mask.${selection.status}`)) || warning;
  const failed =
    !!error || selection.status === 'loadFailed' || selection.status === 'inferenceFailed';

  return (
    <DialogContent
      className="canvas-editor-dialog mask-dialog"
      {...focusProps}
      onInteractOutside={(event) => {
        if (saving) event.preventDefault();
      }}
      onEscapeKeyDown={(event) => {
        if (saving) event.preventDefault();
      }}
      onKeyDown={(event) => {
        if (drawing || disabled || !(event.ctrlKey || event.metaKey) || event.altKey) return;
        if (event.key.toLowerCase() === 'z' && !(event.target instanceof HTMLInputElement)) {
          event.preventDefault();
          navigate(event.shiftKey ? 1 : -1);
        }
      }}
    >
      <div className="canvas-editor-form">
        <div className="compact-dialog-heading canvas-editor-heading">
          <div className="canvas-editor-title">
            <Dialog.Title ref={titleRef} tabIndex={-1}>
              {t('mask.title')}
            </Dialog.Title>
            <FieldHelp label={t('common.fieldHelp', t('mask.title'))} help={t('mask.help')} />
          </div>
          <div className="canvas-editor-toolbar mask-toolbar">
            <ToggleGroup.Root
              className="mask-tools"
              type="single"
              aria-label={t('mask.tools')}
              value={tool}
              disabled={disabled || drawing}
              onValueChange={(value) => {
                if (
                  value === 'paint' ||
                  value === 'erase' ||
                  value === 'add' ||
                  value === 'subtract'
                ) {
                  selection.cancel();
                  setTool(value);
                }
              }}
            >
              <ToggleGroup.Item value="paint" asChild>
                <IconButton label={t('mask.paint')} size="large">
                  <Pencil1Icon aria-hidden="true" />
                </IconButton>
              </ToggleGroup.Item>
              <ToggleGroup.Item value="erase" asChild>
                <IconButton label={t('mask.erase')} size="large">
                  <EraserIcon aria-hidden="true" />
                </IconButton>
              </ToggleGroup.Item>
              {(['add', 'subtract'] as const).map((mode) => (
                <ToggleGroup.Item key={mode} value={mode} asChild>
                  <Button variant="ghost" size="large">
                    {t(`mask.${mode}`)}
                  </Button>
                </ToggleGroup.Item>
              ))}
            </ToggleGroup.Root>
            <DropdownMenu.Root>
              <DropdownMenu.Trigger asChild>
                <Button
                  size="large"
                  variant="ghost"
                  disabled={disabled || drawing || selection.busy}
                >
                  {t('mask.portrait')} <ChevronDownIcon aria-hidden="true" />
                </Button>
              </DropdownMenu.Trigger>
              <DropdownMenu.Portal>
                <DropdownMenu.Content
                  className="ui-menu"
                  sideOffset={4}
                  aria-label={t('mask.portrait')}
                >
                  {portraitParts.map(([part, category]) => (
                    <DropdownMenu.Item
                      key={part}
                      className="ui-menu-item"
                      onSelect={() =>
                        selection.select(
                          { kind: 'portrait', category },
                          tool === 'subtract' ? 'subtract' : 'add',
                        )
                      }
                    >
                      {t(`mask.${part}`)}
                    </DropdownMenu.Item>
                  ))}
                </DropdownMenu.Content>
              </DropdownMenu.Portal>
            </DropdownMenu.Root>
            <Popover.Root>
              <Popover.Trigger asChild>
                <Button
                  className="mask-brush-trigger"
                  size="large"
                  variant="ghost"
                  aria-label={brushLabel}
                  disabled={disabled || drawing || tool === 'add' || tool === 'subtract'}
                >
                  <CircleIcon aria-hidden="true" />
                  {t('mask.pixels', diameter)}
                </Button>
              </Popover.Trigger>
              <Popover.Portal>
                <Popover.Content
                  className="ui-menu mask-brush-menu"
                  aria-label={brushLabel}
                  side="bottom"
                  sideOffset={8}
                >
                  <RangeSlider
                    label={brushLabel}
                    min={1}
                    max={maxBrush}
                    step={1}
                    value={diameter}
                    detail={t('mask.pixels', diameter)}
                    onValueChange={setBrush}
                  />
                </Popover.Content>
              </Popover.Portal>
            </Popover.Root>
            <div className="mask-tools">
              <IconButton
                label={t('outpaint.undo')}
                size="large"
                disabled={disabled || drawing || history.index === 0}
                onClick={() => navigate(-1)}
              >
                <ArrowLeftIcon aria-hidden="true" />
              </IconButton>
              <IconButton
                label={t('outpaint.redo')}
                size="large"
                disabled={disabled || drawing || history.index === history.items.length}
                onClick={() => navigate(1)}
              >
                <ArrowRightIcon aria-hidden="true" />
              </IconButton>
              <IconButton
                label={t('mask.clear')}
                size="large"
                disabled={disabled || drawing || !canClear}
                onClick={() => {
                  selection.cancel();
                  commit('clear');
                }}
              >
                <TrashIcon aria-hidden="true" />
              </IconButton>
            </div>
          </div>
          <DialogActions busy={saving} error="">
            <Button
              variant="primary"
              disabled={disabled || drawing || selection.busy || !changes.length}
              onClick={() => void apply()}
            >
              {t(saving ? 'mask.applying' : 'runParameterDialog.apply')}
            </Button>
          </DialogActions>
        </div>
        <div className="canvas-editor-body">
          <Suspense
            fallback={
              <p className="canvas-editor-viewport" role="status">
                {t('common.loading')}
              </p>
            }
          >
            {image && !loading ? (
              <MaskCanvas
                image={image}
                original={original}
                sourceAlpha={sourceAlpha}
                changes={changes}
                diameter={diameter}
                tool={tool}
                disabled={disabled}
                selecting={selection.busy}
                onDraw={(active) => {
                  if (active) selection.cancel();
                  setDrawing(active);
                }}
                onCommit={commit}
                onSelect={(point, mode) => selection.select({ kind: 'point', point }, mode)}
              />
            ) : (
              <p className="canvas-editor-viewport" role="status">
                {t(loading ? 'common.loading' : 'outpaint.previewUnavailable')}
              </p>
            )}
          </Suspense>
          {image && !loading && (
            <div className="canvas-editor-status">
              {status && (
                <span
                  className={failed ? 'form-error' : undefined}
                  role={failed ? 'alert' : 'status'}
                >
                  {status}
                </span>
              )}
              {!status && (
                <span>{t('mask.dimensions', image.naturalWidth, image.naturalHeight)}</span>
              )}
            </div>
          )}
        </div>
      </div>
    </DialogContent>
  );
}

export function MaskAction(props: Props & { disabled: boolean }) {
  const [open, setOpen] = useState(false);
  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Trigger asChild>
        <Button size="small" variant="ghost" disabled={props.disabled}>
          <TransparencyGridIcon aria-hidden="true" />
          {t('mask.title')}
        </Button>
      </Dialog.Trigger>
      {open && <MaskDialog {...props} close={() => setOpen(false)} />}
    </Dialog.Root>
  );
}
