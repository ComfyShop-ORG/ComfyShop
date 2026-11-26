import { t } from '../app/i18n.ts';
import type { ReactNode } from 'react';
import type { UseInfiniteQueryResult } from '@tanstack/react-query';
import { Button } from '@comfyshop/ui';

export function EmptyState({ label, action }: { label: string; action?: ReactNode }) {
  return (
    <div className="empty-state">
      <p>{label}</p>
      {action}
    </div>
  );
}

function CollectionError({
  error,
  retry,
  plain = false,
}: {
  error: Error;
  retry: () => unknown;
  plain?: boolean;
}) {
  const Container = plain ? 'p' : 'div';
  return (
    <Container className={plain ? undefined : 'inline-status'} role="alert">
      {error.message}
      {plain && ' '}
      <Button size="small" onClick={() => void retry()}>
        {t('app.retry')}
      </Button>
    </Container>
  );
}

export function CollectionStatus({
  pending,
  error,
  empty,
  retry,
  label,
  action,
}: {
  pending: boolean;
  error: Error | null;
  empty: boolean;
  retry: () => unknown;
  label: string;
  action?: ReactNode;
}) {
  if (error) return <CollectionError error={error} retry={retry} />;
  return !pending && empty ? <EmptyState label={label} action={action} /> : null;
}

export function PaginatedListFeedback({
  query,
  children,
  plain = false,
  fallbackErrorSource,
  loadMoreClassName,
}: {
  query: Pick<
    UseInfiniteQueryResult,
    | 'isPending'
    | 'error'
    | 'refetch'
    | 'hasNextPage'
    | 'isFetching'
    | 'isFetchNextPageError'
    | 'fetchNextPage'
  >;
  children?: ReactNode;
  plain?: boolean;
  fallbackErrorSource?: Pick<UseInfiniteQueryResult, 'error' | 'refetch'>;
  loadMoreClassName?: string;
}) {
  const errorSource = query.error || !fallbackErrorSource ? query : fallbackErrorSource;
  const loadMore = () => query.fetchNextPage({ cancelRefetch: false });
  const retry = query.isFetchNextPageError
    ? loadMore
    : () => errorSource.refetch({ cancelRefetch: false });
  return (
    <>
      {query.isPending && !errorSource.error && (
        <p role="status" className={plain ? undefined : 'form-hint'}>
          {t('common.loading')}
        </p>
      )}
      {errorSource.error && (
        <CollectionError error={errorSource.error} retry={retry} plain={plain} />
      )}
      {children}
      {query.hasNextPage && (
        <Button
          className={loadMoreClassName}
          size="small"
          disabled={query.isFetching}
          onClick={() => void loadMore()}
        >
          {t('taskList.loadMore')}
        </Button>
      )}
    </>
  );
}
