/** 作者页面：一位作者公开的工作流和作品。 */
import { lazy, Suspense } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router';
import { ApiError } from '@comfyshop/api-client';
import { Button, Tabs } from '@comfyshop/ui';
import { useAuthor } from '../../app/use-workspace';
import { ProfileAvatar } from '../../components/profile-avatar';
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
  const author = useAuthor(name);
  if (!author.data) {
    const unavailable = author.error instanceof ApiError && author.error.status === 404;
    return (
      <main className="page">
        <div className="inline-status" role={author.error ? 'alert' : 'status'}>
          {author.error?.message ?? '正在读取作者资料'}
          {author.error &&
            (unavailable ? (
              <Button asChild size="small">
                <Link to="/">返回工作流</Link>
              </Button>
            ) : (
              <Button size="small" onClick={() => void author.refetch()}>
                重试
              </Button>
            ))}
        </div>
      </main>
    );
  }
  const { username, nickname, avatarUrl } = author.data;
  const displayName = nickname ?? username;
  return (
    <main className="page">
      <div className="section-heading author-heading">
        <ProfileAvatar name={displayName} src={avatarUrl} className="avatar-small author-avatar" />
        <h1>{displayName}</h1>
      </div>
      <Tabs.Root
        value={tab}
        onValueChange={(value) =>
          setParams(value === 'works' ? { tab: 'works' } : {}, { replace: true })
        }
      >
        <div className="page-toolbar">
          <Tabs.List className="filter-group" aria-label={`${displayName} 的公开内容`}>
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
            <WorkflowCollection author={username} onReset={() => void navigate('/')} />
          )}
        </Tabs.Content>
        <Tabs.Content value="works">
          {tab === 'works' && (
            <Suspense fallback={null}>
              <WorkCollection author={username} onReplay={onReplay} requireAuth={requireAuth} />
            </Suspense>
          )}
        </Tabs.Content>
      </Tabs.Root>
    </main>
  );
}
