import { useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Link, useOutletContext } from 'react-router';
import { Component1Icon } from '@radix-ui/react-icons';
import { Button, ToggleGroup } from '@comfyshop/ui';
import type { TaskFilter } from '../app/task-queries';
import { useMachines, useTasks, useWorkspace } from '../app/use-workspace';
import { cardThumbnail } from '../data/card-thumbnail';
import { durationLabel } from './generation-stage';
import type { Task, Workflow } from '../domain/types';
import type { ReplayAction } from '../domain/types';
import { TaskDetailsDialog } from './task-details';
import { EmptyState } from './collection-status';
import { CancelTaskButton, TaskState } from './task-state';
import { ActiveMark, ListItem, ListPresence } from '../motion';

const taskFilters = [
  { value: 'all', label: '全部' },
  { value: 'active', label: '进行中' },
  { value: 'succeeded', label: '已完成' },
  { value: 'failed', label: '失败' },
  { value: 'cancelled', label: '已取消' },
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
}: {
  openWorkflow: (workflow: Workflow, source: HTMLElement) => void;
  onReplay: ReplayAction;
}) {
  const [filter, setFilter] = useState<TaskFilter | 'all'>('all');
  const { history, activity, items } = useTasks(undefined, filter === 'all' ? undefined : filter);
  const machines = useMachines();
  const machineName = (id: string | null) =>
    machines.data?.items.find((machine) => machine.id === id)?.name;
  const { api } = useWorkspace();
  const [error, setError] = useState('');
  const list = useRef<HTMLDivElement>(null);
  const allFilter = useRef<HTMLButtonElement>(null);
  const [selected, setSelected] = useState<{
    task: Task;
    source: HTMLElement;
    tab: 'progress' | 'results';
  } | null>(null);
  const loadError = history.error ?? activity.error;
  // 状态筛选显示在「我的」标签栏右侧，由页面提供位置。
  const toolbarSlot = useOutletContext<HTMLElement | null>();
  const filters = (
    <ToggleGroup.Root
      className="filter-group"
      type="single"
      value={filter}
      onValueChange={(value) => {
        if (value) setFilter(value as TaskFilter | 'all');
      }}
      aria-label="任务状态"
    >
      {taskFilters.map((item) => (
        <ToggleGroup.Item key={item.value} value={item.value} asChild>
          <Button ref={item.value === 'all' ? allFilter : undefined} size="small" variant="ghost">
            {item.value === filter && <ActiveMark group="task-filter" />}
            {item.label}
          </Button>
        </ToggleGroup.Item>
      ))}
    </ToggleGroup.Root>
  );
  return (
    <>
      {toolbarSlot && createPortal(filters, toolbarSlot)}
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
                      setError(error instanceof Error ? error.message : '加载失败');
                    }
                  })();
                }}
              >
                <TaskThumbnail task={task} />
                <span>
                  <strong id={`task-workflow-${task.id}`}>{task.workflowName}</strong>
                  <span className="muted">
                    {[
                      new Date(task.started).toLocaleString('zh-CN'),
                      task.executionCount > 1 && `${task.executionCount} 次执行`,
                      machineName(task.machineId),
                      task.status !== 'queued' &&
                        task.status !== 'running' &&
                        task.status !== 'cancelled' &&
                        `用时 ${durationLabel(task.updated - task.started)}`,
                    ]
                      .filter(Boolean)
                      .join(' · ')}
                  </span>
                </span>
              </Button>
              <div className="task-item-actions">
                <TaskState task={task} />
                {task.status === 'succeeded' && (
                  <Button
                    variant="ghost"
                    size="small"
                    onClick={(event) =>
                      setSelected({ task, source: event.currentTarget, tab: 'results' })
                    }
                  >
                    结果
                  </Button>
                )}
                {(task.status === 'queued' || task.status === 'running') && (
                  <CancelTaskButton task={task} />
                )}
                <Button
                  size="small"
                  aria-describedby={`task-workflow-${task.id}`}
                  onClick={(event) =>
                    setSelected({ task, source: event.currentTarget, tab: 'progress' })
                  }
                >
                  任务详情
                </Button>
              </div>
            </ListItem>
          ))}
        </ListPresence>
      </div>
      {loadError && (
        <div className="inline-status" role="alert">
          {loadError.message}
          <Button size="small" onClick={() => void (history.error ? history : activity).refetch()}>
            重试
          </Button>
        </div>
      )}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {!history.isPending && !loadError && !items.length && (
        <EmptyState
          label={filter === 'all' ? '暂无任务' : '没有符合筛选的任务'}
          action={
            filter === 'all' ? (
              <Button asChild size="small">
                <Link to="/workspace/workflows">打开我的工作流</Link>
              </Button>
            ) : (
              <Button
                size="small"
                onClick={() => {
                  setFilter('all');
                  // 焦点落到已选中的「全部」筛选，读屏可以听到当前状态。
                  (allFilter.current ?? list.current)?.focus({ preventScroll: true });
                }}
              >
                查看全部任务
              </Button>
            )
          }
        />
      )}
      {history.hasNextPage && (
        <div className="load-more">
          <Button
            size="small"
            disabled={history.isFetching}
            onClick={() => void history.fetchNextPage({ cancelRefetch: false })}
          >
            加载更多
          </Button>
        </div>
      )}
      {selected && (
        <TaskDetailsDialog
          task={selected.task}
          initialTab={selected.tab}
          onClose={() => setSelected(null)}
          restoreFocus={() => {
            const target = selected.source.isConnected ? selected.source : list.current;
            target?.focus({ preventScroll: true });
          }}
          onReplay={(replay) => {
            setSelected(null);
            onReplay(replay, selected.source);
          }}
        />
      )}
    </>
  );
}
