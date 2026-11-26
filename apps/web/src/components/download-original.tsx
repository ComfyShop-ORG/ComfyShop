import { DownloadIcon } from '@radix-ui/react-icons';
import type { Media } from '@comfyshop/api-client';
import { Button } from '@comfyshop/ui';
import { t } from '../app/i18n';
import { mediaUrl } from '../data/media-url';

export function DownloadOriginal({ media, filename }: { media: Media; filename: string }) {
  return (
    <Button size="small" asChild>
      <a href={mediaUrl(media.video || media.src, 'download', 'true')} download={filename}>
        <DownloadIcon />
        {t('artifactCollection.downloadOriginal')}
      </a>
    </Button>
  );
}
