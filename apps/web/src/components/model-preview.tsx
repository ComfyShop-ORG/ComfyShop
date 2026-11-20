import { useEffect, useRef, useState } from 'react';
import {
  AmbientLight,
  Box3,
  DirectionalLight,
  LoadingManager,
  Mesh,
  PerspectiveCamera,
  Scene,
  Sphere,
  Texture,
  Vector3,
  WebGLRenderer,
} from 'three';
import type { BufferGeometry, Material, Object3D } from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { Button } from '@comfyshop/ui';

function disposeModel(model: Object3D) {
  const geometries = new Set<BufferGeometry>();
  const materials = new Set<Material>();
  const textures = new Set<Texture>();
  model.traverse((object) => {
    if (!(object instanceof Mesh)) return;
    const mesh = object as Mesh;
    geometries.add(mesh.geometry);
    for (const material of [mesh.material].flat()) materials.add(material);
  });
  for (const geometry of geometries) geometry.dispose();
  for (const material of materials) {
    for (const value of Object.values(material)) {
      if (value instanceof Texture) textures.add(value as Texture);
    }
    material.dispose();
  }
  for (const texture of textures) {
    if (typeof ImageBitmap !== 'undefined' && texture.image instanceof ImageBitmap) {
      texture.image.close();
    }
    texture.dispose();
  }
}

export default function ModelPreview({ src, name }: { src: string; name: string }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const controls = useRef<OrbitControls | null>(null);
  const [status, setStatus] = useState<'loading' | 'ready' | 'failed'>('loading');
  useEffect(() => {
    const element = canvas.current;
    if (!element) return;
    const controller = new AbortController();
    let teardown: (() => void) | undefined;

    async function preview(surface: HTMLCanvasElement) {
      const renderer = new WebGLRenderer({ canvas: surface, alpha: true, antialias: true });
      renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
      const scene = new Scene();
      const light = new DirectionalLight(undefined, 2);
      light.position.set(3, 5, 4);
      scene.add(new AmbientLight(undefined, 1.4), light);

      const camera = new PerspectiveCamera(42);
      const orbit = new OrbitControls(camera, surface);
      controls.current = orbit;
      orbit.listenToKeyEvents(surface);
      const render = () => renderer.render(scene, camera);
      const resize = () => {
        const width = Math.max(1, surface.clientWidth);
        const height = Math.max(1, surface.clientHeight);
        renderer.setSize(width, height, false);
        camera.aspect = width / height;
        camera.updateProjectionMatrix();
        render();
      };
      const observer = new ResizeObserver(resize);
      observer.observe(surface);
      orbit.addEventListener('change', render);
      teardown = () => {
        observer.disconnect();
        orbit.removeEventListener('change', render);
        orbit.dispose();
        controls.current = null;
        disposeModel(scene);
        renderer.dispose();
        renderer.forceContextLoss();
      };
      resize();

      const response = await fetch(src, { signal: controller.signal, credentials: 'same-origin' });
      if (!response.ok) throw new Error('读取模型失败');
      const manager = new LoadingManager();
      // 只加载 GLB 内嵌资源。模型文件中的地址不能发起额外请求。
      manager.setURLModifier((url) => {
        if (url.startsWith('blob:') || url.startsWith('data:')) return url;
        throw new Error('GLB 包含外部资源');
      });
      const gltf = await new GLTFLoader(manager).parseAsync(await response.arrayBuffer(), '');
      if (controller.signal.aborted) {
        disposeModel(gltf.scene);
        return;
      }
      const model = gltf.scene;
      scene.add(model);
      const sphere = new Box3().setFromObject(model).getBoundingSphere(new Sphere());
      if (!Number.isFinite(sphere.radius) || sphere.radius <= 0) throw new Error('模型尺寸无效');
      const vertical = (camera.fov * Math.PI) / 360;
      const horizontal = Math.atan(Math.tan(vertical) * camera.aspect);
      const distance = (sphere.radius * 1.15) / Math.sin(Math.min(vertical, horizontal));
      camera.near = distance / 1000;
      camera.far = distance * 100;
      camera.position.copy(sphere.center).add(new Vector3(1, 0.55, 1.1).setLength(distance));
      camera.updateProjectionMatrix();
      orbit.target.copy(sphere.center);
      orbit.minDistance = sphere.radius / 4;
      orbit.maxDistance = distance * 10;
      orbit.update();
      orbit.saveState();
      render();
      setStatus('ready');
    }

    void preview(element).catch(() => {
      if (controller.signal.aborted) return;
      teardown?.();
      teardown = undefined;
      setStatus('failed');
    });
    return () => {
      controller.abort();
      teardown?.();
    };
  }, [src]);

  return (
    <div className="model-preview" aria-busy={status === 'loading'}>
      <canvas ref={canvas} tabIndex={0} aria-label={name} hidden={status === 'failed'} />
      {status === 'loading' && <span role="status">正在读取模型</span>}
      {status === 'failed' && <span role="status">无法预览此模型，可下载原件查看</span>}
      {status === 'ready' && (
        <Button size="small" onClick={() => controls.current?.reset()}>
          重置视角
        </Button>
      )}
    </div>
  );
}
