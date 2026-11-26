import { FrameIcon } from '@radix-ui/react-icons';
import { Button, ToggleGroup } from '@comfyshop/ui';
import { t } from '../../app/i18n';

export const frameRatios = [
  [21, 9],
  [16, 9],
  [3, 2],
  [4, 3],
  [1, 1],
  [4, 5],
  [3, 4],
  [2, 3],
  [9, 16],
] as const;

export function FrameRatios({
  presets,
  ratio,
  disabled,
  onChange,
}: {
  presets: { value: string; label: string; aspect: number | null; disabled?: boolean }[];
  ratio: string;
  disabled?: boolean;
  onChange: (ratio: string) => void;
}) {
  return (
    <ToggleGroup.Root
      type="single"
      className="outpaint-ratios"
      aria-label={t('outpaint.aspectRatio')}
      value={ratio}
      disabled={disabled}
      onValueChange={onChange}
    >
      {presets.map(({ value, label, aspect, disabled: unavailable }) => (
        <ToggleGroup.Item key={value} value={value} disabled={unavailable} asChild>
          <Button variant="ghost" className="outpaint-ratio">
            {aspect ? (
              <span
                className="outpaint-ratio-shape"
                aria-hidden="true"
                style={{
                  width: `calc(var(--space-3) * ${Math.min(5 / 3, aspect)})`,
                  aspectRatio: aspect,
                }}
              />
            ) : (
              <FrameIcon aria-hidden="true" />
            )}
            {label}
          </Button>
        </ToggleGroup.Item>
      ))}
    </ToggleGroup.Root>
  );
}
