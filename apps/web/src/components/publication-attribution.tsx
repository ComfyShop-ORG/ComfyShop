import { Link } from 'react-router';
import type { Workflow } from '@comfyshop/api-client';
import { t } from '../app/i18n';
import { authorPath, publicTeamPath } from '../app/workflow-route';
import { ProfileAvatar } from './profile-avatar';

type Credit = Pick<Workflow, 'author' | 'authorProfile' | 'publicTeam'>;

function authorIdentity(content: Credit) {
  return {
    name: content.authorProfile.nickname ?? content.author,
    avatarUrl: content.authorProfile.avatarUrl,
  };
}

export function CardAttribution({ content, showTeam }: { content: Credit; showTeam: boolean }) {
  const profile = (showTeam && content.publicTeam) || authorIdentity(content);
  return (
    <>
      <ProfileAvatar name={profile.name} src={profile.avatarUrl} />
      <span className="profile-name">{profile.name}</span>
    </>
  );
}

export function AttributionLinks({
  content,
  teamTab,
  authorLabel,
  showAvatar = false,
  onTeamClick,
}: {
  content: Credit;
  teamTab?: 'works';
  authorLabel?: string;
  showAvatar?: boolean;
  onTeamClick?: () => void;
}) {
  const author = authorIdentity(content);
  const team = content.publicTeam;
  const profile = team ?? author;
  return (
    <>
      {showAvatar && <ProfileAvatar name={profile.name} src={profile.avatarUrl} />}
      <span className="publication-byline">
        {team && (
          <>
            <Link
              className="author-link publication-team-link"
              to={publicTeamPath(team.id, teamTab)}
              aria-label={`${t('teams.viewPublicProfile')} ${team.name}`}
              onClick={onTeamClick}
            >
              {team.name}
            </Link>
            {' · '}
          </>
        )}
        <Link className="author-link" to={authorPath(content.author)} aria-label={authorLabel}>
          {author.name}
        </Link>
      </span>
    </>
  );
}
