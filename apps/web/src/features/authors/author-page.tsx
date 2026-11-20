/** 作者页面：一位作者公开的工作流和作品。 */
import { lazy, Suspense } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router';
import { Button, Tabs } from '@comfyshop/ui';
import type { ReplayAction } from '../../domain/types';
import type { RequireAuth } from '../auth/login-dialog';
import { ActiveMark } from '../../motion';
import { WorkflowCollection } from '../catalog/workflow-collection';

const WorkCollection = lazy(() =>
  import('../../components/work-collection').then(({ WorkCollection }) => ({
    default: WorkCollection,
  })),
);

const tabs = [
  { id: 'workflows', label: '工作流' },
  { id: 'works', label: '作品' },
] as const;

export function AuthorPage({
  onReplay,
  requireAuth,
}: {
  onReplay: ReplayAction;
  requireAuth: RequireAuth;
}) {
  const { name = '' } = useParams();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const tab = params.get('tab') === 'works' ? 'works' : 'workflows';
  return (
    <main className="page">
      <div className="section-heading author-heading">
        <span className="avatar-small author-avatar">{name.slice(0, 1).toUpperCase()}</span>
        <h1>{name}</h1>
      </div>
      <Tabs.Root
        value={tab}
        onValueChange={(value) =>
          setParams(value === 'works' ? { tab: 'works' } : {}, { replace: true })
        }
      >
        <div className="page-toolbar">
          <Tabs.List className="filter-group" aria-label={`${name} 的公开内容`}>
            {tabs.map((item) => (
              <Tabs.Trigger key={item.id} value={item.id} asChild>
                <Button variant="ghost" size="small">
                  {item.id === tab && <ActiveMark group="author-tabs" />}
                  {item.label}
                </Button>
              </Tabs.Trigger>
            ))}
          </Tabs.List>
        </div>
        <Tabs.Content value="workflows">
          {tab === 'workflows' && (
            <WorkflowCollection author={name} onReset={() => void navigate('/')} />
          )}
        </Tabs.Content>
        <Tabs.Content value="works">
          {tab === 'works' && (
            <Suspense fallback={null}>
              <WorkCollection author={name} onReplay={onReplay} requireAuth={requireAuth} />
            </Suspense>
          )}
        </Tabs.Content>
      </Tabs.Root>
    </main>
  );
}
