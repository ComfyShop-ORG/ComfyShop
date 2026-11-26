import { t } from '../../app/i18n.ts';
import type { Machine } from '@comfyshop/api-client';

export function machineUpdateLabel(update: Machine['update']) {
  switch (update?.status) {
    case 'pending':
      return t('machineUpdate.waitingToUpdate');
    case 'updating':
      return update.release
        ? t('machineUpdate.updatingTo', update.release.version)
        : t('machineUpdate.updating');
    case 'succeeded':
      return update.release
        ? t('machineUpdate.updatedTo', update.release.version)
        : t('machineUpdate.updateComplete');
    case 'failed':
      return update.error || t('machineUpdate.updateFailed');
    default:
      return null;
  }
}
