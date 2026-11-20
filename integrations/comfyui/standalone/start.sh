#!/bin/sh
# macOS 和 Linux 共用启动入口，在解压目录创建工作机环境。
set -eu
cd "$(dirname "$0")"
# worker.json 里没有密钥时，工作机启动后会在浏览器里申请接入账号。
umask 077
if [ -f worker.json ]; then
    chmod 600 worker.json
fi

version=0.13.7
uv_dir=".uv-$version"
if [ -x "$uv_dir/uv" ]; then
    uv="./$uv_dir/uv"
elif command -v uv >/dev/null 2>&1; then
    uv=uv
else
    # 发布物名称和 SHA-256 与 Astral 对应版本的 Release 一致。
    case "$(uname -s)/$(uname -m)" in
        Darwin/arm64)
            target=aarch64-apple-darwin
            checksum=81b811b57e4624df7ed3aac148e0359100d9962f3d9dce00aec533dc2e086731 ;;
        Darwin/x86_64)
            target=x86_64-apple-darwin
            checksum=20c47e4c1f630b8abaff8c291fa9b9aa300fef92c4fbff95adf198b55287cda7 ;;
        Linux/aarch64|Linux/arm64)
            target=aarch64-unknown-linux-gnu
            checksum=71279f8d3c67241e807b9d8db872d1bf541579fb9f08b7d1eb1682196d1e57dc ;;
        Linux/x86_64)
            target=x86_64-unknown-linux-gnu
            checksum=c5221ff41b7892bfc223543883600125f6a47fe845093e0f5bdff4f359196d83 ;;
        *)
            echo '此系统需要先安装 uv，再运行启动文件。参见工作机接入文档。' >&2
            exit 1 ;;
    esac
    if ! command -v curl >/dev/null 2>&1; then
        echo '请先安装 curl 或 uv，再运行启动文件。' >&2
        exit 1
    fi
    echo '正在下载 uv，需要联网。'
    scratch=$(mktemp -d)
    trap 'rm -rf "$scratch"' 0
    download_uv() {
        curl --proto '=https' --proto-redir '=https' --connect-timeout 20 \
            --speed-limit 1024 --speed-time 60 -fLsS -o "$scratch/uv.tar.gz" "$1"
    }
    release="astral-sh/uv/releases/download/$version/uv-$target.tar.gz"
    download_uv "https://releases.astral.sh/github/$release" || download_uv "https://github.com/$release"
    printf '%s  %s\n' "$checksum" "$scratch/uv.tar.gz" > "$scratch/uv.sha256"
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum -c "$scratch/uv.sha256"
    else
        shasum -a 256 -c "$scratch/uv.sha256"
    fi
    tar -xf "$scratch/uv.tar.gz" --strip-components 1 -C "$scratch"
    mkdir -p "$uv_dir"
    mv "$scratch/uv" "$uv_dir/uv"
    rm -rf "$scratch"
    trap - 0
    uv="./$uv_dir/uv"
fi

echo '正在检查 Python 3.12 和工作机依赖。'
"$uv" --no-config venv --allow-existing --python 3.12 .venv
"$uv" --no-config pip sync --python .venv --require-hashes --only-binary :all: requirements.txt
export COMFYSHOP_WORKER_CONFIG="$PWD/worker.json"
.venv/bin/python -m comfyshop_worker "$@"
