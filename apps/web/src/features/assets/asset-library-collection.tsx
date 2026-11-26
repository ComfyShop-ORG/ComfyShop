import { useDeferredValue, useState } from 'react';
import type { ReactNode } from 'react';
import type { Asset } from '@comfyshop/api-client';
import { SearchField, Select } from '@comfyshop/ui';
import { t } from '../../app/i18n';
import { EmptyState } from '../../components/collection-status';
import { MediaCollection } from '../../components/media-grid';
import { PageToolbar } from '../../components/page-toolbar';
import { fileSizeLabel } from '../../data/download';
import { useLibraryAssets } from './asset-queries';

const types = [
  { value: 'all', label: t('assetLibrary.allTypes') },
  { value: 'image', label: t('parameterEditor.image') },
  { value: 'video', label: t('mediaCards.video') },
  { value: 'audio', label: t('mediaCards.audio') },
  { value: '3d', label: t('mediaCards.dModel') },
] as const;
type Filter = (typeof types)[number]['value'];

export function AssetLibraryCollection({
  contentTypes,
  scrollRoot,
  action,
  error,
  projectId,
  picking,
  onOpen,
}: {
  contentTypes?: string[];
  scrollRoot?: HTMLElement;
  action?: ReactNode;
  error?: string;
  projectId?: string;
  picking?: boolean;
  onOpen: (asset: Asset, source: HTMLElement) => void;
}) {
  const [text, setText] = useState('');
  const [kind, setKind] = useState<Filter>('all');
  const search = useDeferredValue(text.trim());
  const { query, resetKey } = useLibraryAssets({
    search,
    kind: kind === 'all' ? undefined : kind,
    content_types: contentTypes,
    project_id: projectId,
  });
  const empty =
    search || kind !== 'all'
      ? t('assetLibrary.noMatches')
      : contentTypes
        ? t('assetLibrary.noCompatible')
        : t(projectId ? 'projects.noAssets' : 'assetLibrary.empty');
  const uploadError = error && (
    <p className="form-error" role="alert">
      {error}
    </p>
  );
  const unfilteredEmpty =
    !contentTypes &&
    !text &&
    kind === 'all' &&
    query.isSuccess &&
    query.data.pages.every((page) => !page.items.length);

  return (
    <>
      {!unfilteredEmpty && (
        <PageToolbar className="asset-library-tools" standalone={!!scrollRoot}>
          <SearchField
            aria-label={t('assetLibrary.search')}
            placeholder={t('assetLibrary.search')}
            clearLabel={t('app.clearSearch')}
            value={text}
            maxLength={200}
            onValueChange={setText}
          />
          {!contentTypes && (
            <Select
              label={t('assetLibrary.kind')}
              value={kind}
              options={types}
              onValueChange={(value) => setKind(value as Filter)}
            />
          )}
          {action}
        </PageToolbar>
      )}
      {unfilteredEmpty ? (
        <EmptyState
          label={empty}
          action={
            <>
              {action}
              {uploadError}
            </>
          }
        />
      ) : (
        <>
          {uploadError}
          <MediaCollection
            query={query}
            resetKey={resetKey}
            scrollRoot={scrollRoot}
            label={t('assetLibrary.title')}
            emptyLabel={empty}
            view={(asset) => ({
              label: t(picking ? 'assetLibrary.pick' : 'assetLibrary.preview', asset.filename),
              title: asset.filename,
              media: asset.media,
              detail: fileSizeLabel(asset.size),
            })}
            onOpen={onOpen}
          />
        </>
      )}
    </>
  );
}
