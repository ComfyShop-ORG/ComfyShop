import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Link, useLocation, useNavigate } from 'react-router';
import {
  ArrowTopRightIcon,
  Cross2Icon,
  MagnifyingGlassIcon,
  ChevronDownIcon,
} from '@radix-ui/react-icons';
import { Button, DropdownMenu, IconButton, Input, Logo, Toast, Tooltip } from '@comfyshop/ui';
import { CardActions } from '../components/card-actions';
import { Notify } from '../components/notify';
import type { NoticeAction } from '../components/notify';
import { AccountDialog } from '../features/auth/account-dialog';
import { EmailConfirmDialog } from '../features/auth/email-confirm-dialog';
import { LoginDialog } from '../features/auth/login-dialog';
import type { RequireAuth } from '../features/auth/login-dialog';
import { AppRoutes } from './app-routes';
import { useWorkspace } from './use-workspace';
import { workflowOverlayState, workflowPath, workflowRouteState } from './workflow-route';
import type { Workflow, WorkflowFilters } from '../domain/types';
import type { Replay } from '@comfyshop/api-client';
import { ActiveMark } from '../motion';

const navigation = [
  { to: '/', name: '工作流' },
  { to: '/workspace', name: '我的' },
  { to: '/machines', name: '工作机' },
];

function hasOpenDialog() {
  return !!document.querySelector(
    '[role="dialog"][data-state="open"], [role="alertdialog"][data-state="open"]',
  );
}

