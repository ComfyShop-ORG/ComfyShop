import { forwardRef, useState } from 'react';
import { DayPicker } from '@daypicker/react';
import type { DayPickerProps } from '@daypicker/react';
import { enUS } from '@daypicker/react/locale/en-US';
import { ja } from '@daypicker/react/locale/ja';
import { ko } from '@daypicker/react/locale/ko';
import { zhCN } from '@daypicker/react/locale/zh-CN';
import { zhTW } from '@daypicker/react/locale/zh-TW';
import { CalendarIcon } from '@radix-ui/react-icons';
import { Popover } from 'radix-ui';
import { Button } from './index';
import type { ButtonProps } from './index';

const calendarLocales: Record<string, DayPickerProps['locale']> = {
  en: enUS,
  'ja-JP': ja,
  'ko-KR': ko,
  'zh-CN': zhCN,
  'zh-TW': zhTW,
};

const calendarButton = 'ui-control ui-button ui-button--ghost';
const calendarClasses = {
  month: 'ui-calendar-month',
  month_caption: 'ui-calendar-caption',
  button_previous: `${calendarButton} ui-icon-button`,
  button_next: `${calendarButton} ui-icon-button`,
  month_grid: 'ui-calendar-grid',
  weekday: 'ui-calendar-weekday',
  day: 'ui-calendar-day',
  day_button: calendarButton,
  today: 'ui-calendar-today',
  selected: 'ui-calendar-selected',
};

type DatePickerProps = Omit<ButtonProps, 'children' | 'asChild' | 'value'> & {
  label: string;
  todayLabel: string;
  clearLabel: string;
  locale: string;
  value?: Date;
  onValueChange: (value: Date | undefined) => void;
};

export const DatePicker = forwardRef<HTMLButtonElement, DatePickerProps>(function DatePicker(
  { label, todayLabel, clearLabel, locale, value, onValueChange, className, ...props },
  ref,
) {
  const [open, setOpen] = useState(false);
  const formatted = value && new Intl.DateTimeFormat(locale, { dateStyle: 'medium' }).format(value);
  function select(day: Date | undefined) {
    onValueChange(day);
    setOpen(false);
  }
  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <Popover.Trigger asChild>
        <Button
          ref={ref}
          className={className ? `ui-date-trigger ${className}` : 'ui-date-trigger'}
          data-placeholder={!value || undefined}
          aria-label={formatted ? `${label} ${formatted}` : label}
          {...props}
        >
          <span>{formatted ?? label}</span>
          <CalendarIcon aria-hidden="true" />
        </Button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          className="ui-menu ui-date-popover"
          aria-label={label}
          align="start"
          sideOffset={4}
          collisionPadding={12}
          onOpenAutoFocus={(event) => event.preventDefault()}
        >
          <DayPicker
            autoFocus
            mode="single"
            required
            selected={value}
            defaultMonth={value}
            locale={calendarLocales[locale]}
            classNames={calendarClasses}
            navLayout="around"
            fixedWeeks
            onSelect={select}
          />
          <div className="ui-calendar-actions">
            <Button size="small" variant="ghost" onClick={() => select(new Date())}>
              {todayLabel}
            </Button>
            <Button
              size="small"
              variant="ghost"
              disabled={!value}
              onClick={() => select(undefined)}
            >
              {clearLabel}
            </Button>
          </div>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
});
