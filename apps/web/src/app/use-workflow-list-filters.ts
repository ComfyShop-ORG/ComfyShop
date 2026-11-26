import { useSearchParams } from 'react-router';
import { workflowCategoryFilters } from '../domain/workflow-categories';
import type { Sort } from '../domain/types';

export function useWorkflowListFilters() {
  const [params, setParams] = useSearchParams();
  const category =
    workflowCategoryFilters.find(({ value }) => value === params.get('category'))?.value ?? 'all';
  const sort: Sort = params.get('sort') === 'popular' ? 'popular' : 'updated';
  function choose(key: string, value: string, fallback: string) {
    setParams(
      (current) => {
        const next = new URLSearchParams(current);
        if (value === fallback) next.delete(key);
        else next.set(key, value);
        return next;
      },
      { replace: true, preventScrollReset: true },
    );
  }
  return {
    category,
    sort,
    setCategory: (value: string) => choose('category', value, 'all'),
    setSort: (value: string) => choose('sort', value, 'updated'),
  };
}
