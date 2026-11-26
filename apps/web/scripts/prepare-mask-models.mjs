import { createHash, randomUUID } from 'node:crypto';
import { mkdir, readFile, rename, rm, writeFile } from 'node:fs/promises';

// Package the pinned Google models with the web app so workspaces can run inference offline.
const directory = new URL('../src/features/workflows/.mask-models/', import.meta.url);
const models = [
  {
    repo: 'MediaPipe-InteractiveSegmenter-MagicTouch',
    revision: '61de3ef0dcf18e1ad21636bb206439dff5cf516d',
    file: 'interactive_segmentation.task',
    sha256: '38431bc66b883404e8397f74c3579404315b9b52b04a46c6346fe906a7309b03',
  },
  {
    repo: 'MediaPipe-ImageSegmenter-Selfie-Multiclass',
    revision: 'c7b7e9e0f1e73c10a12114379077b5257e60c25c',
    file: 'selfie_multiclass_256x256.tflite',
    sha256: 'c6748b1253a99067ef71f7e26ca71096cd449baefa8f101900ea23016507e0e0',
  },
];

function checksum(bytes) {
  return createHash('sha256').update(bytes).digest('hex');
}

async function prepare({ repo, revision, file, sha256 }) {
  const destination = new URL(file, directory);
  const existing = await readFile(destination).catch((error) => {
    if (error.code !== 'ENOENT') throw error;
  });
  if (existing && checksum(existing) === sha256) return;
  const url = `https://huggingface.co/litert-community/${repo}/resolve/${revision}/${file}?download=true`;
  const response = await fetch(url, { signal: AbortSignal.timeout(180_000) });
  if (!response.ok) throw new Error(`Could not download ${file} (HTTP ${response.status})`);
  const bytes = Buffer.from(await response.arrayBuffer());
  if (checksum(bytes) !== sha256) throw new Error(`Checksum mismatch for ${file}`);
  const temporary = new URL(`${file}.${randomUUID()}.tmp`, directory);
  try {
    await writeFile(temporary, bytes);
    await rename(temporary, destination);
  } finally {
    await rm(temporary, { force: true });
  }
}

await mkdir(directory, { recursive: true });
await Promise.all(models.map(prepare));
