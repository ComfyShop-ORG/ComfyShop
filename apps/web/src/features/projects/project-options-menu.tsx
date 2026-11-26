import type { ReactNode } from 'react';
import { CheckIcon } from '@radix-ui/react-icons';
import { DropdownMenu } from '@comfyshop/ui';
import type { Project } from '@comfyshop/api-client';
import { t } from '../../app/i18n';
import { useProjectPages } from './project-queries';

type ProjectOption = Pick<Project, 'id' | 'name'>;

export function useProjectOptions(open: boolean, archived = false) {
  const query = useProjectPages({ enabled: open, archived });
  const projects = query.data?.pages.flatMap((page) => page.items) ?? [];
  return { query, projects };
}

export function ProjectOptionsMenu({
  query,
  projects,
  label,
  pinned,
  value,
  onValueChange,
  onCloseAutoFocus,
  allowNone = false,
  children,
}: ReturnType<typeof useProjectOptions> & {
  label: string;
  pinned?: ProjectOption;
  value: string;
  onValueChange: (value: string) => void;
  onCloseAutoFocus?: (event: Event) => void;
  allowNone?: boolean;
  children?: ReactNode;
}) {
  const options: ProjectOption[] = pinned
    ? [pinned, ...projects.filter(({ id }) => id !== pinned.id)]
    : [...projects];
  if (allowNone) options.unshift({ id: 'none', name: t('projects.none') });
  const loadMore = () => query.fetchNextPage({ cancelRefetch: false });

  return (
    <DropdownMenu.Portal>
      <DropdownMenu.Content
        className={allowNone ? 'ui-menu project-menu project-menu--field' : 'ui-menu project-menu'}
        aria-label={label}
        aria-labelledby={undefined}
        align="start"
        sideOffset={allowNone ? 4 : 8}
        collisionPadding={12}
        onCloseAutoFocus={onCloseAutoFocus}
        onScroll={(event) => {
          const { scrollTop, scrollHeight, clientHeight } = event.currentTarget;
          if (
            query.hasNextPage &&
            !query.isFetching &&
            !query.error &&
            scrollHeight - scrollTop <= clientHeight * 1.5
          )
            void loadMore();
        }}
      >
        <DropdownMenu.RadioGroup value={value} onValueChange={onValueChange}>
          {options.map(({ id, name }) => (
            <DropdownMenu.RadioItem className="ui-menu-item" key={id} value={id}>
              <span>{name}</span>
              <DropdownMenu.ItemIndicator>
                <CheckIcon aria-hidden="true" />
              </DropdownMenu.ItemIndicator>
            </DropdownMenu.RadioItem>
          ))}
        </DropdownMenu.RadioGroup>
        {(query.hasNextPage || query.error) && (
          <DropdownMenu.Item
            className="ui-menu-item"
            disabled={query.isFetching}
            onSelect={(event) => {
              event.preventDefault();
              if (query.error && !query.isFetchNextPageError)
                void query.refetch({ cancelRefetch: false });
              else void loadMore();
            }}
          >
            {t(
              query.error ? 'app.retry' : query.isFetching ? 'common.loading' : 'taskList.loadMore',
            )}
          </DropdownMenu.Item>
        )}
        {query.isPending && !query.error && (
          <div className="ui-menu-item muted" role="status">
            {t('common.loading')}
          </div>
        )}
        {children}
      </DropdownMenu.Content>
    </DropdownMenu.Portal>
  );
}
