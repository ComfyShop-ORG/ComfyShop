import { useDeferredValue, useRef } from 'react';
import { useSearchParams } from 'react-router';
import { SearchField } from '@comfyshop/ui';
import { DatePicker } from '@comfyshop/ui/date-picker';
import { t } from '../../app/i18n';
import { locale } from '../../app/language';
import { ExecutionCollection } from '../../components/execution-collection';
import { FilterToolbar } from '../../components/page-toolbar';
import { localDayBounds } from '../../data/local-day';
import type { ReplayAction } from '../../domain/types';

function localDay(value: string) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value) || value.startsWith('0000')) return undefined;
  const date = new Date(`${value}T00:00:00`);
  const [, month, day] = value.split('-').map(Number);
  if (month !== date.getMonth() + 1 || day !== date.getDate()) return undefined;
  return {
    date,
    filters: localDayBounds(date),
  };
}

function dateParam(date: Date | undefined) {
  if (!date) return '';
  return [
    String(date.getFullYear()).padStart(4, '0'),
    String(date.getMonth() + 1).padStart(2, '0'),
    String(date.getDate()).padStart(2, '0'),
  ].join('-');
}

export function WorkspaceResults({
  onReplay,
  projectId,
}: {
  onReplay: ReplayAction;
  projectId?: string;
}) {
  const [params, setParams] = useSearchParams();
  const search = useRef<HTMLInputElement>(null);
  const name = (params.get('workflow') ?? '').slice(0, 120);
  const day = localDay(params.get('date') ?? '');
  const workflowName = useDeferredValue(name.trim());
  const filters =
    workflowName || day ? { workflow_name: workflowName || undefined, ...day?.filters } : undefined;

  function change(key: 'workflow' | 'date', value: string) {
    // 连续调整筛选时，浏览器地址可能已经更新，路由还在等待重新渲染。
    const next = new URLSearchParams(window.location.search);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next, { replace: true, preventScrollReset: true });
  }

  function clear() {
    const next = new URLSearchParams(window.location.search);
    next.delete('workflow');
    next.delete('date');
    setParams(next, { replace: true, preventScrollReset: true });
  }

  return (
    <>
      <FilterToolbar onClear={name || day ? clear : undefined} focusOnClear={search}>
        <div className="results-filter-fields">
          <SearchField
            ref={search}
            aria-label={t('workspaceResults.workflowName')}
            placeholder={t('workspaceResults.searchByName')}
            clearLabel={t('app.clearSearch')}
            value={name}
            maxLength={120}
            onValueChange={(value) => change('workflow', value)}
          />
          <DatePicker
            label={t('workspaceResults.date')}
            todayLabel={t('workspaceResults.today')}
            clearLabel={t('workspaceResults.clearDate')}
            locale={locale}
            value={day?.date}
            onValueChange={(value) => change('date', dateParam(value))}
          />
        </div>
      </FilterToolbar>
      <ExecutionCollection filters={filters} onReplay={onReplay} projectId={projectId} />
    </>
  );
}
