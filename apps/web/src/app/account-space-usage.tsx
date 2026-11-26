import { DropdownMenu, ProgressBar } from '@comfyshop/ui';
import { fileSizeLabel } from '../data/download';
import { useAssetUsage } from '../features/assets/asset-queries';
import { t } from './i18n';
import { locale } from './language';

const percentFormat = new Intl.NumberFormat(locale, {
  style: 'percent',
  maximumFractionDigits: 0,
});

export function AccountSpaceUsage() {
  const { data, error, refetch } = useAssetUsage();
  const label = t('assetLibrary.usage');
  const percent = data ? Math.floor((data.usedBytes * 100) / data.limitBytes) : 0;
  const lowUsage = percent === 0 && (data?.usedBytes ?? 0) > 0;
  return (
    <div className="account-menu-usage">
      <DropdownMenu.Label className="account-menu-usage-title">
        <span>{label}</span>
        {data && !error && (
          <span className="account-menu-usage-percent" aria-hidden="true">
            {lowUsage ? `<${percentFormat.format(0.01)}` : percentFormat.format(percent / 100)}
          </span>
        )}
      </DropdownMenu.Label>
      {error ? (
        <>
          <span className="muted" role="alert">
            {t('assetLibrary.usageUnavailable')}
          </span>
          <DropdownMenu.Item
            className="ui-menu-item"
            onSelect={(event) => {
              event.preventDefault();
              void refetch();
            }}
          >
            {t('app.retry')}
          </DropdownMenu.Item>
        </>
      ) : data ? (
        <>
          <ProgressBar
            role="meter"
            label={label}
            data-low-usage={lowUsage ? '' : undefined}
            value={Math.min(data.usedBytes, data.limitBytes)}
            max={data.limitBytes}
            getValueLabel={() =>
              t(
                'assetLibrary.usageValue',
                fileSizeLabel(data.usedBytes),
                fileSizeLabel(data.limitBytes),
              )
            }
          />
          <dl aria-live="polite">
            <div>
              <dt>{t('assetLibrary.used')}</dt>
              <dd>{fileSizeLabel(data.usedBytes)}</dd>
            </div>
            <div>
              <dt>{t('assetLibrary.remaining')}</dt>
              <dd>{fileSizeLabel(data.remainingBytes)}</dd>
            </div>
            <div>
              <dt>{t('assetLibrary.limit')}</dt>
              <dd>{fileSizeLabel(data.limitBytes)}</dd>
            </div>
          </dl>
        </>
      ) : (
        <span className="muted" role="status">
          {t('common.loading')}
        </span>
      )}
    </div>
  );
}
