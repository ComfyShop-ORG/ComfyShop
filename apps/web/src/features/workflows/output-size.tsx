import { useState } from 'react';
import type { ReactNode } from 'react';
import { Field, Select } from '@comfyshop/ui';
import type { InputValue } from '@comfyshop/api-client';
import { ratioDimensions } from './output-specification';

export function RatioSizePreview({
  ratio,
  megapixels,
  multiple,
  roundTo,
  latentMultiple,
  modelMultiple,
}: {
  ratio: InputValue;
  megapixels: InputValue;
  multiple: InputValue;
  roundTo?: number | null;
  latentMultiple?: number | null;
  modelMultiple?: number | null;
}) {
  const dimensions = ratioDimensions(
    ratio,
    megapixels,
    multiple,
    roundTo,
    latentMultiple,
    modelMultiple,
  );
  return (
    dimensions && (
      <p className="form-hint" role="status">
        预计尺寸 {dimensions[0]} × {dimensions[1]} 像素
      </p>
    )
  );
}

export function AutomaticSizeFields({
  id,
  width,
  height,
  usesReference,
  onAutomatic,
  children,
}: {
  id: string;
  width: InputValue;
  height: InputValue;
  usesReference: boolean;
  onAutomatic: () => void;
  children: ReactNode;
}) {
  const [editing, setEditing] = useState(false);
  const automatic = width === 0 && height === 0 && !editing;
  const label = usesReference ? '按原图比例自动选尺寸' : '自动 · 1024 × 1024';
  const explicit =
    typeof width === 'number' &&
    typeof height === 'number' &&
    width > 0 &&
    height > 0 &&
    width % 16 === 0 &&
    height % 16 === 0;
  return (
    <div className="output-size-fields">
      <Field label="成品尺寸" htmlFor={id}>
        <Select
          id={id}
          label="成品尺寸"
          options={[
            { value: 'auto', label },
            { value: 'custom', label: '自定义宽高' },
          ]}
          value={automatic ? 'auto' : 'custom'}
          onValueChange={(mode) => {
            setEditing(mode === 'custom');
            if (mode === 'auto') onAutomatic();
          }}
        />
      </Field>
      {!automatic && (
        <>
          {children}
          <p className="form-hint" role="status">
            {explicit
              ? `预计尺寸 ${width} × ${height} 像素`
              : '宽或高填 0 时，该边由工作流自动确定。'}
          </p>
        </>
      )}
    </div>
  );
}
