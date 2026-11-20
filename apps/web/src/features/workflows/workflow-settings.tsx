/** 作者修改工作流的名称和分类，或上传新的工作流文件作为下一个草稿版本。 */
import { useId, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Pencil1Icon, UploadIcon } from '@radix-ui/react-icons';
import type { Workflow } from '@comfyshop/api-client';
import {
  Button,
  Dialog,
  DialogClose,
  DialogContent,
  Field,
  FileInput,
  IconButton,
  Input,
  Select,
  TextArea,
} from '@comfyshop/ui';
import { useWorkspace } from '../../app/use-workspace';
import { useAction } from '../../components/use-action';
import { isEditorGraph, readGraph } from '../../data/workflow-import';

export const workflowCategories = [
  { value: 'image', label: '图像' },
  { value: 'video', label: '视频' },
  { value: 'tool', label: '工具' },
] as const;

export function WorkflowSettings({
  workflow,
  disabled,
  notify,
}: {
  workflow: Workflow;
  disabled?: boolean;
  notify: (message: string) => void;
}) {
  const { api } = useWorkspace();
  const queries = useQueryClient();
  const id = useId();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState(workflow.name);
  const [category, setCategory] = useState(workflow.category);
  const [description, setDescription] = useState(workflow.description);
  const [file, setFile] = useState<{ name: string; graph: Record<string, unknown> }>();
  const [fileError, setFileError] = useState('');
  const { busy, error, run } = useAction('保存失败');
  const changed =
    name.trim() !== workflow.name ||
    category !== workflow.category ||
    description.trim() !== workflow.description ||
    !!file;
  return (
    <Dialog.Root
      open={open}
      onOpenChange={(next) => {
        if (busy) return;
        if (next) {
          setName(workflow.name);
          setCategory(workflow.category);
          setDescription(workflow.description);
          setFile(undefined);
          setFileError('');
        }
        setOpen(next);
      }}
    >
      <Dialog.Trigger asChild>
        <IconButton label="编辑工作流" disabled={disabled}>
          <Pencil1Icon />
        </IconButton>
      </Dialog.Trigger>
      <DialogContent compact className="publish-dialog">
        <div className="compact-dialog-heading">
          <Dialog.Title>编辑工作流</Dialog.Title>
          <DialogClose disabled={busy} />
        </div>
        <form
          className="publish-form"
          onSubmit={(event) => {
            event.preventDefault();
            if (!name.trim() || !changed) return;
            void run(async () => {
              await api.updateWorkflow(workflow.id, {
                name: name.trim(),
                category,
                description: description.trim(),
                ...(file && { graph: file.graph }),
              });
              await Promise.all([
                queries.invalidateQueries({ queryKey: ['workflows'] }),
                queries.invalidateQueries({ queryKey: ['workflow-form'] }),
              ]);
              setOpen(false);
              notify(file ? '已保存为新版本' : '已保存');
            });
          }}
        >
          <Field label="名称" htmlFor={id + '-name'}>
            <Input
              id={id + '-name'}
              value={name}
              maxLength={120}
              required
              disabled={busy}
              onChange={(event) => setName(event.target.value)}
            />
          </Field>
          <Field label="分类" htmlFor={id + '-category'}>
            <Select
              id={id + '-category'}
              label="分类"
              value={category}
              disabled={busy}
              onValueChange={(value) => setCategory(value as Workflow['category'])}
              options={workflowCategories}
            />
          </Field>
          <Field label="简介" htmlFor={id + '-description'} detail={`${description.length} / 2000`}>
            <TextArea
              id={id + '-description'}
              value={description}
              maxLength={2000}
              disabled={busy}
              placeholder="这个工作流做什么，需要准备哪些素材"
              onChange={(event) => setDescription(event.target.value)}
            />
          </Field>
          <Field
            label="工作流文件"
            htmlFor={id + '-file'}
            detail={file ? file.name : `当前 v${workflow.version}`}
          >
            <FileInput
              id={id + '-file'}
              accept=".json,application/json"
              disabled={busy}
              onChange={(event) => {
                const input = event.currentTarget;
                void (async () => {
                  const picked = input.files?.[0];
                  input.value = '';
                  if (!picked) return;
                  try {
                    setFile({ name: picked.name, graph: await readGraph(picked) });
                    setFileError('');
                  } catch (error) {
                    setFile(undefined);
                    setFileError(error instanceof Error ? error.message : '无法读取文件');
                  }
                })();
              }}
            >
              <UploadIcon />
              上传新版本
            </FileInput>
            <p className="form-hint">
              {file && isEditorGraph(file.graph)
                ? '这是编辑器格式，可以保存，运行需要在 ComfyUI 导出的 API 格式。'
                : '新文件保存为下一个版本，已发布的版本和历史结果不受影响。'}
            </p>
          </Field>
          {(fileError || error) && (
            <p className="form-error" role="alert">
              {fileError || error}
            </p>
          )}
          <div className="compact-dialog-footer">
            <Dialog.Close asChild>
              <Button disabled={busy}>取消</Button>
            </Dialog.Close>
            <Button type="submit" variant="primary" disabled={busy || !name.trim() || !changed}>
              {busy ? '保存中' : '保存'}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog.Root>
  );
}
