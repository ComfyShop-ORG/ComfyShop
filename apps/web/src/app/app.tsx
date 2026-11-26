import { t } from './i18n.ts';
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Link, useLocation, useNavigate } from 'react-router';
import {
  ArrowTopRightIcon,
  Cross2Icon,
  MagnifyingGlassIcon,
  ChevronDownIcon,
} from '@radix-ui/react-icons';
import { Button, DropdownMenu, IconButton, Input, Logo, Tooltip } from '@comfyshop/ui';
import { CardActions } from '../components/card-actions';
import { NotificationLayer } from '../components/notification';
import { Notify } from '../components/notify';
import type { NoticeAction } from '../components/notify';
import { ProfileAvatar } from '../components/profile-avatar';
import { AccountDialog } from '../features/auth/account-dialog';
import type { AccountSection } from '../features/auth/account-dialog';
import { EmailConfirmDialog } from '../features/auth/email-confirm-dialog';
import { LoginDialog } from '../features/auth/login-dialog';
import type { RequireAuth } from '../features/auth/login-dialog';
import { projectDetailKey } from '../features/projects/project-queries';
import { TeamSwitcher } from '../features/workspace/team-switcher';
import { WorkspaceAccessStatus } from '../features/workspace/workspace-boundary';
import { AccountSpaceUsage } from './account-space-usage';
import { AppRoutes } from './app-routes';
import { BrowserInstallDialog, useBrowserInstall } from './browser-app';
import {
  matchProjectsPath,
  projectsPath,
  projectsRoute,
  ScopedWorkspace,
  workspaceKey,
  workspaceTargetFromPath,
} from './workspace-scope';
import { DisplayPreferenceItem, HeaderPreferences } from './header-preferences';
import { useTeamSelection } from './use-team-selection';
import { useVisualViewport } from './use-visual-viewport';
import { useWorkspace, useWorkspaceAccess, workflowDetailOptions } from './use-workspace';
import { workflowOverlayState, workflowPath, workflowRouteState } from './workflow-route';
import type { Workflow, WorkflowFilters } from '../domain/types';
import type { Project, Replay } from '@comfyshop/api-client';
import { ActiveMark } from '../motion';

const navigation = [
  { to: '/', name: t('app.workflows') },
  { to: projectsRoute, name: t('projects.title') },
  { to: '/workspace', name: t('app.workspace') },
  { to: '/machines', name: t('app.machinesNav') },
];

function hasOpenDialog() {
  return !!document.querySelector(
    '[role="dialog"][data-state="open"], [role="alertdialog"][data-state="open"]',
  );
}

export function App() {
  useVisualViewport();
  const location = useLocation();
  const { teamId, selectTeam } = useTeamSelection(
    workflowRouteState(location)?.background ?? location,
  );
  const { scope, error } = useWorkspaceAccess(teamId ? { kind: 'team', id: teamId } : undefined);
  return (
    <ScopedWorkspace.Provider value={scope}>
      <AppShell
        teamId={teamId}
        selectTeam={selectTeam}
        workspaceStatus={
          teamId && !scope ? (
            <WorkspaceAccessStatus error={error}>
              <Button size="small" onClick={() => selectTeam()}>
                {t('workspaceSharing.backToMine')}
              </Button>
            </WorkspaceAccessStatus>
          ) : undefined
        }
      />
    </ScopedWorkspace.Provider>
  );
}