export function App() {
  const { state, workspace } = useWorkspace();
  const queries = useQueryClient();
  const location = useLocation();
  const { key: locationKey, pathname } = location;
  const navigate = useNavigate();
  const overlay = workflowRouteState(location);
  const navigationPath = overlay?.background.pathname ?? pathname;
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
  const [accountOpen, setAccountOpen] = useState(false);
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
  const searchRef = useRef<HTMLInputElement>(null);
  const searchButton = useRef<HTMLButtonElement>(null);
  const searchBox = useRef<HTMLDivElement>(null);
  const pendingSearchFocus = useRef(false);
  const loginSource = useRef<HTMLElement | null>(null);
  const workflowSource = useRef<{ backgroundKey: string; source: HTMLElement } | null>(null);
  const restoreHomeFocus = () => homeRef.current?.focus({ preventScroll: true });
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
  }, [goToCatalog]);
  useLayoutEffect(() => {
    if (pendingSearchFocus.current && pathname === '/' && mobileSearchOpen) {
      searchRef.current?.focus();
      pendingSearchFocus.current = false;
    }
  }, [pathname, mobileSearchOpen]);
  const notify = useCallback(
    (text: string, action?: NoticeAction) => setToast({ open: true, text, id: Date.now(), action }),
    [],
  );
  const runAction = useCallback(
    async (action: () => void | Promise<void>) => {
      try {
        await action();
      } catch (error) {
        notify(error instanceof Error ? error.message : '操作失败');
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
    [state.user, runAction, locationKey],
  );
  function openWorkflow(
    workflow: Workflow,
    source: HTMLElement,
    { filters, replay }: { filters?: WorkflowFilters; replay?: Replay } = {},
  ) {
    const path = workflowPath(workflow.id);
    workflowSource.current = { backgroundKey: location.key, source };
    // 先用列表里的资料打开弹框，详情随后在后台刷新，点卡片不必等一次请求。
    const detailKey = ['workflows', 'detail', state.userId, workflow.id];
    if (!queries.getQueryData(detailKey)) {
      queries.setQueryData(detailKey, workflow);
      void queries.invalidateQueries({ queryKey: detailKey, exact: true });
    }
    const overlay = workflowOverlayState(location, replay, filters);
    if (overlay.replaySource)
      queries.setQueryData(['workflow-route-replay', state.userId, overlay.replaySource], replay);
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
  if (accountOpen && !state.user) setAccountOpen(false);
  return (
    <Tooltip.Provider delayDuration={400}>
      <Toast.Provider duration={2600}>
        <Notify.Provider value={notify}>
          <CardActions.Provider
            value={{
              openWorkflow: (workflow, source, filters) =>
                openWorkflow(workflow, source, { filters }),
              favorite: (id, source) =>
                requireAuth(source, () => workspace.toggleFavorite(id), '登录后收藏这个工作流'),
            }}
          >
            <header className="app-header">
              <div className="header-inner">
                <Button asChild variant="ghost" className="brand">
                  <Link
                    ref={homeRef}
                    to="/"
                    aria-label="ComfyShop 首页"
                    onClick={() => {
                      // 链接回到不带参数的首页，搜索词随地址一起清空。
                      setMobileSearchOpen(false);
                      window.scrollTo({ top: 0 });
                    }}
                  >
                    <Logo wordmark />
                  </Link>
                </Button>
                <nav className="main-nav" aria-label="主导航">
                  {navigation.map((item) => {
                    const active =
                      navigationPath === item.to ||
                      (item.to === '/'
                        ? navigationPath.startsWith('/workflows/')
                        : navigationPath.startsWith(item.to + '/'));
                    return (
                      <Button key={item.to} asChild variant="ghost">
                        <Link to={item.to} aria-current={active ? 'page' : undefined}>
                          {active && <ActiveMark group="main-nav" />}
                          {item.name}
                        </Link>
                      </Button>
                    );
                  })}
                </nav>
                <div
                  ref={searchBox}
                  className={`search-box${pathname === '/' && (mobileSearchOpen || search) ? ' search-box-open' : ''}`}
                  role="search"
                >
                  <MagnifyingGlassIcon />
                  <Input
                    ref={searchRef}
                    id="catalog-search"
                    type="search"
                    aria-label="搜索工作流"
                    placeholder="搜索工作流"
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
                      label="清除搜索"
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
                      pathname === '/' && mobileSearchOpen && !search ? '关闭搜索' : '打开搜索'
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
                  {state.user ? (
                    <DropdownMenu.Root>
                      <DropdownMenu.Trigger asChild>
                        <Button
                          ref={accountRef}
                          className="account-button"
                          variant="ghost"
                          aria-label={`账户 ${state.user}`}
                        >
                          <span className="avatar-small">
                            {state.user.slice(0, 1).toUpperCase()}
                          </span>
                          <span>{state.user}</span>
                          <ChevronDownIcon />
                        </Button>
                      </DropdownMenu.Trigger>
                      <DropdownMenu.Portal>
                        <DropdownMenu.Content className="ui-menu" sideOffset={8} align="end">
                          <DropdownMenu.Item className="ui-menu-item" asChild>
                            <Link to="/workspace/artworks">我的作品</Link>
                          </DropdownMenu.Item>
                          <DropdownMenu.Item className="ui-menu-item" asChild>
                            <Link to="/skill">安装 Skill</Link>
                          </DropdownMenu.Item>
                          <DropdownMenu.Item
                            className="ui-menu-item"
                            onSelect={() => setAccountOpen(true)}
                          >
                            账号设置
                          </DropdownMenu.Item>
                          <DropdownMenu.Item
                            className="ui-menu-item"
                            onSelect={() => {
                              void runAction(async () => {
                                await workspace.signOut();
                                void navigate('/', { replace: true });
                              });
                            }}
                          >
                            退出登录
                          </DropdownMenu.Item>
                        </DropdownMenu.Content>
                      </DropdownMenu.Portal>
                    </DropdownMenu.Root>
                  ) : (
                    <Button
                      size="small"
                      variant="primary"
                      className="header-login"
                      disabled={!state.ready}
                      onClick={(event) => requireAuth(event.currentTarget)}
                    >
                      登录
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
                  重试
                </Button>
              </div>
            )}
            <AppRoutes
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
            />
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
            {state.user && (
              <AccountDialog
                open={accountOpen}
                onOpenChange={setAccountOpen}
                restoreFocus={() => accountRef.current?.focus()}
                onDeleted={() => {
                  setAccountOpen(false);
                  void navigate('/', { replace: true });
                  notify('账号已注销');
                }}
              />
            )}
            <Toast.Root
              key={toast.id}
              className="ui-toast"
              open={toast.open}
              onOpenChange={(open) => setToast((previous) => ({ ...previous, open }))}
            >
              <Toast.Title>{toast.text}</Toast.Title>
              {toast.action && (
                <Toast.Action altText={toast.action.label} asChild>
                  <Button
                    size="small"
                    onClick={() => {
                      const { run } = toast.action!;
                      void runAction(run);
                    }}
                  >
                    {toast.action.label}
                  </Button>
                </Toast.Action>
              )}
              <Toast.Close asChild>
                <IconButton label="关闭通知">
                  <Cross2Icon />
                </IconButton>
              </Toast.Close>
            </Toast.Root>
            <Toast.Viewport
              className="ui-toast-viewport"
              data-placement={pathname.startsWith('/workflows/') ? 'top' : 'bottom'}
            />
          </CardActions.Provider>
        </Notify.Provider>
      </Toast.Provider>
    </Tooltip.Provider>
  );
}
