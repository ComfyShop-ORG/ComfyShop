import { Outlet, useLocation, useNavigate } from 'react-router';
import { useWorkspace } from '../../app/use-workspace';
import { LoginDialog } from './login-dialog';

/** 个人页面的登录边界。未登录时页面留空并打开登录框，关闭登录框回到首页。 */
export function RequireSession({ restoreFocus }: { restoreFocus: () => void }) {
  const { state } = useWorkspace();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  if (state.userId) return <Outlet />;
  if (!state.ready || state.error) return null;
  return (
    <>
      <main className="page" />
      <LoginDialog
        open
        reason={
          // 工作机首次启动时打开的确认链接，登录后接着确认接入。
          pathname === '/machines/link'
            ? '登录后确认接入这台工作机'
            : '登录后查看自己的工作流、作品和工作机'
        }
        restoreFocus={restoreFocus}
        onOpenChange={(open) => {
          if (!open) void navigate('/', { replace: true });
        }}
      />
    </>
  );
}
