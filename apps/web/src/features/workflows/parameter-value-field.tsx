import {
  Checkbox,
  Field,
  Input,
  RadioGroup,
  RangeSlider,
  Select,
  Switch,
  TextArea,
} from '@comfyshop/ui';
import type { InputValue } from '@comfyshop/api-client';
import { unavailableChoice } from './parameter-layout';
import type { ParameterRow } from './parameter-layout';

export function ParameterValueField({
  field,
  id = `input-${field.id}`,
  help,
  value,
  issueId,
  disabled = false,
  onChange,
}: {
  field: ParameterRow;
  id?: string;
  help?: string;
  value: InputValue;
  issueId?: string;
  disabled?: boolean;
  onChange: (value: InputValue) => void;
}) {
  const mode = field.control && field.controls?.options.includes(field.control) && field.control;
  const detail = !field.primary ? field.nodeTitle : undefined;
  const slider = mode === 'slider' && field.controls?.slider;
  if (slider && typeof value === 'number') {
    const { minimum, maximum, step, scale } = slider;
    const position = Math.round(value * scale);
    if (
      position / scale === value &&
      position >= minimum &&
      position <= maximum &&
      (position - minimum) % step === 0
    ) {
      return (
        <RangeSlider
          id={id}
          label={field.label}
          detail={detail ? `${detail} · ${value}` : String(value)}
          help={help}
          disabled={disabled}
          min={minimum}
          max={maximum}
          step={step}
          value={position}
          thumbProps={{
            'aria-valuemin': minimum / scale,
            'aria-valuemax': maximum / scale,
            'aria-valuenow': value,
            'aria-invalid': issueId ? true : undefined,
            'aria-describedby': issueId,
          }}
          onValueChange={(next) => onChange(next / scale)}
        />
      );
    }
  }
  let control;
  if (field.kind === 'boolean') {
    const BooleanControl = mode === 'checkbox' ? Checkbox : Switch;
    control = (
      <BooleanControl
        id={id}
        disabled={disabled}
        checked={value === true}
        onCheckedChange={(checked) => onChange(checked === true)}
        aria-label={field.label}
      />
    );
  } else if (field.kind === 'choice') {
    const encode = (choice: InputValue) => JSON.stringify(choice);
    const labels = field.presentation?.choiceLabels ?? {};
    const options = field.choices.map((choice) => ({
      value: encode(choice),
      label:
        typeof choice === 'string' && Object.hasOwn(labels, choice)
          ? labels[choice]
          : String(choice),
      disabled: false,
    }));
    const selected = encode(value);
    if (!options.some((option) => option.value === selected))
      options.unshift({
        value: selected,
        label: `${value !== null && typeof value === 'object' ? '素材' : String(value)} · 不可用`,
        disabled: mode === 'radio',
      });
    const ChoiceControl = mode === 'radio' ? RadioGroup : Select;
    control = (
      <ChoiceControl
        id={id}
        label={field.label}
        disabled={disabled}
        aria-invalid={issueId ? true : undefined}
        aria-describedby={issueId}
        value={selected}
        onValueChange={(next) => onChange(JSON.parse(next) as InputValue)}
        options={options}
      />
    );
  } else if (field.kind === 'number' || field.kind === 'integer')
    control = (
      <Input
        id={id}
        disabled={disabled}
        type={field.integerAsString ? 'text' : 'number'}
        aria-invalid={issueId ? true : undefined}
        aria-describedby={issueId}
        inputMode={field.kind === 'integer' ? 'numeric' : 'decimal'}
        value={typeof value === 'number' || typeof value === 'string' ? value : ''}
        min={field.minimum ?? undefined}
        max={field.maximum ?? undefined}
        step={field.step ?? (field.kind === 'integer' ? 1 : 'any')}
        onChange={(event) =>
          onChange(
            field.integerAsString || event.target.value === ''
              ? event.target.value
              : Number(event.target.value),
          )
        }
      />
    );
  else if (
    mode === 'textarea' ||
    (mode === 'text' ? typeof value === 'string' && /[\r\n]/.test(value) : field.multiline)
  )
    control = (
      <TextArea
        id={id}
        disabled={disabled}
        value={typeof value === 'string' ? value : ''}
        onChange={(event) => onChange(event.target.value)}
      />
    );
  else
    control = (
      <Input
        id={id}
        disabled={disabled}
        value={typeof value === 'string' ? value : ''}
        onChange={(event) => onChange(event.target.value)}
      />
    );
  return (
    <Field
      label={field.label}
      htmlFor={mode === 'radio' ? undefined : id}
      detail={detail}
      help={help}
    >
      {control}
      {!issueId && unavailableChoice(field, value) && (
        <p className="form-error" role="alert">
          当前工作机没有这个选项，请改选可用项。
        </p>
      )}
    </Field>
  );
}
