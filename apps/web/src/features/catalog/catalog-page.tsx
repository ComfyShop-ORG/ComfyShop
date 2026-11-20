import { useSearchParams } from 'react-router';
import { Button, Select, ToggleGroup } from '@comfyshop/ui';
import type { Sort } from '../../domain/types';
import { workflowCategoryFilters } from '../../domain/workflow-categories';
import { WorkflowCollection } from './workflow-collection';
import { ActiveMark } from '../../motion';

export function CatalogPage({ search, clearSearch }: { search: string; clearSearch: () => void }) {
  // 分类和排序写在地址里，打开工作流再返回、刷新或分享链接时保持不变。
  const [params, setParams] = useSearchParams();
  const category =
    workflowCategoryFilters.find(({ value }) => value === params.get('category'))?.value ?? 'all';
  const sort: Sort = params.get('sort') === 'popular' ? 'popular' : 'updated';
  function choose(key: 'category' | 'sort', value: string, fallback: string) {
    setParams(
      (prior) => {
        const next = new URLSearchParams(prior);
        if (value === fallback) next.delete(key);
        else next.set(key, value);
        return next;
      },
      { replace: true, preventScrollReset: true },
    );
  }
  return (
    <main className="page">
      <div className="page-toolbar">
        <ToggleGroup.Root
          className="filter-group"
          type="single"
          value={category}
          onValueChange={(value) => {
            if (value) choose('category', value, 'all');
          }}
          aria-label="工作流分类"
        >
          {workflowCategoryFilters.map((item) => (
            <ToggleGroup.Item key={item.value} value={item.value} asChild>
              <Button size="small" variant="ghost">
                {item.value === category && <ActiveMark group="catalog-category" />}
                {item.label}
              </Button>
            </ToggleGroup.Item>
          ))}
        </ToggleGroup.Root>
        <Select
          className="sort-select"
          label="排序"
          value={sort}
          onValueChange={(value) => choose('sort', value, 'updated')}
          options={[
            { value: 'updated', label: '最近更新' },
            { value: 'popular', label: '最受欢迎' },
          ]}
        />
      </div>
      <WorkflowCollection
        search={search}
        category={category}
        sort={sort}
        onReset={search ? clearSearch : () => choose('category', 'all', 'all')}
      />
    </main>
  );
}