function AppShell({
  teamId,
  selectTeam,
  workspaceStatus,
}: {
  teamId?: string;
  selectTeam: (id?: string) => void;
  workspaceStatus?: ReactNode;
}) {
  const { api, state, workspace, workspaceScope, workspaceTeam, canManageWorkspace } =
    useWorkspace();
  const browserInstall = useBrowserInstall();
  const displayName = state.nickname ?? state.user ?? '';
  const queries = useQueryClient();
  const location = useLocation();
  const { key: locationKey, pathname } = location;
  const navigate = useNavigate();
  const overlay = workflowRouteState(location);
  const navigationPath = overlay?.background.pathname ?? pathname;
  const projectRoute = matchProjectsPath(navigationPath);
  const navigationScope = workspaceTargetFromPath(navigationPath);
  const resetToken =
    pathname === '/reset-password'
      ? (new URLSearchParams(location.search).get('token') ?? undefined)
      : undefined;
  const confirmToken =
    pathname === '/confirm-email'
      ? (new URLSearchParams(location.search).get('token') ?? undefined)
      : undefined;
  // 搜索词写在首页地址的 `q` 参数里，刷新和分享时保留。输入框用本地状态保证输入法流畅。
  const urlQuery =
    navigationPath === '/'
      ? (new URLSearchParams((overlay?.background ?? location).search).get('q') ?? '')
      : '';
  const [search, setSearchText] = useState(urlQuery);
  const [syncedQuery, setSyncedQuery] = useState(urlQuery);
  if (syncedQuery !== urlQuery) {
    // 前进、后退或打开带搜索词的链接时，以地址为准。
    setSyncedQuery(urlQuery);
    setSearchText(urlQuery);
  }
  function setSearch(value: string) {
    setSearchText(value);
    setSyncedQuery(value);
    const next = new URLSearchParams(pathname === '/' ? location.search : '');
    if (value) next.set('q', value);
    else next.delete('q');
    void navigate(
      { pathname: '/', search: next.toString() },
      { replace: pathname === '/', preventScrollReset: true },
    );
  }
  const [mobileSearchOpen, setMobileSearchOpen] = useState(false);
  const [switchingSpace, setSwitchingSpace] = useState(false);
  const [account, setAccount] = useState<{
    section: AccountSection;
    open: boolean;
    teamId?: string;
  }>({
    section: 'settings',
    open: false,
  });
  const managedTeam =
    canManageWorkspace && workspaceTeam?.id === account.teamId ? workspaceTeam : undefined;
  const setAccountOpen = (open: boolean) => setAccount((previous) => ({ ...previous, open }));
  const [login, setLogin] = useState<{
    locationKey: string;
    action?: () => void | Promise<void>;
    reason?: string;
  } | null>(null);
  const [toast, setToast] = useState<{
    open: boolean;
    text: string;
    id: number;
    action?: NoticeAction;
  }>({ open: false, text: '', id: 0 });
  const homeRef = useRef<HTMLAnchorElement>(null);
  const accountRef = useRef<HTMLButtonElement>(null);
  const guestInstallRef = useRef<HTMLButtonElement>(null);
  const spaceSwitchSource = useRef<HTMLElement | null>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const searchButton = useRef<HTMLButtonElement>(null);
  const searchBox = useRef<HTMLDivElement>(null);
  const pendingSearchFocus = useRef(false);
  const loginSource = useRef<HTMLElement | null>(null);
  const workflowSource = useRef<{ backgroundKey: string; source: HTMLElement } | null>(null);
  const restoreHomeFocus = () => homeRef.current?.focus({ preventScroll: true });
  function openSpaceSwitcher(source: HTMLElement | null) {
    spaceSwitchSource.current = source;
    setSwitchingSpace(true);
  }
  // 登录成功后焦点交给页面主体，不在页头某个控件上留下焦点框。放弃登录则回到首页链接。
  const focusPage = () => {
    const page = document.querySelector('main');
    if (!page) return false;
    page.tabIndex = -1;
    page.focus({ preventScroll: true });
    return true;
  };
  const restoreSessionFocus = () => {
    if (!accountRef.current || !focusPage()) restoreHomeFocus();
  };
  const goToCatalog = useCallback(() => {
    if (pathname !== '/') void navigate('/');
  }, [navigate, pathname]);
  const focusSearch = useCallback(() => {
    if (searchBox.current?.getClientRects().length) searchRef.current?.focus();
    else pendingSearchFocus.current = true;
    setMobileSearchOpen(true);
    goToCatalog();
  }, [goToCatalog, setMobileSearchOpen]);
  useLayoutEffect(() => {
    if (pendingSearchFocus.current && pathname === '/' && mobileSearchOpen) {
      searchRef.current?.focus();
      pendingSearchFocus.current = false;
    }
  }, [pathname, mobileSearchOpen]);
  const notify = useCallback(
    (text: string, action?: NoticeAction) =>
      setToast(({ id }) => ({ open: true, text, id: id + 1, action })),
    [],
  );
  const runAction = useCallback(
    async (action: () => void | Promise<void>) => {
      try {
        await action();
      } catch (error) {
        notify(error instanceof Error ? error.message : t('app.theActionFailed'));
      }
    },
    [notify],
  );
  const requireAuth = useCallback<RequireAuth>(
    (source, action, reason) => {
      if (!state.user) {
        loginSource.current = source;
        setLogin({ locationKey, action, reason });
      } else if (action) void runAction(action);
    },
    [state.user, runAction, locationKey, setLogin],
  );
  function openWorkflow(
    workflow: Workflow,
    source: HTMLElement,
    { filters, replay }: { filters?: WorkflowFilters; replay?: Replay } = {},
  ) {
    const path = workflowPath(workflow.id);
    const target = workspaceTargetFromPath(pathname) ?? workspaceScope;
    workflowSource.current = { backgroundKey: location.key, source };
    // 先用列表里的资料打开弹框，详情随后在后台刷新，点卡片不必等一次请求。
    const detailKey = workflowDetailOptions(
      api,
      state.userId,
      workflow.id,
      undefined,
      target,
    ).queryKey;
    if (!queries.getQueryData(detailKey)) {
      queries.setQueryData(detailKey, workflow);
      void queries.invalidateQueries({ queryKey: detailKey, exact: true });
    }
    const overlay = workflowOverlayState(location, replay, filters);
    if (target?.kind === 'shared') overlay.workspace = target;
    const projectId = matchProjectsPath(pathname)?.params.projectId;
    if (projectId) {
      const project = queries.getQueryData<Project>(
        projectDetailKey(state.userId, target, projectId),
      );
      if (project?.archivedAt === null) overlay.projectId = projectId;
    }
    if (overlay.replaySource)
      queries.setQueryData(
        ['workflow-route-replay', state.userId, overlay.replaySource, ...workspaceKey(target)],
        replay,
      );
    void navigate(path, { state: overlay, preventScrollReset: true });
  }
  function restoreWorkflowFocus(backgroundKey: string) {
    const origin = workflowSource.current;
    if (origin?.backgroundKey === backgroundKey && origin.source.isConnected)
      origin.source.focus({ preventScroll: true });
    else restoreHomeFocus();
  }
  function restoreLoginFocus() {
    const source = loginSource.current;
    loginSource.current = null;
    const dialog = source?.closest('[role="dialog"]');
    const heading = dialog?.isConnected ? dialog.querySelector<HTMLElement>('h2[tabindex]') : null;
    if (source?.isConnected && !source.matches(':disabled')) return source.focus();
    if (heading) return heading.focus({ preventScroll: true });
    // 页头的登录按钮在登录后换成账户菜单，原来的触发元素已经不在。
    if (accountRef.current && focusPage()) return;
    const target = homeRef.current;
    target?.focus({ preventScroll: true });
  }
  useEffect(() => {
    const root = document.documentElement;
    // 在 Radix 恢复焦点前记录输入方式，键盘操作会恢复可见焦点样式。
    const markInput = (event: Event) =>
      root.toggleAttribute('data-pointer-focus', event.type === 'pointerdown');
    window.addEventListener('pointerdown', markInput, true);
    window.addEventListener('keydown', markInput, true);
    return () => {
      window.removeEventListener('pointerdown', markInput, true);
      window.removeEventListener('keydown', markInput, true);
      root.removeAttribute('data-pointer-focus');
    };
  }, []);
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        if (!hasOpenDialog()) focusSearch();
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [focusSearch]);
  if (login && login.locationKey !== locationKey) setLogin(null);
  // 会话在别处失效时关掉账号设置，下次登录不会自己弹出来。
  if (account.open && (!state.user || (account.teamId && !managedTeam))) setAccountOpen(false);
  if (switchingSpace && !state.user) setSwitchingSpace(false);
  return (
    <Tooltip.Provider delayDuration={400}>
      <NotificationLayer
        id={toast.id}
        open={toast.open}
        text={toast.text}
        action={toast.action}
        placement={pathname.startsWith('/workflows/') ? 'top' : 'bottom'}
        onAction={(action) => void runAction(action)}
        onClose={() =>
          setToast((previous) =>
            previous.id === toast.id ? { ...previous, open: false } : previous,
          )
        }
      >
        <Notify.Provider value={notify}>
          <CardActions.Provider
            value={{
              openWorkflow: (workflow, source, filters) =>
                openWorkflow(workflow, source, { filters }),
              favorite: (workflow, source) =>
                requireAuth(
                  source,
                  async () => {
                    const saved = await workspace.toggleFavorite(workflow.id);
                    if (workspaceTeam)
                      notify(
                        t(saved ? 'teams.favoritedIn' : 'teams.unfavoritedIn', workspaceTeam.name),
                      );
                  },
                  t('app.signInToSaveThisWorkflow'),
                ),
            }}
          >
            <header className="app-header ui-glass">
              <div className="header-inner">
                <Button asChild variant="ghost" className="brand">
                  <Link
                    ref={homeRef}
                    to="/"
                    aria-label={t('app.comfyshopHome')}
                    onClick={() => {
                      // 链接回到不带参数的首页，搜索词随地址一起清空。
                      setMobileSearchOpen(false);
                      window.scrollTo({ top: 0 });
                    }}
                  >
                    <Logo wordmark />
                  </Link>
                </Button>
                <nav className="main-nav" aria-label={t('app.mainNavigation')}>
                  {navigation.map((item) => {
                    const projects = item.to === projectsRoute;
                    const active = projects
                      ? !!projectRoute
                      : !projectRoute &&
                        (navigationPath === item.to ||
                          (item.to === '/'
                            ? navigationPath.startsWith('/workflows/')
                            : navigationPath.startsWith(item.to + '/')));
                    return (
                      <Button key={item.to} asChild variant="ghost">
                        <Link
                          to={projects ? projectsPath(navigationScope) : item.to}
                          aria-current={active ? 'page' : undefined}
                        >
                          {active && <ActiveMark group="main-nav" />}
                          {item.name}
                        </Link>
                      </Button>
                    );
                  })}
                </nav>
                <div
                  ref={searchBox}
                  className={`ui-search-field search-box${pathname === '/' && (mobileSearchOpen || search) ? ' search-box-open' : ''}`}
                  role="search"
                >
                  <MagnifyingGlassIcon />
                  <Input
                    ref={searchRef}
                    id="catalog-search"
                    type="search"
                    aria-label={t('app.searchWorkflows')}
                    placeholder={t('app.searchWorkflows')}
                    autoComplete="off"
                    maxLength={120}
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === 'Escape' && !search) {
                        setMobileSearchOpen(false);
                        if (searchButton.current?.getClientRects().length)
                          searchButton.current.focus();
                        else event.currentTarget.blur();
                      }
                    }}
                  />
                  {search ? (
                    <IconButton
                      size="normal"
                      label={t('app.clearSearch')}
                      onClick={() => {
                        setSearch('');
                        searchRef.current?.focus();
                      }}
                    >
                      <Cross2Icon />
                    </IconButton>
                  ) : (
                    <kbd>{/Mac|iPhone|iPad/.test(navigator.userAgent) ? '⌘ K' : 'Ctrl K'}</kbd>
                  )}
                </div>
                <div className="header-actions">
                  <IconButton
                    ref={searchButton}
                    className="mobile-search-trigger"
                    label={
                      pathname === '/' && mobileSearchOpen && !search
                        ? t('app.closeSearch')
                        : t('app.openSearch')
                    }
                    aria-controls="catalog-search"
                    aria-expanded={pathname === '/' && !!(mobileSearchOpen || search)}
                    onClick={() => {
                      if (pathname === '/' && mobileSearchOpen && !search)
                        setMobileSearchOpen(false);
                      else focusSearch();
                    }}
                  >
                    <MagnifyingGlassIcon />
                  </IconButton>
                  <HeaderPreferences
                    install={
                      !state.user && browserInstall.available ? browserInstall.install : undefined
                    }
                    installOpen={browserInstall.open}
                    installTrigger={!state.user ? guestInstallRef : undefined}
                  />
                  {state.user ? (
                    <DropdownMenu.Root>
                      <DropdownMenu.Trigger asChild>
                        <Button
                          ref={accountRef}
                          className="account-button"
                          variant="ghost"
                          aria-label={
                            workspaceTeam
                              ? t('app.accountInTeam', displayName, workspaceTeam.name)
                              : t('app.accountFor', displayName)
                          }
                        >
                          <span className="account-avatars" data-team={!!workspaceTeam}>
                            <ProfileAvatar name={displayName} src={state.avatarUrl} />
                            {workspaceTeam && (
                              <ProfileAvatar
                                className="account-team-avatar"
                                name={workspaceTeam.name}
                                src={workspaceTeam.avatarUrl}
                              />
                            )}
                          </span>
                          <span className="account-name">{workspaceTeam?.name ?? displayName}</span>
                          <ChevronDownIcon />
                        </Button>
                      </DropdownMenu.Trigger>
                      <DropdownMenu.Portal>
                        <DropdownMenu.Content
                          className="ui-menu account-menu"
                          sideOffset={8}
                          align="end"
                          onCloseAutoFocus={(event) => {
                            if (switchingSpace || account.open || browserInstall.open)
                              event.preventDefault();
                          }}
                        >
                          {(!teamId || workspaceTeam) && (
                            <div className="account-menu-space">
                              {workspaceTeam && (
                                <DropdownMenu.Label className="account-menu-identity">
                                  <strong>{workspaceTeam.name}</strong>
                                  <span className="muted">
                                    {displayName} · {t(`teams.${workspaceTeam.role}`)}
                                  </span>
                                </DropdownMenu.Label>
                              )}
                              <AccountSpaceUsage />
                            </div>
                          )}
                          <DropdownMenu.Item
                            className="ui-menu-item"
                            onSelect={() => openSpaceSwitcher(accountRef.current)}
                          >
                            {t('teams.switcher')}
                          </DropdownMenu.Item>
                          {workspaceTeam && canManageWorkspace && (
                            <>
                              <DropdownMenu.Item
                                className="ui-menu-item"
                                onSelect={() =>
                                  setAccount({
                                    section: 'team-profile',
                                    open: true,
                                    teamId: workspaceTeam.id,
                                  })
                                }
                              >
                                {t('teams.profile')}
                              </DropdownMenu.Item>
                              <DropdownMenu.Item
                                className="ui-menu-item"
                                onSelect={() =>
                                  setAccount({
                                    section: 'team-events',
                                    open: true,
                                    teamId: workspaceTeam.id,
                                  })
                                }
                              >
                                {t('teamEvents.menu')}
                              </DropdownMenu.Item>
                            </>
                          )}
                          <DropdownMenu.Item className="ui-menu-item" asChild>
                            <Link to="/workspace/artworks">
                              {t(workspaceTeam ? 'teams.works' : 'app.myWorks')}
                            </Link>
                          </DropdownMenu.Item>
                          <DropdownMenu.Item className="ui-menu-item" asChild>
                            <Link to="/skill">{t('app.installSkill')}</Link>
                          </DropdownMenu.Item>
                          {browserInstall.available && (
                            <DropdownMenu.Item
                              className="ui-menu-item"
                              onSelect={browserInstall.install}
                            >
                              {t('browserApp.install')}
                            </DropdownMenu.Item>
                          )}
                          <DropdownMenu.Item
                            className="ui-menu-item"
                            onSelect={() => setAccount({ section: 'profile', open: true })}
                          >
                            {t('app.profile')}
                          </DropdownMenu.Item>
                          <DropdownMenu.Item
                            className="ui-menu-item"
                            onSelect={() => setAccount({ section: 'settings', open: true })}
                          >
                            {t('app.accountSettings')}
                          </DropdownMenu.Item>
                          <DropdownMenu.Item
                            className="ui-menu-item"
                            onSelect={() => setAccount({ section: 'notifications', open: true })}
                          >
                            {t('webPush.settings')}
                          </DropdownMenu.Item>
                          <DisplayPreferenceItem
                            preference="glass"
                            label={t('app.experimentalGlass')}
                          />
                          <DisplayPreferenceItem
                            preference="fullWidth"
                            label={t('app.experimentalFullWidth')}
                          />
                          <DisplayPreferenceItem
                            preference="workflowFullscreen"
                            label={t('app.experimentalWorkflowFullscreen')}
                          />
                          <DropdownMenu.Item
                            className="ui-menu-item"
                            onSelect={() => {
                              void runAction(async () => {
                                await workspace.signOut();
                                void navigate('/', { replace: true });
                              });
                            }}
                          >
                            {t('app.signOut')}
                          </DropdownMenu.Item>
                        </DropdownMenu.Content>
                      </DropdownMenu.Portal>
                    </DropdownMenu.Root>
                  ) : (
                    <Button
                      variant="primary"
                      className="header-login"
                      disabled={!state.ready}
                      onClick={(event) => requireAuth(event.currentTarget)}
                    >
                      {t('app.signIn')}
                      <ArrowTopRightIcon />
                    </Button>
                  )}
                </div>
              </div>
            </header>
            {state.error && (
              <div className="inline-status" role="alert">
                {state.error}
                <Button size="small" onClick={() => void workspace.reload()}>
                  {t('app.retry')}
                </Button>
              </div>
            )}
            {workspaceStatus ?? (
              <AppRoutes
                key={teamId}
                search={search}
                clearSearch={() => {
                  setSearch('');
                  focusSearch();
                }}
                openWorkflow={openWorkflow}
                onReplay={(replay, source) => openWorkflow(replay.workflow, source, { replay })}
                restoreHomeFocus={restoreHomeFocus}
                restoreSessionFocus={restoreSessionFocus}
                restoreWorkflowFocus={restoreWorkflowFocus}
                requireAuth={requireAuth}
                notify={notify}
                openSpaceSwitcher={openSpaceSwitcher}
                onExitTeam={selectTeam}
              />
            )}
            {switchingSpace && state.user && (
              <TeamSwitcher
                teamId={teamId}
                onSelect={selectTeam}
                onClose={() => setSwitchingSpace(false)}
                restoreFocus={() => {
                  const source = spaceSwitchSource.current;
                  (source?.isConnected ? source : accountRef.current)?.focus({
                    preventScroll: true,
                  });
                }}
              />
            )}
            <LoginDialog
              // 邮件里的重置链接打开同一个弹框，从「设置新密码」开始。
              key={resetToken ?? 'login'}
              open={login !== null || resetToken !== undefined}
              reason={login?.reason}
              resetToken={resetToken}
              restoreFocus={restoreLoginFocus}
              onOpenChange={(open) => {
                if (open) return;
                setLogin(null);
                if (resetToken !== undefined) void navigate('/', { replace: true });
              }}
              onSuccess={() => {
                setLogin(null);
                if (resetToken !== undefined) void navigate('/', { replace: true });
                if (login?.action) void runAction(login.action);
              }}
            />
            {confirmToken !== undefined && (
              <EmailConfirmDialog
                key={confirmToken}
                token={confirmToken}
                onClose={() => void navigate('/', { replace: true })}
              />
            )}
            <BrowserInstallDialog
              open={browserInstall.open}
              onOpenChange={browserInstall.setOpen}
              restoreFocus={() =>
                (accountRef.current ?? guestInstallRef.current ?? homeRef.current)?.focus({
                  preventScroll: true,
                })
              }
            />
            {state.user && (
              <AccountDialog
                key={state.userId}
                section={account.section}
                team={managedTeam}
                open={account.open}
                onOpenChange={setAccountOpen}
                restoreFocus={() => accountRef.current?.focus()}
                onDeleted={() => {
                  setAccountOpen(false);
                  void navigate('/', { replace: true });
                  notify(t('app.accountDeleted'));
                }}
              />
            )}
          </CardActions.Provider>
        </Notify.Provider>
      </NotificationLayer>
    </Tooltip.Provider>
  );
}
