import { t } from '../../app/i18n.ts';
import type { ReactNode } from 'react';
import { DesktopIcon } from '@radix-ui/react-icons';
import type { Machine } from '@comfyshop/api-client';

type OperatingSystem = Machine['operatingSystem'];

const systems = {
  windows: {
    label: 'Windows',
    glyph: <path d="M2 2h9v9H2zM13 2h9v9h-9zM2 13h9v9H2zM13 13h9v9h-9z" />,
  },
  macos: {
    label: 'macOS',
    glyph: (
      <path d="M16.3 2c.1 1.3-.4 2.5-1.3 3.4-.7.8-1.7 1.2-2.8 1.2.1-1.1.5-2.2 1.3-3 .7-.8 1.7-1.4 2.8-1.6ZM12 8.2c1.6 0 2.7-1 4.5-.9 1.3.1 2.5.8 3.2 1.8-2.8 1.6-2.7 5.7.3 7.2-.6 1.7-2.4 5.5-4.4 5.5-1.1 0-1.9-.7-3.4-.7s-2.3.7-3.5.7c-2.1 0-4.6-4.3-5.2-7.3-.6-3.1.8-6.8 4-7.2 1.8-.2 3.1.9 4.5.9Z" />
    ),
  },
  linux: {
    label: 'Linux',
    glyph: (
      <g
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M7.8 9V7.3a4.2 4.2 0 0 1 8.4 0V9c1 1.1 3.1 3.4 3.1 6 0 1.4-.5 2.3-1.4 2.7l1.9 2.1c.5.6 0 1.4-.8 1.4l-4.5-.5a5.6 5.6 0 0 1-5.2 0l-4.5.5c-.8 0-1.3-.8-.8-1.4l2-2.1c-1-.4-1.5-1.3-1.5-2.7 0-2.6 2.2-4.9 3.3-6Z" />
        <path d="m10.3 9.2 1.7 1.2 1.7-1.2M8.7 18c-.5-.7-.7-1.5-.7-2.4 0-2.1 1.6-3.8 4-3.8s4 1.7 4 3.8c0 .9-.3 1.7-.7 2.4" />
        <path d="M10.5 7h.01m2.98 0h.01" strokeWidth="2" />
      </g>
    ),
  },
} satisfies Record<NonNullable<OperatingSystem>, { label: string; glyph: ReactNode }>;

export function machineSystemLabel(system: OperatingSystem) {
  return (system && systems[system]?.label) || t('machineSystem.unknownSystem');
}

export function MachineSystemIcon({ system }: { system: OperatingSystem }) {
  const glyph = system && systems[system]?.glyph;
  const label = machineSystemLabel(system);
  return (
    <span className="machine-icon" role="img" aria-label={label} title={label}>
      {glyph ? (
        <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
          {glyph}
        </svg>
      ) : (
        <DesktopIcon aria-hidden="true" />
      )}
    </span>
  );
}
