/** 共享界面控件，以原生表单元素和 Radix 组合提供样式、键盘行为及焦点管理。 */
import { forwardRef, useId, useState } from 'react';
import type {
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  TextareaHTMLAttributes,
  ComponentPropsWithoutRef,
  ReactNode,
} from 'react';
import {
  AlertDialog,
  Dialog,
  Tabs,
  Select as SelectPrimitive,
  Slider,
  Checkbox as CheckboxPrimitive,
  RadioGroup as RadioGroupPrimitive,
  Collapsible,
  ToggleGroup,
  Tooltip,
  Toast,
  DropdownMenu,
  Popover,
  Progress,
  Slot,
  Switch as SwitchPrimitive,
  VisuallyHidden,
} from 'radix-ui';
import {
  CheckIcon,
  ChevronDownIcon,
  Cross2Icon,
  QuestionMarkCircledIcon,
} from '@radix-ui/react-icons';

import brandMark from '@comfyshop/tokens/brand/comfyshop-logo.svg?no-inline';
import brandWordmark from '@comfyshop/tokens/brand/comfyshop-wordmark.svg?no-inline';

export { AlertDialog, Dialog, Tabs, Collapsible, ToggleGroup, Tooltip, Toast, DropdownMenu };
/** @public Intentionally retained shared primitive. */
export { VisuallyHidden };
const cx = (...names: Array<string | false | undefined>) => names.filter(Boolean).join(' ');

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  size?: 'normal' | 'small';
  asChild?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = 'secondary', size = 'normal', asChild, className, type = 'button', ...props },
  ref,
) {
  const Element = asChild ? Slot.Root : 'button';
  return (
    <Element
      ref={ref}
      type={asChild ? undefined : type}
      className={cx(
        'ui-button',
        `ui-button--${variant}`,
        size === 'small' && 'ui-button--small',
        className,
      )}
      {...props}
    />
  );
});

export const IconButton = forwardRef<
  HTMLButtonElement,
  ButtonProps & { label: string; tooltip?: string }
>(function IconButton({ label, tooltip = label, className, ...props }, ref) {
  return (
    <Tooltip.Root>
      <Tooltip.Trigger
        asChild
        onFocus={(event) => {
          // 弹框打开和关闭时会自动移动焦点。鼠标操作沿用悬停触发提示。
          if (event.currentTarget.closest('[data-pointer-focus]')) event.preventDefault();
        }}
      >
        <Button
          ref={ref}
          variant="ghost"
          aria-label={label}
          className={cx('ui-icon-button', className)}
          {...props}
        />
      </Tooltip.Trigger>
      <Tooltip.Portal>
        <Tooltip.Content className="ui-tooltip" sideOffset={8}>
          {tooltip}
        </Tooltip.Content>
      </Tooltip.Portal>
    </Tooltip.Root>
  );
});

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  function Input({ className, ...props }, ref) {
    return <input ref={ref} className={cx('ui-input', className)} {...props} />;
  },
);

export const TextArea = forwardRef<
  HTMLTextAreaElement,
  TextareaHTMLAttributes<HTMLTextAreaElement>
>(function TextArea({ className, ...props }, ref) {
  return <textarea ref={ref} className={cx('ui-input', 'ui-textarea', className)} {...props} />;
});

/**
 * 字段名旁的问号。点击或轻触打开说明，触屏同样可用；鼠标悬停和键盘聚焦也会打开。
 * 说明同时作为按钮的描述提供给读屏软件。打开和关闭都不移动焦点，划过问号不会打断输入。
 */
