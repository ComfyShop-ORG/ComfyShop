#!/bin/sh
# Finder 双击此文件，在终端调用共用启动脚本。
exec /bin/sh "$(dirname "$0")/start.sh" "$@"
