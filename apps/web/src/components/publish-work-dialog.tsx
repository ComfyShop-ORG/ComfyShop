/** 把一次成功执行里选定的成品发布为作品，并从中选择作品封面。 */
import { useRef, useState } from 'react';
import { durationLabel } from './generation-stage';
import type { Artifact, Execution, Work } from '@comfyshop/api-client';
import {
  Button,
  Dialog,
  DialogClose,
  DialogContent,
  Field,
  Input,
  Switch,
  TextArea,
} from '@comfyshop/ui';
import { useWorkspace } from '../app/use-workspace';
import { createRequestId } from '../data/request-id';
import { AssetGallery } from './artifact-collection';
import { useAction } from './use-action';
import { useDialogFocus } from './use-dialog-focus';

export function PublishWorkDialog({
  execution,
  assets,
  returnToSelection,
  restoreFocus,
  onClose,
  onPublished,
}: {
  execution: Execution;
  assets: Artifact[];
  returnToSelection: boolean;
  restoreFocus: () => void;
  onClose: () => void;
  onPublished: (work: Work) => void;
}) {
  const { api } = useWorkspace();
  const [title, setTitle] = useState(execution.workflowName);
  const [cover, setCover] = useState(
    assets.find((asset) => asset.id === execution.coverArtifactId)?.id ?? assets[0].id,
  );
  const [share, setShare] = useState(false);
  const [description, setDescription] = useState('');
  const { busy, error, run } = useAction('发布失败');
  const intent = useRef<{ fingerprint: string; id: string } | null>(null);
  const [scrollRoot, setScrollRoot] = useState<HTMLDivElement | null>(null);
  const { titleRef, focusProps } = useDialogFocus(restoreFocus);
  return (
    <Dialog.Root
      open
      onOpenChange={(open) => {
        if (!open && !busy) onClose();
      }}
    >
      <DialogContent compact className="publish-dialog" {...focusProps}>
        <div className="compact-dialog-heading">
          <Dialog.Title ref={titleRef} tabIndex={-1}>
            发布作品
          </Dialog.Title>
          <DialogClose disabled={busy} />
        </div>
        <form
          className="publish-form"
          onSubmit={(event) => {
            event.preventDefault();
            if (!title.trim()) return;
            const body = {
              executionId: execution.id,
              artifactIds: assets.map((asset) => asset.id),
              coverArtifactId: cover,
              // 封面仍是结果组的封面视频时，沿用在结果里为它选定的画面。
              coverFrameMs:
                cover === execution.coverArtifactId ? (execution.coverFrameMs ?? null) : null,
              title: title.trim(),
              shareParameters: share,
              description: description.trim(),
            };
            void run(async () => {
              // 内容不变的重试沿用同一个发布编号，平台据此返回已保存的作品。
              const fingerprint = JSON.stringify(body);
              if (intent.current?.fingerprint !== fingerprint)
                intent.current = { fingerprint, id: createRequestId() };
              onPublished(await api.publishWork({ id: intent.current.id, ...body }));
            });
          }}
        >
          <Field label="名称" htmlFor={`work-title-${execution.id}`}>
            <Input
              id={`work-title-${execution.id}`}
              value={title}
              maxLength={120}
              required
              onChange={(event) => setTitle(event.target.value)}
            />
          </Field>
          <Field
            label="说明"
            htmlFor={`work-description-${execution.id}`}
            detail={`${description.length} / 1000`}
          >
            <TextArea
              id={`work-description-${execution.id}`}
              value={description}
              maxLength={1000}
              placeholder="可选，随作品公开"
              onChange={(event) => setDescription(event.target.value)}
            />
          </Field>
          <div className="form-section-heading">
            <span>{assets.length > 1 ? '选择作品封面' : '作品封面'}</span>
            <span>公开 {assets.length} 份成品</span>
          </div>
          <div className="publish-media-scroll" ref={setScrollRoot}>
            <AssetGallery
              items={assets}
              onOpen={(asset) => setCover(asset.id)}
              selected={new Set([cover])}
              resetKey={`publish:${execution.id}`}
              scrollRoot={scrollRoot}
            />
          </div>
          {cover === execution.coverArtifactId && !!execution.coverFrameMs && (
            <p className="form-hint">
              封面使用在结果里为这个视频选定的画面（{durationLabel(execution.coverFrameMs)}）。
            </p>
          )}
          <Field label="公开参数" htmlFor={`share-parameters-${execution.id}`}>
            <Switch
              id={`share-parameters-${execution.id}`}
              checked={share}
              onCheckedChange={setShare}
            />
          </Field>
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          <div className="compact-dialog-footer">
            <Dialog.Close asChild>
              <Button disabled={busy}>{returnToSelection ? '返回选择' : '取消'}</Button>
            </Dialog.Close>
            <Button type="submit" variant="primary" disabled={busy || !title.trim()}>
              {busy ? '发布中' : '发布作品'}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog.Root>
  );
}
