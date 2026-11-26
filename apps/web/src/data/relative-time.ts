/** 把过去的时刻写成「刚刚」「5 分钟前」这类相对时间，超过一周显示日期。 */
import { locale } from '../app/language.ts';
import { t } from '../app/i18n.ts';

const relative = new Intl.RelativeTimeFormat(locale);

export function relativeTime(timestamp: number, now = Date.now()) {
  const minutes = Math.floor((now - timestamp) / 60_000);
  if (minutes < 1) return t('relativeTime.justNow');
  if (minutes < 60) return relative.format(-minutes, 'minute');
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return relative.format(-hours, 'hour');
  const days = Math.floor(hours / 24);
  if (days < 7) return relative.format(-days, 'day');
  return new Date(timestamp).toLocaleDateString(locale);
}
