import { t } from '../../app/i18n.ts';
import { useWorkflowListFilters } from '../../app/use-workflow-list-filters';
import { Button, Select, ToggleGroup } from '@comfyshop/ui';
import { workflowCategoryFilters, workflowCategoryMenu } from '../../domain/workflow-categories';
import { useMediaQuery } from '../../app/use-media-query';
import { WorkflowCollection } from './workflow-collection';
import { ActiveMark } from '../../motion';

export function CatalogPage({ search, clearSearch }: { search: string; clearSearch: () => void }) {
  const { category, sort, setCategory, setSort } = useWorkflowListFilters();
  const compact = useMediaQuery('(max-width: 1535px), (max-height: 500px)');
  return (
    <main className="page">
      <div className="page-toolbar catalog-toolbar">
        {compact ? (
          <Select
            className="catalog-category-select"
            label={t('catalogPage.workflowCategory')}
            value={category}
            onValueChange={setCategory}
            options={workflowCategoryMenu}
          />
        ) : (
          <ToggleGroup.Root
            className="filter-group"
            type="single"
            value={category}
            onValueChange={(value) => {
              if (value) setCategory(value);
            }}
            aria-label={t('catalogPage.workflowCategory')}
          >
            {workflowCategoryFilters.map((item) => (
              <ToggleGroup.Item key={item.value} value={item.value} asChild>
                <Button variant="ghost">
                  {item.value === category && <ActiveMark group="catalog-category" />}
                  {item.label}
                </Button>
              </ToggleGroup.Item>
            ))}
          </ToggleGroup.Root>
        )}
        <Select
          className="catalog-sort"
          label={t('catalogPage.sort')}
          value={sort}
          onValueChange={setSort}
          options={[
            { value: 'updated', label: t('catalogPage.recentlyUpdated') },
            { value: 'popular', label: t('catalogPage.mostPopular') },
          ]}
        />
      </div>
      <WorkflowCollection
        search={search}
        category={category}
        sort={sort}
        onReset={search ? clearSearch : () => setCategory('all')}
      />
    </main>
  );
}
