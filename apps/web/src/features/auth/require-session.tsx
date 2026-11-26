import { t } from '../../app/i18n.ts';
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
            ? t('requireSession.signInToConnectThisWork')
            : pathname === '/workspace/assets'
              ? t('assetLibrary.signIn')
              : t('requireSession.signInToViewYourWorkflows')
        }
        restoreFocus={restoreFocus}
        onOpenChange={(open) => {
          if (!open) void navigate('/', { replace: true });
        }}
      />
    </>
  );
}
