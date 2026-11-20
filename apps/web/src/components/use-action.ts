/** 弹框里串行执行的写操作：同一时间只跑一个，失败信息留给界面显示。 */
import { useState } from 'react';

/**
 * @param fallback 异常不带说明时显示的文字。
 * @param scope 当前操作对象的标识。对象切换后，之前留下的失败信息不再显示。
 */
export function useAction(fallback = '操作失败', scope = '') {
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState({ scope, message: '' });
  async function run(operation: () => Promise<void>) {
    if (busy) return;
    setBusy(true);
    setFailure({ scope, message: '' });
    try {
      await operation();
    } catch (error) {
      setFailure({ scope, message: error instanceof Error ? error.message : fallback });
    } finally {
      setBusy(false);
    }
  }
  return {
    busy,
    error: failure.scope === scope ? failure.message : '',
    run,
    clearError: () => setFailure({ scope, message: '' }),
  };
}
