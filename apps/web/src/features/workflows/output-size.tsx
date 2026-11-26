import { t } from '../../app/i18n.ts';
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
        {t('outputSize.estimatedSizePixels', dimensions[0], dimensions[1])}
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
  const label = usesReference
    ? t('outputSize.automaticSizeFromSourceAspectRatio')
    : t('outputSize.auto');
  const explicit =
    typeof width === 'number' &&
    typeof height === 'number' &&
    width > 0 &&
    height > 0 &&
    width % 16 === 0 &&
    height % 16 === 0;
  return (
    <div className="output-size-fields">
      <Field label={t('outputSize.outputSize')} htmlFor={id}>
        <Select
          id={id}
          label={t('outputSize.outputSize')}
          options={[
            { value: 'auto', label },
            { value: 'custom', label: t('outputSize.customDimensions') },
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
              ? t('outputSize.estimatedSizePixels', width, height)
              : t('outputSize.setEitherDimensionToToLet')}
          </p>
        </>
      )}
    </div>
  );
}
