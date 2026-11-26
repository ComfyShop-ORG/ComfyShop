import type { TeamRole } from '@comfyshop/api-client';
import { t } from '../../app/i18n';

export function TeamRoleLabel({ role, id }: { role: TeamRole; id?: string }) {
  return (
    <span id={id} className="workspace-access-label team-role-label" data-role={role}>
      {t(`teams.${role}`)}
    </span>
  );
}
