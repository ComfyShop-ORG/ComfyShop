# ComfyShop Media

`comfyshop-media` 是可独立安装的 Python 媒体库，导入名为 `comfyshop_media`，需要 Python 3.12 或更高版本。

## 模块职责

- 流式接收图片和视频，在数据卷的 `staging/` 内暂存，校验格式并返回 SHA-256、字节数和尺寸。
- 通过本地目录或 S3 兼容存储读写原件。本地原件写入 `originals/`，同一文件系统上使用硬链接原子发布。S3 的 `open_original()` 支持单段字节范围读取，读取结束后由调用方关闭返回的 `body`。
- 按需生成 WebP 图片缩略图、JPEG 视频封面和静音 MP4 短片。视频校验需要 `ffprobe`，封面和短片生成需要 `ffmpeg`，短片编码使用 `libx264`。

ComfyShop API 负责鉴权、HTTP 响应、原件登记和业务引用。后台根据素材和成品的实际外键决定何时回收原件。详见[架构文档](../../docs/architecture.md#数据库)。

## 独立使用

在使用该库的 Python 虚拟环境中，从仓库根目录运行以下安装命令。需要构建 wheel 时，运行 `uv build --package comfyshop-media --wheel`。

```sh
uv pip install ./libs/media
```

下面的示例在临时目录接收一张 PNG，存储原件，再生成长边 256 像素的缩略图。

```python
import asyncio
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image

from comfyshop_media.renditions import MediaSource, read_thumbnail
from comfyshop_media.settings import MediaSettings
from comfyshop_media.uploads import receive_media


async def chunks():
    with BytesIO() as image:
        Image.new("RGB", (640, 480)).save(image, format="PNG")
        yield image.getvalue()


async def main():
    with TemporaryDirectory() as data_dir:
        settings = MediaSettings(data_dir=Path(data_dir), storage_backend="local")
        storage = settings.media_storage
        with storage.staging_directory() as directory:
            media = await receive_media(chunks(), Path(directory), 1024**2, settings.ffprobe)
            name = media.path.name
            storage.put(name, media.path, media.content_type)

        source = MediaSource(name, media.sha256, media.content_type, media.width, media.height)
        content, content_type = read_thumbnail(source, settings, 256)
        print(content_type, len(content))


asyncio.run(main())
```

## 配置与缓存

独立使用时，`MediaSettings` 可通过参数或 `COMFYSHOP_MEDIA_` 环境变量配置。`DATA_DIR` 必填，`STORAGE_BACKEND` 默认为 `local`。使用 S3 时将后者设为 `s3`，并填写 `S3_BUCKET`。连接 RustFS 时可设置 `S3_ENDPOINT_URL` 并将 `S3_ADDRESSING_STYLE` 设为 `path`。凭据可通过 SDK 凭据链提供，也可同时设置 `S3_ACCESS_KEY_ID` 和 `S3_SECRET_ACCESS_KEY`。

本地的 `thumbnails/` 和 `video-previews/` 共用一份容量配额，S3 的 `derived/` 使用同样大小的独立配额。`DERIVATIVE_CACHE_MAX_BYTES` 默认 `536870912`（512 MiB），设为 `0` 时按需生成。`DERIVATIVE_CACHE_TTL_SECONDS` 默认 `604800`（7 天），从派生文件写入时开始计算。

暂存目录在使用期间持有文件锁。独立调用方可定期运行 `prune_abandoned_staging()` 回收进程退出后遗留的暂存目录，并运行 `prune_local_derivatives()` 和 `prune_object_derivatives()`，删除过期派生文件，并在超额时优先淘汰最早写入的文件。ComfyShop API 约每分钟运行清理，缓存总量在两次清理之间可短暂超过配额。应用配置使用 `COMFYSHOP_` 前缀，详见[部署文档](../../docs/deployment.md)。

## 测试

在仓库根目录运行 `uv run --all-packages pytest libs/media/tests`。
