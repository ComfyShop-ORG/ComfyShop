import { useEffect, useState } from 'react';
import { matchPath, useNavigate } from 'react-router';
import type { Location } from 'react-router';
import { useSession } from './use-workspace';
import {
  matchProjectsPath,
  projectsPath,
  workspacePath,
  workspaceRoutes,
  workspaceTargetFromPath,
} from './workspace-scope';

const storageKey = 'comfyshop.selectedTeam';
type Selection = { userId: string; teamId: string };

function readSelection(): Selection | null {
  try {
    const value = JSON.parse(
      sessionStorage.getItem(storageKey) ?? 'null',
    ) as Partial<Selection> | null;
    if (typeof value?.userId === 'string' && typeof value.teamId === 'string')
      return { userId: value.userId, teamId: value.teamId };
  } catch {
    // 浏览器可能封锁会话存储。当前页面仍可切换空间。
  }
  return null;
}

export function useTeamSelection({ pathname, search, key }: Location) {
  const navigate = useNavigate();
  const session = useSession();
  const userId = session.data?.user?.id;
  const [selection, setSelection] = useState(readSelection);
  const [handledScopeLink, setHandledScopeLink] = useState<string>();
  const target = workspaceTargetFromPath(pathname);
  const params = new URLSearchParams(search);
  const personalTaskLink =
    pathname === workspacePath(undefined, 'tasks') &&
    params.has('task') &&
    params.get('space') === 'personal';
  const scopeLink =
    userId && (target?.kind === 'team' || personalTaskLink) ? `${userId}:${key}` : undefined;
  const teamId = selection?.userId === userId ? selection?.teamId : undefined;

  // 带空间的链接只在进入时选择一次，之后由当前空间决定内容。
  if (scopeLink !== handledScopeLink) {
    setHandledScopeLink(scopeLink);
    if (userId && target?.kind === 'team') setSelection({ userId, teamId: target.id });
    else if (userId && personalTaskLink) setSelection(null);
  } else if (!session.isPending && selection && selection.userId !== userId) {
    setSelection(null);
  }

  useEffect(() => {
    if (session.isPending) return;
    try {
      if (userId && teamId) sessionStorage.setItem(storageKey, JSON.stringify({ userId, teamId }));
      else sessionStorage.removeItem(storageKey);
    } catch {
      // 会话存储可选，团队权限每次由 API 校验。
    }
  }, [session.isPending, userId, teamId]);

  function selectTeam(id?: string) {
    if (!userId) return;
    setSelection(id ? { userId, teamId: id } : null);
    if (matchProjectsPath(pathname)) {
      if (target?.kind === 'shared' || id !== teamId)
        void navigate(projectsPath(), { replace: true });
      return;
    }
    if (!target) return;
    const linked = matchPath(`${workspaceRoutes[target.kind]}/*`, pathname);
    const tab = linked?.params['*']?.split('/')[0] || undefined;
    void navigate(workspacePath(undefined, tab), { replace: target.kind === 'team' });
  }

  return { teamId, selectTeam };
}
