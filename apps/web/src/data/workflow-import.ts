import { t } from '../app/i18n.ts';
import type { Workflow, WorkflowCreate } from '@comfyshop/api-client';

type Graph = Record<string, unknown>;

/** 输出视频的常见节点。图里出现它们时，导入的工作流默认归入视频分类。 */
const videoNodes = /video|animat|vhs_/i;
const modelOutputs = new Set(['Save3DAdvanced', 'SaveGLB']);
const audioOutputs = new Set(['SaveAudioAdvanced', 'SaveAudio', 'SaveAudioMP3', 'SaveAudioOpus']);

/**
 * 读取 ComfyUI 导出的 JSON 文件。
 * @throws {Error} 文件超过 5 MB、不是 JSON 或根节点不是对象。
 */
export async function readGraph(file: File): Promise<Graph> {
  if (file.size > 5 * 1024 * 1024) throw new Error(t('workflowImport.theFileCannotExceedMb'));
  let graph: unknown;
  try {
    graph = JSON.parse(await file.text());
  } catch {
    throw new Error(t('workflowImport.couldNotReadTheJson'));
  }
  if (!graph || typeof graph !== 'object' || Array.isArray(graph))
    throw new Error(t('workflowImport.invalidWorkflow'));
  return graph as Graph;
}

/** 编辑器保存的图以 `nodes` 数组列出节点，API 格式以节点 ID 为键。 */
export function isEditorGraph(graph: Graph) {
  return Array.isArray(graph.nodes);
}

function nodeTypes(graph: Graph): string[] {
  const nodes: unknown[] = isEditorGraph(graph) ? (graph.nodes as unknown[]) : Object.values(graph);
  return nodes.flatMap((node) => {
    if (!node || typeof node !== 'object') return [];
    const { type, class_type: classType } = node as { type?: unknown; class_type?: unknown };
    const name = typeof classType === 'string' ? classType : type;
    return typeof name === 'string' ? [name] : [];
  });
}

function suggestedCategory(graph: Graph): Workflow['category'] {
  const types = nodeTypes(graph);
  if (types.some((type) => modelOutputs.has(type))) return '3d';
  if (types.some((type) => audioOutputs.has(type))) return 'audio';
  return types.some((type) => videoNodes.test(type)) ? 'video' : 'image';
}

/** 以文件名为工作流名称。分类按输出节点推断，导入后可在工作流里修改。 */
export async function readWorkflow(file: File): Promise<WorkflowCreate> {
  const graph = await readGraph(file);
  const fileName = file.name.replace(/\.json$/i, '').slice(0, 120);
  if (graph.format === 'service') {
    return {
      name: typeof graph.name === 'string' ? graph.name : fileName,
      category:
        typeof graph.category === 'string' ? (graph.category as Workflow['category']) : 'image',
      graph,
    };
  }
  return {
    name: fileName,
    category: suggestedCategory(graph),
    graph,
  };
}
