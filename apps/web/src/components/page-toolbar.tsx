import { createContext, useContext, useState } from 'react';
import type { ReactNode, RefObject } from 'react';
import { createPortal } from 'react-dom';
import { Button } from '@comfyshop/ui';
import { t } from '../app/i18n';

const ToolbarHost = createContext<HTMLDivElement | null | undefined>(undefined);

export function TabbedToolbar({
  navigation,
  actions,
  className,
  children,
}: {
  navigation: ReactNode;
  actions?: ReactNode;
  className?: string;
  children: ReactNode;
}) {
  const [host, setHost] = useState<HTMLDivElement | null>(null);
  return (
    <ToolbarHost.Provider value={host}>
      <div className={className ? `tabbed-toolbar ${className}` : 'tabbed-toolbar'}>
        {navigation}
        <div className="tabbed-toolbar-controls">
          <div className="tabbed-toolbar-tools" ref={setHost} />
          {actions}
        </div>
      </div>
      {children}
    </ToolbarHost.Provider>
  );
}

export function PageToolbar({
  className,
  standalone,
  children,
}: {
  className?: string;
  standalone?: boolean;
  children: ReactNode;
}) {
  const host = useContext(ToolbarHost);
  const content = (
    <div className={className ? `page-toolbar ${className}` : 'page-toolbar'}>{children}</div>
  );
  if (standalone || host === undefined) return content;
  return host && createPortal(content, host);
}

export function FilterToolbar({
  children,
  onClear,
  focusOnClear,
  standalone,
}: {
  children: ReactNode;
  onClear?: () => void;
  focusOnClear: RefObject<HTMLElement | null>;
  standalone?: boolean;
}) {
  return (
    <PageToolbar className="filter-toolbar" standalone={standalone}>
      {children}
      {onClear && (
        <Button
          onClick={() => {
            onClear();
            focusOnClear.current?.focus({ preventScroll: true });
          }}
        >
          {t('workspaceResults.clearFilters')}
        </Button>
      )}
    </PageToolbar>
  );
}
