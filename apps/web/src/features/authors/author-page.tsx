/** 个人作者与团队共用的公开主页。 */
import { t } from '../../app/i18n.ts';
import { lazy, Suspense } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router';
import { ApiError } from '@comfyshop/api-client';
import { Button, Tabs, TabsList } from '@comfyshop/ui';
import { useAuthor, usePublicTeam } from '../../app/use-workspace';
import { TabbedToolbar } from '../../components/page-toolbar';
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
  { id: 'workflows', label: t('app.workflows') },
  { id: 'works', label: t('workCollection.works') },
] as const;

type ProfilePageActions = {
  onReplay: ReplayAction;
  requireAuth: RequireAuth;
};

export function AuthorPage(props: ProfilePageActions) {
  const { name = '' } = useParams();
  const author = useAuthor(name);
  return (
    <PublicProfilePage
      {...props}
      displayName={author.data?.nickname ?? author.data?.username}
      avatarUrl={author.data?.avatarUrl}
      author={author.data?.username}
      error={author.error}
      retry={author.refetch}
      loadingLabel={t('authorPage.loadingAuthorProfile')}
    />
  );
}

export function PublicTeamPage(props: ProfilePageActions) {
  const { teamId } = useParams();
  const team = usePublicTeam(teamId);
  return (
    <PublicProfilePage
      {...props}
      displayName={team.data?.name}
      avatarUrl={team.data?.avatarUrl}
      publicTeamId={teamId}
      defaultTab={team.data?.hasWorkflows ? 'workflows' : 'works'}
      error={team.error}
      retry={team.refetch}
      loadingLabel={t('teams.loadingPublicProfile')}
    />
  );
}

function PublicProfilePage({
  displayName,
  avatarUrl,
  author,
  publicTeamId,
  defaultTab = 'workflows',
  error,
  retry,
  loadingLabel,
  onReplay,
  requireAuth,
}: ProfilePageActions & {
  displayName?: string;
  avatarUrl?: string | null;
  author?: string;
  publicTeamId?: string;
  defaultTab?: (typeof tabs)[number]['id'];
  error: Error | null;
  retry: () => unknown;
  loadingLabel: string;
}) {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const requestedTab = params.get('tab');
  const tab = requestedTab === 'works' || requestedTab === 'workflows' ? requestedTab : defaultTab;
  const unavailable = error instanceof ApiError && [404, 422].includes(error.status);
  if (!displayName || unavailable) {
    return (
      <main className="page">
        <div className="inline-status" role={error ? 'alert' : 'status'}>
          {error?.message ?? loadingLabel}
          {error &&
            (unavailable ? (
              <Button asChild size="small">
                <Link to="/">{t('appRoutes.backToWorkflows')}</Link>
              </Button>
            ) : (
              <Button size="small" onClick={() => void retry()}>
                {t('app.retry')}
              </Button>
            ))}
        </div>
      </main>
    );
  }
  return (
    <main className="page">
      <div className="section-heading author-heading">
        <ProfileAvatar name={displayName} src={avatarUrl} className="avatar-small author-avatar" />
        <h1>{displayName}</h1>
      </div>
      <Tabs.Root
        value={tab}
        onValueChange={(value) =>
          setParams(value === defaultTab ? {} : { tab: value }, { replace: true })
        }
      >
        <TabbedToolbar
          navigation={
            <TabsList
              className="filter-group"
              aria-label={t('authorPage.publicContentBy', displayName)}
            >
              {tabs.map((item) => (
                <Tabs.Trigger key={item.id} value={item.id} asChild>
                  <Button variant="ghost">
                    {item.id === tab && <ActiveMark group="author-tabs" />}
                    {item.label}
                  </Button>
                </Tabs.Trigger>
              ))}
            </TabsList>
          }
        >
          <Tabs.Content value="workflows">
            {tab === 'workflows' && (
              <WorkflowCollection
                author={author}
                publicTeamId={publicTeamId}
                onReset={() => void navigate('/')}
              />
            )}
          </Tabs.Content>
          <Tabs.Content value="works">
            {tab === 'works' && (
              <Suspense fallback={null}>
                <WorkCollection
                  author={author}
                  publicTeamId={publicTeamId}
                  onReplay={onReplay}
                  requireAuth={requireAuth}
                />
              </Suspense>
            )}
          </Tabs.Content>
        </TabbedToolbar>
      </Tabs.Root>
    </main>
  );
}
