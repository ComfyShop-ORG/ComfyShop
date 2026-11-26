import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import type { QueryClient } from '@tanstack/react-query';
import { createApiClient } from '@comfyshop/api-client';
import type { AuthSession } from '@comfyshop/api-client';
import { WorkspaceContext } from './use-workspace';
import { t } from './i18n';

function forgetIdentity(queries: QueryClient) {
  void queries.cancelQueries({ predicate: (query) => query.queryKey[0] !== 'session' });
  queries.removeQueries({ predicate: (query) => query.queryKey[0] !== 'session' });
}

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const queries = useQueryClient();
  const [api] = useState(() =>
    createApiClient(
      '',
      fetch,
      () => queries.setQueryData(['session'], { user: null, csrfToken: null }),
      {
        messages: {
          offline: t('api.offline'),
          requestFailed: t('api.requestFailed'),
          invalidResponse: t('api.invalidResponse'),
        },
      },
    ),
  );
  useEffect(() => {
    // 会话在别处变了（另一个标签页换了账号或退出、重置密码后失效），重新读取时发现
    // 账号不同，就丢掉原账号的全部缓存。有些公开列表的键不含用户 ID，但内容随身份不同。
    const sessionHash = JSON.stringify(['session']);
    const userOf = () => queries.getQueryData<AuthSession>(['session'])?.user?.id ?? null;
    let known = userOf();
    return queries.getQueryCache().subscribe((event) => {
      if (event.type !== 'updated' || event.query.queryHash !== sessionHash) return;
      if (event.action.type !== 'success') return;
      const next = userOf();
      if (next !== known) forgetIdentity(queries);
      known = next;
    });
  }, [queries]);
  return <WorkspaceContext.Provider value={api}>{children}</WorkspaceContext.Provider>;
}