function FieldHelp({ label, help }: { label: string; help: string }) {
  const [open, setOpen] = useState(false);
  // 由悬停或键盘聚焦打开时为真：随后的点击保持打开，移开或失焦时随之关闭。
  const [passive, setPassive] = useState(false);
  const descriptionId = useId();
  function show() {
    if (open) return;
    setPassive(true);
    setOpen(true);
  }
  function hide() {
    if (!passive) return;
    setPassive(false);
    setOpen(false);
  }
  return (
    <Popover.Root
      open={open}
      onOpenChange={(next) => {
        setPassive(false);
        setOpen(next);
      }}
    >
      <Popover.Trigger asChild>
        <Button
          variant="ghost"
          aria-label={`${label}提示`}
          aria-describedby={descriptionId}
          className="ui-icon-button ui-field-help"
          onPointerEnter={(event) => {
            if (event.pointerType === 'mouse') show();
          }}
          onPointerLeave={(event) => {
            if (event.pointerType === 'mouse') hide();
          }}
          onFocus={(event) => {
            if (event.currentTarget.matches(':focus-visible')) show();
          }}
          onBlur={hide}
          onClick={(event) => {
            if (!passive) return;
            event.preventDefault();
            setPassive(false);
          }}
        >
          <QuestionMarkCircledIcon />
        </Button>
      </Popover.Trigger>
      <VisuallyHidden.Root id={descriptionId}>{help}</VisuallyHidden.Root>
      <Popover.Portal>
        <Popover.Content
          // 只显示文字说明，不是需要操作的弹层：不算作打开的弹框，也不抢焦点。
          role="tooltip"
          className="ui-tooltip ui-help"
          sideOffset={8}
          // 与页面两侧的留白一致，窄屏上不贴着屏幕边缘。
          collisionPadding={16}
          onOpenAutoFocus={(event) => event.preventDefault()}
          onCloseAutoFocus={(event) => event.preventDefault()}
        >
          {help}
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}

export function Field({
  label,
  htmlFor,
  children,
  detail,
  help,
}: {
  label: string;
  htmlFor?: string;
  children: ReactNode;
  detail?: ReactNode;
  help?: string;
}) {
  return (
    <div className="ui-field">
      <div className="ui-field-heading">
        {help ? (
          <div className="ui-field-label">
            <label htmlFor={htmlFor}>{label}</label>
            <FieldHelp label={label} help={help} />
          </div>
        ) : (
          <label htmlFor={htmlFor}>{label}</label>
        )}
        {detail && <span>{detail}</span>}
      </div>
      {children}
    </div>
  );
}

export const FileInput = forwardRef<
  HTMLInputElement,
  Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> & { children: ReactNode }
>(function FileInput({ children, className, ...props }, ref) {
  // 文件拖到控件上方时高亮。放下后由原生文件输入接收，触发同一个 onChange。
  const [dragging, setDragging] = useState(false);
  return (
    <label
      className={cx('ui-file', className)}
      data-dragging={dragging}
      onDragEnter={() => setDragging(true)}
      onDragLeave={() => setDragging(false)}
      onDrop={() => setDragging(false)}
    >
      <input {...props} type="file" ref={ref} />
      {children}
    </label>
  );
});

/** 统一弹框遮罩与内容层。嵌套弹框的遮罩盖住前一层弹框。 */
export const DialogContent = forwardRef<
  HTMLDivElement,
  ComponentPropsWithoutRef<typeof Dialog.Content> & { compact?: boolean }
>(function DialogContent({ className, children, compact, ...props }, ref) {
  return (
    <Dialog.Portal>
      <Dialog.Overlay className="ui-overlay" />
      <Dialog.Content
        ref={ref}
        aria-describedby={undefined}
        className={cx('ui-dialog', compact && 'ui-dialog--compact', className)}
        {...props}
      >
        {children}
      </Dialog.Content>
    </Dialog.Portal>
  );
});

export const DialogClose = forwardRef<HTMLButtonElement, ButtonProps>(function DialogClose(
  { className, ...props },
  ref,
) {
  return (
    <Dialog.Close asChild>
      <IconButton ref={ref} label="关闭" className={className} {...props}>
        <Cross2Icon />
      </IconButton>
    </Dialog.Close>
  );
});

export const AlertDialogContent = forwardRef<
  HTMLDivElement,
  ComponentPropsWithoutRef<typeof AlertDialog.Content>
>(function AlertDialogContent({ className, children, ...props }, ref) {
  return (
    <AlertDialog.Portal>
      <AlertDialog.Overlay className="ui-overlay" />
      <AlertDialog.Content
        ref={ref}
        className={cx('ui-dialog', 'ui-dialog--compact', className)}
        {...props}
      >
        {children}
      </AlertDialog.Content>
    </AlertDialog.Portal>
  );
});

type ChoiceOption = { value: string; label: string; disabled?: boolean };

type SelectProps = Omit<ComponentPropsWithoutRef<typeof SelectPrimitive.Root>, 'children'> & {
  label: string;
  options: readonly ChoiceOption[];
  id?: string;
  className?: string;
  triggerProps?: Omit<
    ComponentPropsWithoutRef<typeof SelectPrimitive.Trigger>,
    'children' | 'id' | 'className'
  >;
};

export const Select = forwardRef<HTMLButtonElement, SelectProps>(function Select(
  { label, options, id, className, triggerProps, ...props },
  ref,
) {
  return (
    <SelectPrimitive.Root {...props}>
      <SelectPrimitive.Trigger
        ref={ref}
        {...triggerProps}
        id={id}
        aria-label={triggerProps?.['aria-label'] ?? label}
        className={cx('ui-select-trigger', className)}
      >
        <SelectPrimitive.Value />
        <SelectPrimitive.Icon>
          <ChevronDownIcon />
        </SelectPrimitive.Icon>
      </SelectPrimitive.Trigger>
      <SelectPrimitive.Portal>
        <SelectPrimitive.Content
          className="ui-select-content"
          position="popper"
          sideOffset={4}
          collisionPadding={12}
        >
          <SelectPrimitive.Viewport>
            {options.map((option) => (
              <SelectPrimitive.Item
                className="ui-select-item"
                key={option.value}
                value={option.value}
                disabled={option.disabled}
              >
                <SelectPrimitive.ItemText>{option.label}</SelectPrimitive.ItemText>
                <SelectPrimitive.ItemIndicator>
                  <CheckIcon />
                </SelectPrimitive.ItemIndicator>
              </SelectPrimitive.Item>
            ))}
          </SelectPrimitive.Viewport>
        </SelectPrimitive.Content>
      </SelectPrimitive.Portal>
    </SelectPrimitive.Root>
  );
});

export const RadioGroup = forwardRef<
  HTMLDivElement,
  Omit<ComponentPropsWithoutRef<typeof RadioGroupPrimitive.Root>, 'children'> & {
    label: string;
    options: readonly ChoiceOption[];
  }
>(function RadioGroup({ label, options, className, ...props }, ref) {
  return (
    <RadioGroupPrimitive.Root
      ref={ref}
      aria-label={label}
      className={cx('ui-radio-group', className)}
      {...props}
    >
      {options.map((option) => (
        <RadioGroupPrimitive.Item
          key={option.value}
          value={option.value}
          disabled={option.disabled}
          className="ui-radio-item"
        >
          <span className="ui-radio-mark" aria-hidden="true">
            <RadioGroupPrimitive.Indicator asChild>
              <CheckIcon />
            </RadioGroupPrimitive.Indicator>
          </span>
          <span>{option.label}</span>
        </RadioGroupPrimitive.Item>
      ))}
    </RadioGroupPrimitive.Root>
  );
});

type SliderProps = Omit<
  ComponentPropsWithoutRef<typeof Slider.Root>,
  'children' | 'value' | 'defaultValue' | 'onValueChange'
> & {
  label: string;
  value: number;
  onValueChange: (value: number) => void;
  thumbProps?: Omit<ComponentPropsWithoutRef<typeof Slider.Thumb>, 'id' | 'className'>;
};

/** 单滑块轨道，不带字段标题。`label` 作为滑块的无障碍名称。 */
export const TrackSlider = forwardRef<HTMLSpanElement, SliderProps>(function TrackSlider(
  { label, value, onValueChange, min = 1, max = 50, step = 1, id, className, thumbProps, ...props },
  ref,
) {
  return (
    <Slider.Root
      className={cx('ui-slider', className)}
      min={min}
      max={max}
      step={step}
      value={[value]}
      onValueChange={(values) => onValueChange(values[0])}
      {...props}
    >
      <Slider.Track className="ui-slider-track">
        <Slider.Range className="ui-slider-range" />
      </Slider.Track>
      <Slider.Thumb
        ref={ref}
        id={id}
        className="ui-slider-thumb"
        aria-label={label}
        {...thumbProps}
      />
    </Slider.Root>
  );
});

export const RangeSlider = forwardRef<
  HTMLSpanElement,
  SliderProps & { detail?: ReactNode; help?: string }
>(function RangeSlider({ label, value, id, detail = value, help, ...props }, ref) {
  const generatedId = useId();
  const thumbId = id ?? generatedId;
  return (
    <Field label={label} htmlFor={thumbId} detail={detail} help={help}>
      <TrackSlider ref={ref} id={thumbId} label={label} value={value} {...props} />
    </Field>
  );
});

export function ProgressBar({ value, label }: { value: number; label: string }) {
  return (
    <Progress.Root className="ui-progress" value={value} aria-label={label}>
      <Progress.Indicator
        className="ui-progress-indicator"
        style={{ transform: `translateX(-${100 - value}%)` }}
      />
    </Progress.Root>
  );
}

export const Switch = forwardRef<
  HTMLButtonElement,
  ComponentPropsWithoutRef<typeof SwitchPrimitive.Root>
>(function Switch({ className, ...props }, ref) {
  return (
    <SwitchPrimitive.Root ref={ref} className={cx('ui-switch', className)} {...props}>
      <SwitchPrimitive.Thumb className="ui-switch-thumb" />
    </SwitchPrimitive.Root>
  );
});

export const Checkbox = forwardRef<
  HTMLButtonElement,
  ComponentPropsWithoutRef<typeof CheckboxPrimitive.Root>
>(function Checkbox({ className, ...props }, ref) {
  return (
    <CheckboxPrimitive.Root ref={ref} className={cx('ui-checkbox', className)} {...props}>
      <CheckboxPrimitive.Indicator asChild>
        <CheckIcon aria-hidden="true" />
      </CheckboxPrimitive.Indicator>
    </CheckboxPrimitive.Root>
  );
});

export function Logo({ wordmark = false }: { wordmark?: boolean }) {
  return (
    <span className={cx('ui-logo', wordmark && 'ui-logo-full')} aria-hidden="true">
      <svg className="ui-logo-mark" viewBox="176 170 648 648">
        <use href={`${brandMark}#glyph`} />
      </svg>
      {wordmark && (
        <svg className="ui-logo-wordmark" viewBox="180 198 1812 338">
          <use href={`${brandWordmark}#glyph`} />
        </svg>
      )}
    </span>
  );
}
