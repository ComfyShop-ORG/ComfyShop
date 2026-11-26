import type { ReactNode } from 'react';
import { Link } from 'react-router';
import { Button } from '@comfyshop/ui';
import { t } from '../../app/i18n';
import { useWorkspaceAccess } from '../../app/use-workspace';
import { ScopedWorkspace, workspaceRoutes } from '../../app/workspace-scope';
import type { WorkspaceTarget } from '../../app/workspace-scope';

export function WorkspaceAccessStatus({
  error,
  children,
}: {
  error: Error | null;
  children: ReactNode;
}) {
  return (
    <main className="page">
      <div className="inline-status" role={error ? 'alert' : 'status'}>
        {error?.message ?? t('common.loading')}
        {error && children}
      </div>
    </main>
  );
}

export function WorkspaceBoundary({
  target,
  children,
  overlay,
}: {
  target: WorkspaceTarget;
  children: ReactNode;
  overlay?: boolean;
}) {
  const { userId, scope, error } = useWorkspaceAccess(target);
  if (!userId || (overlay && !scope)) return null;
  if (!scope)
    return (
      <WorkspaceAccessStatus error={error}>
        <Button asChild size="small">
          <Link to={workspaceRoutes.personal}>{t('workspaceSharing.backToMine')}</Link>
        </Button>
      </WorkspaceAccessStatus>
    );
  return <ScopedWorkspace.Provider value={scope}>{children}</ScopedWorkspace.Provider>;
}
