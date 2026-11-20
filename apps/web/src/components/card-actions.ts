import { createContext } from 'react';
import type { Workflow, WorkflowFilters } from '../domain/types';

export const CardActions = createContext<{
  openWorkflow: (workflow: Workflow, source: HTMLElement, filters?: WorkflowFilters) => void;
  favorite: (id: string, source: HTMLElement) => void;
}>({ openWorkflow: () => {}, favorite: () => {} });
