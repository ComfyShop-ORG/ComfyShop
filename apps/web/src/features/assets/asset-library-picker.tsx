import { ArchiveIcon } from '@radix-ui/react-icons';
import type { Asset } from '@comfyshop/api-client';
import { Button } from '@comfyshop/ui';
import type { ButtonProps } from '@comfyshop/ui';
import { t } from '../../app/i18n';
import { PickerDialog } from '../../components/picker-dialog';
import { AssetLibraryCollection } from './asset-library-collection';

export function AssetLibraryPicker({
  field,
  contentTypes,
  disabled,
  onSelect,
  label = t('assetLibrary.choose'),
  size = 'small',
}: {
  field?: string;
  contentTypes?: string[];
  disabled?: boolean;
  onSelect: (asset: Asset) => void;
  label?: string;
  size?: ButtonProps['size'];
}) {
  return (
    <PickerDialog
      title={label}
      trigger={
        <Button
          size={size}
          aria-label={field ? t('assetLibrary.chooseFor', field) : label}
          disabled={disabled}
        >
          <ArchiveIcon />
          {label}
        </Button>
      }
    >
      {(scrollRoot, close) => (
        <AssetLibraryCollection
          contentTypes={contentTypes}
          scrollRoot={scrollRoot}
          picking
          onOpen={(asset) => {
            onSelect(asset);
            close();
          }}
        />
      )}
    </PickerDialog>
  );
}
