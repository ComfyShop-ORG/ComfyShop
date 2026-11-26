/** 执行详情底部的发布提示：先公开工作流、选择成品，或发布完成。 */
import { t } from '../app/i18n.ts';
import { useState } from 'react';
import type { RefObject } from 'react';
import { Link } from 'react-router';
import type { Workflow } from '@comfyshop/api-client';
import { CheckIcon, Link2Icon } from '@radix-ui/react-icons';
import { Button } from '@comfyshop/ui';
import { CopyLink } from './copy-link';
import { StatusMark } from './status-mark';
import { PublishWorkflowButton } from '../features/workflows/publish-workflow-button';

export function ExecutionPublicationBar({
  draftWorkflow,
  selecting,
  chosenCount,
  published,
  publishedLink,
  worksPath,
  canStart,
  hintId,
  actionRef,
  onBegin,
  onCancel,
  onReview,
}: {
  /** 尚未公开的来源工作流。作品只能发布在已公开的工作流下。 */
  draftWorkflow: Workflow | undefined;
  selecting: boolean;
  chosenCount: number;
  /** 当前执行刚完成发布。 */
  published: boolean;
  /** 刚发布的作品的分享地址。 */
  publishedLink?: string;
  worksPath: string;
  canStart: boolean;
  /** 选择说明的元素 ID，成品列表通过它关联说明。 */
  hintId: string;
  actionRef: RefObject<HTMLButtonElement | null>;
  onBegin: () => void;
  onCancel: () => void;
  onReview: () => void;
}) {
  const [copied, setCopied] = useState<string>();
  return (
    <>
      {draftWorkflow && !selecting && (
        <div className="collection-actions work-publish-bar">
          <p>{t('executionPublicationBar.publishTheWorkflowBeforePublishingA')}</p>
          <PublishWorkflowButton
            workflow={draftWorkflow}
            disabled={!canStart}
            continueToWork={onBegin}
          />
        </div>
      )}
      {selecting && (
        <div className="collection-actions work-publish-bar">
          <div>
            <p id={hintId}>{t('executionPublicationBar.selectOutputsToPublish')}</p>
            <p className="form-hint" role="status">
              {t('executionPublicationBar.selected', chosenCount)}
            </p>
          </div>
          <div className="compact-dialog-footer">
            <Button size="small" variant="ghost" onClick={onCancel}>
              {t('executionPublicationBar.clearSelection')}
            </Button>
            <Button
              ref={actionRef}
              size="small"
              variant="primary"
              disabled={!chosenCount}
              onClick={onReview}
            >
              {t('executionPublicationBar.nextSetCover')}
            </Button>
          </div>
        </div>
      )}
      {published && (
        <div className="collection-actions work-publish-bar">
          <p className="publish-done" role="status">
            <StatusMark tone="success" />
            {t('executionPublicationBar.workPublishedVisitorsCanFindIt')}
          </p>
          <div className="compact-dialog-footer">
            {publishedLink && (
              <CopyLink
                href={publishedLink}
                title={t('executionPublicationBar.workLink')}
                shareTitle={t('executionPublicationBar.workLink')}
                onCopied={() => setCopied(publishedLink)}
              >
                {copied === publishedLink ? <CheckIcon /> : <Link2Icon />}
                {copied === publishedLink
                  ? t('executionPublicationBar.linkCopied')
                  : t('executionPublicationBar.copyWorkLink')}
              </CopyLink>
            )}
            <Button size="small" asChild>
              <Link to={worksPath}>{t('executionPublicationBar.viewMyWorks')}</Link>
            </Button>
          </div>
        </div>
      )}
    </>
  );
}
