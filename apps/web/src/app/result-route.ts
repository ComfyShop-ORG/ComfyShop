import { useLocation, useNavigate, useSearchParams } from 'react-router';
import type { Location } from 'react-router';

export function resultHistoryDepth(location: Location) {
  if (!new URLSearchParams(location.search).has('result')) return 0;
  const depth = (location.state as { resultDepth?: unknown } | null)?.resultDepth;
  return depth === 1 || depth === 2 ? depth : 0;
}

export function clearResultParams(params: URLSearchParams) {
  params.delete('result');
  params.delete('artifact');
}

/** 结果组和放大的成品各对应一条历史记录，同层切换替换当前记录。 */
export function useResultRoute() {
  const location = useLocation();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const routeState = location.state as Record<string, unknown> | null;
  const resultId = params.get('result');
  const artifactId = resultId ? params.get('artifact') : null;
  const depth = resultHistoryDepth(location);
  function write(result: string | null, artifact: string | null, replace: boolean) {
    const next = new URLSearchParams(params);
    clearResultParams(next);
    if (result) next.set('result', result);
    if (artifact) next.set('artifact', artifact);
    setParams(next, {
      replace,
      preventScrollReset: true,
      state: { ...routeState, resultDepth: result ? depth + Number(!replace) : 0 },
    });
  }
  return {
    resultId,
    artifactId,
    openResult: (id: string) => write(id, null, !!resultId),
    openArtifact: (executionId: string, id: string) => write(executionId, id, !!artifactId),
    closeArtifact: () => {
      if (depth > 0) void navigate(-1);
      else write(resultId, null, true);
    },
    closeResult: () => {
      if (depth > 0 && (!artifactId || depth > 1)) void navigate(-depth);
      else write(null, null, true);
    },
  };
}
