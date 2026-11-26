import { locale } from '../app/language.ts';
import { t } from '../app/i18n.ts';
import { useRef, useState } from 'react';
import { skipToken, useQuery } from '@tanstack/react-query';
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router';
import { Component1Icon } from '@radix-ui/react-icons';
import { Button, Select } from '@comfyshop/ui';
import type { TaskFilter } from '../app/task-queries';
import { useTasks, useWorkspace } from '../app/use-workspace';
import { workspaceKey, workspacePath } from '../app/workspace-scope';
import { clearResultParams } from '../app/result-route';
import { cardThumbnail } from '../data/card-thumbnail';
import { durationLabel } from './generation-stage';
import type { Task, Workflow } from '../domain/types';
import { isTaskActive } from '../domain/types';
import type { ReplayAction } from '../domain/types';
import { TaskDetailsDialog } from './task-details';
import { EmptyState, PaginatedListFeedback } from './collection-status';
import { PageToolbar } from './page-toolbar';
import { CancelTaskButton, TaskState } from './task-state';
import { ListItem, ListPresence } from '../motion';

const taskFilters = [
  { value: 'all', label: t('taskList.allStatuses') },
  { value: 'active', label: t('taskList.active') },
  { value: 'succeeded', label: t('taskList.completed') },
  { value: 'failed', label: t('taskList.failed') },
  { value: 'cancelled', label: t('taskList.canceled') },
] as const;

function TaskThumbnail({ task }: { task: Task }) {
  const thumbnail = task.media && cardThumbnail(task.media, 48);
  return thumbnail ? (
    <img className="task-thumbnail" src={thumbnail.src} srcSet={thumbnail.srcSet} alt="" />
  ) : (
    <span className="task-thumbnail" aria-hidden="true">
      <Component1Icon />
    </span>
  );
}

