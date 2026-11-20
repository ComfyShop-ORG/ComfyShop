import type { ReactNode } from 'react';
import { Button } from '@comfyshop/ui';

export function EmptyState({ label, action }: { label: string; action?: ReactNode }) {
  return (
    <div className="empty-state">
      <p>{label}</p>
      {action}
    </div>
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
  if (error)
    return (
      <div className="inline-status" role="alert">
        {error.message}
        <Button size="small" onClick={() => void retry()}>
          重试
        </Button>
      </div>
    );
  return !pending && empty ? <EmptyState label={label} action={action} /> : null;
}
