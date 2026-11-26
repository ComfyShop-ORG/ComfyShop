import type { ReactNode } from 'react';
import { ChevronDownIcon } from '@radix-ui/react-icons';
import { Button, Collapsible } from '@comfyshop/ui';
import type { Workflow } from '@comfyshop/api-client';
import { t } from '../../app/i18n';
import { useMediaQuery } from '../../app/use-media-query';
import { AttributionLinks } from '../../components/publication-attribution';
import { workflowCategories } from '../../domain/workflow-categories';

export function WorkflowMetadata({
  workflow,
  actions,
}: {
  workflow: Workflow;
  actions?: ReactNode;
}) {
  const compactMetadata = useMediaQuery('(max-width: 700px), (max-height: 760px)');
  const author = workflow.authorProfile.nickname ?? workflow.author;
  const metadata = (
    <>
      <div className="author-line">
        <AttributionLinks
          content={workflow}
          showAvatar
          authorLabel={t('runForm.viewWorkflowsBy', author)}
        />
        <span className="meta-status">
          {workflow.published ? t('runForm.public') : t('runForm.private')}
        </span>
      </div>
      {workflow.description && <p className="workflow-description">{workflow.description}</p>}
      {workflow.published && (
        <dl className="workflow-stats">
          <div>
            <dt>{t('runForm.run')}</dt>
            <dd>{workflow.runs}</dd>
          </div>
          <div>
            <dt>{t('runForm.saveToFavorites')}</dt>
            <dd>{workflow.popularity}</dd>
          </div>
          <div>
            <dt>{t('runForm.version')}</dt>
            <dd>v{workflow.version}</dd>
          </div>
        </dl>
      )}
    </>
  );
  return (
    <div className="workflow-meta">
      <span className="eyebrow">
        {workflowCategories.find(({ value }) => value === workflow.category)?.label}
      </span>
      <h1>{workflow.name}</h1>
      {compactMetadata ? (
        <Collapsible.Root>
          <Collapsible.Trigger asChild>
            <Button size="small" variant="ghost" className="advanced-trigger">
              {t('runForm.workflowDetails')}
              <ChevronDownIcon />
            </Button>
          </Collapsible.Trigger>
          <Collapsible.Content>{metadata}</Collapsible.Content>
        </Collapsible.Root>
      ) : (
        metadata
      )}
      {actions && <div className="workflow-actions">{actions}</div>}
    </div>
  );
}