export function TaskList({
  openWorkflow,
  onReplay,
  projectId,
}: {
  openWorkflow: (workflow: Workflow, source: HTMLElement) => void;
  onReplay: ReplayAction;
  projectId?: string;
}) {
  const [filter, setFilter] = useState<TaskFilter | 'all'>('all');
  const { history, activity, items } = useTasks(
    undefined,
    filter === 'all' ? undefined : filter,
    undefined,
    projectId,
  );
  const { api, state, workspaceScope } = useWorkspace();
  const navigate = useNavigate();
  const location = useLocation();
  const [params, setParams] = useSearchParams();
  const [error, setError] = useState('');
  const list = useRef<HTMLDivElement>(null);
  const statusFilter = useRef<HTMLButtonElement>(null);
  const [selected, setSelected] = useState<{
    task: Task;
    source: HTMLElement;
    tab: 'progress' | 'results';
  } | null>(null);
  const linkedId = params.get('task');
  const listedTask = items.find((task) => task.id === linkedId);
  const linked = useQuery({
    queryKey: ['tasks', 'detail', state.userId, linkedId, ...workspaceKey(workspaceScope)],
    enabled: !listedTask,
    queryFn: linkedId && state.userId ? ({ signal }) => api.task(linkedId, signal) : skipToken,
    retry: false,
  });
  const openedTask =
    selected?.task ??
    listedTask ??
    (!linked.isError && (!projectId || linked.data?.projectId === projectId)
      ? linked.data
      : undefined);
  function closeLinkedTask() {
    if ((location.state as { fromResult?: unknown } | null)?.fromResult === true) {
      void navigate(-1);
      return;
    }
    const next = new URLSearchParams(params);
    next.delete('task');
    next.delete('space');
    clearResultParams(next);
    setParams(next, { replace: true, preventScrollReset: true });
  }
  return (
    <>
      <PageToolbar>
        <Select
          ref={statusFilter}
          label={t('taskList.taskStatus')}
          options={taskFilters}
          value={filter}
          onValueChange={(value) => setFilter(value as TaskFilter | 'all')}
        />
      </PageToolbar>
      <div className="task-list" ref={list} tabIndex={-1}>
        <ListPresence>
          {items.map((task) => (
            <ListItem className="task-item" key={task.id}>
              <Button
                variant="ghost"
                className="task-open"
                onClick={(event) => {
                  void (async () => {
                    const origin = event.currentTarget;
                    try {
                      openWorkflow(await api.workflow(task.workflowId), origin);
                    } catch (error) {
                      setError(
                        error instanceof Error ? error.message : t('taskList.loadingFailed'),
                      );
                    }
                  })();
                }}
              >
                <TaskThumbnail task={task} />
                <span>
                  <strong id={`task-workflow-${task.id}`}>{task.workflowName}</strong>
                  <span className="muted">
                    {[
                      new Date(task.started).toLocaleString(locale),
                      task.executionCount > 1 && t('taskList.runs', task.executionCount),
                      task.machineName,
                      !isTaskActive(task.status) &&
                        task.status !== 'cancelled' &&
                        t('generationStage.elapsed2', durationLabel(task.updated - task.started)),
                    ]
                      .filter(Boolean)
                      .join(' · ')}
                  </span>
                </span>
              </Button>
              <div className="task-item-actions">
                <TaskState task={task} />
                <div className="task-item-buttons">
                  {task.status === 'succeeded' && (
                    <Button
                      variant="ghost"
                      size="small"
                      onClick={(event) =>
                        setSelected({ task, source: event.currentTarget, tab: 'results' })
                      }
                    >
                      {t('taskDetails.results')}
                    </Button>
                  )}
                  {isTaskActive(task.status) && <CancelTaskButton task={task} />}
                  <Button
                    size="small"
                    aria-describedby={`task-workflow-${task.id}`}
                    onClick={(event) =>
                      setSelected({ task, source: event.currentTarget, tab: 'progress' })
                    }
                  >
                    {t('taskDetails.taskDetails')}
                  </Button>
                </div>
              </div>
            </ListItem>
          ))}
        </ListPresence>
      </div>
      <PaginatedListFeedback
        query={history}
        fallbackErrorSource={activity}
        loadMoreClassName="task-load-more"
      >
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        {!history.isPending && !history.error && !activity.error && !items.length && (
          <EmptyState
            label={
              filter === 'all' ? t('taskList.noTasksYet') : t('taskList.noTasksMatchTheseFilters')
            }
            action={
              filter === 'all' && !projectId ? (
                <Button asChild size="small">
                  <Link to={workspacePath(workspaceScope, 'workflows')}>
                    {t('taskList.openMyWorkflows')}
                  </Link>
                </Button>
              ) : filter === 'all' ? undefined : (
                <Button
                  size="small"
                  onClick={() => {
                    setFilter('all');
                    statusFilter.current?.focus({ preventScroll: true });
                  }}
                >
                  {t('taskList.viewAllTasks')}
                </Button>
              )
            }
          />
        )}
      </PaginatedListFeedback>
      {linkedId && !openedTask && (
        <div className="inline-status" role={linked.isPending ? 'status' : 'alert'}>
          {linked.isPending
            ? t('common.loading')
            : (linked.error?.message ?? t('projects.unavailable'))}
          {!linked.isPending && (
            <>
              {linked.error && (
                <Button size="small" onClick={() => void linked.refetch()}>
                  {t('app.retry')}
                </Button>
              )}
              <Button size="small" onClick={closeLinkedTask}>
                {t('common.close')}
              </Button>
            </>
          )}
        </div>
      )}
      {openedTask && (
        <TaskDetailsDialog
          key={openedTask.id}
          task={openedTask}
          initialTab={selected?.tab}
          onClose={selected ? () => setSelected(null) : closeLinkedTask}
          onProjectChanged={(next) => {
            if (!projectId || projectId === next) return;
            if (selected) setSelected(null);
            else closeLinkedTask();
          }}
          restoreFocus={() => {
            const target = selected?.source.isConnected ? selected.source : list.current;
            target?.focus({ preventScroll: true });
          }}
          onReplay={(replay, source) => {
            setSelected(null);
            onReplay(replay, selected?.source ?? source);
          }}
        />
      )}
    </>
  );
}
