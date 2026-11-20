import { useState } from 'react';

export function ProfileAvatar({
  name,
  src,
  className = 'avatar-small',
}: {
  name: string;
  src?: string | null;
  className?: string;
}) {
  const [failed, setFailed] = useState<string>();
  return (
    <span className={`profile-avatar ${className}`} aria-hidden="true">
      {src && src !== failed ? (
        <img src={src} alt="" onError={() => setFailed(src)} />
      ) : (
        [...name][0]?.toUpperCase()
      )}
    </span>
  );
}
