import { createContext } from 'react';
import type { ReactNode } from 'react';
import type { Workflow, WorkflowFilters } from '../domain/types';

export const CardActions = createContext<{
  openWorkflow: (workflow: Workflow, source: HTMLElement, filters?: WorkflowFilters) => void;
  favorite: (workflow: Workflow, source: HTMLElement) => void;
  /** 列表可提供自己的操作，null 隐藏卡片操作。 */
  workflowAction?: ((workflow: Workflow) => ReactNode) | null;
}>({ openWorkflow: () => {}, favorite: () => {} });
