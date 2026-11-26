import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ApiError } from '@comfyshop/api-client';
import type { ApiClient, GenerationInputs } from '@comfyshop/api-client';
import { Button } from '@comfyshop/ui';
import { t } from '../../app/i18n';
import { locale } from '../../app/language';

export function RunCostEstimate({
  api,
  inputs,
  executionCount,
  scope,
  inputsReady,
  disabled,
}: {
  api: ApiClient;
  inputs: GenerationInputs;
  executionCount: number | null;
  scope: readonly unknown[];
  inputsReady: boolean;
  disabled: boolean;
}) {
  const references = Object.entries(inputs.inputValues).flatMap(([id, value]) =>
    value && typeof value === 'object' && 'assetId' in value ? [[id, value.assetId]] : [],
  );
  const referenceKey = JSON.stringify(references);
  const [approvedReferences, setApprovedReferences] = useState<string>();
  const needsApproval = references.length > 0 && approvedReferences !== referenceKey;
  const quote = useQuery({
    queryKey: ['task-cost-estimate', ...scope, inputs],
    queryFn: async ({ signal }) => {
      await new Promise<void>((resolve) => setTimeout(resolve, 450));
      signal.throwIfAborted();
      return api.taskCostEstimate(inputs, signal);
    },
    enabled: inputsReady && !needsApproval && !disabled,
    retry: false,
    staleTime: 30_000,
    gcTime: 0,
    refetchOnWindowFocus: false,
  });
  if (!inputsReady || executionCount === null) return null;
  if (needsApproval) {
    return (
      <div className="run-cost-estimate">
        <p className="form-hint">{t('runForm.costMediaNotice')}</p>
        <Button
          type="button"
          size="small"
          variant="secondary"
          disabled={disabled}
          onClick={() => setApprovedReferences(referenceKey)}
        >
          {t('runForm.estimateCost')}
        </Button>
      </div>
    );
  }
  if (quote.error instanceof ApiError && quote.error.status === 404) return null;
  if (quote.isError && !quote.isFetching) {
    return (
      <div className="run-cost-estimate">
        <p className="form-hint" role="status">
          {t('runForm.costUnavailable')}
        </p>
        <Button
          type="button"
          size="small"
          variant="secondary"
          disabled={disabled || quote.isFetching}
          onClick={() => void quote.refetch()}
        >
          {t('app.retry')}
        </Button>
      </div>
    );
  }
  if (!quote.data || quote.isFetching) {
    return (
      !disabled && (
        <p className="form-hint run-cost-total" role="status">
          {t('runForm.costLoading')}
        </p>
      )
    );
  }
  // Preserve the provider's decimal precision when multiplying by the batch size.
  const [whole, fraction = ''] = quote.data.unitPrice.split('.');
  const batch = BigInt(whole + fraction) * BigInt(executionCount);
  const digits = String(batch).padStart(fraction.length + 1, '0');
  const boundary = digits.length - fraction.length;
  const amount = `${digits.slice(0, boundary)}.${digits.slice(boundary) || '0'}`;
  const total = new Intl.NumberFormat(locale, {
    style: 'currency',
    currency: quote.data.currency,
    currencyDisplay: 'code',
    maximumFractionDigits: 10,
  }).format(amount as Intl.StringNumericLiteral);
  return (
    <div className="run-cost-estimate">
      <p className="run-cost-total" role="status">
        {t('runForm.costTotal', total, executionCount)}
      </p>
      {quote.data.estimated && <p className="form-hint">{t('runForm.costActualUsage')}</p>}
    </div>
  );
}
