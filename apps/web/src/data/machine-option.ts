import type { Machine } from '@comfyshop/api-client';
import { t } from '../app/i18n';

function statusLabel(machine: Machine) {
  if (machine.worker.connection === 'account') return t('connection.configured');
  if (!machine.online) return t('machinesPage.offline');
  if (machine.paused) return t('machinesPage.tasksPaused');
  if (machine.busy) return t('machinesPage.busy');
  return t('machinesPage.online');
}

export function machineOption(machine: Machine) {
  return {
    value: machine.id,
    label: `${machine.name} · ${statusLabel(machine)}`,
    disabled: !machine.online,
  };
}
