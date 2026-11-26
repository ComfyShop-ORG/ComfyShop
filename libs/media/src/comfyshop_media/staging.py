"""通过文件锁识别仍在使用的暂存目录，进程退出后由维护循环接手。"""

from collections.abc import Callable
from pathlib import Path
from shutil import rmtree
from tempfile import TemporaryDirectory

from anyio import CancelScope, to_thread
from filelock import FileLock, Timeout


class StagingDirectory(TemporaryDirectory[str]):
    def __init__(self, root: Path) -> None:
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.keep_for_recovery = False
        self._gate = FileLock(root / ".allocation.lock", thread_local=False)
        # 创建目录和取得所有权对清理者可见为一个操作。
        with self._gate:
            super().__init__(dir=root, prefix="work-", delete=False)
            self._owner = FileLock(
                Path(self.name) / ".owner.lock", thread_local=False, preserve_lock_file=True
            )
            self._owner.acquire()

    def cleanup(self) -> None:
        with self._gate:
            if self._owner.is_locked:
                self._owner.release()
                if not self.keep_for_recovery:
                    super().cleanup()

    async def aclose(self) -> None:
        with CancelScope(shield=True):
            await to_thread.run_sync(self.cleanup)

    def __exit__(self, *_exc_info: object) -> None:
        self.cleanup()


def prune_staging(root: Path, recover: Callable[[Path], None] | None) -> None:
    lock_path = root / ".allocation.lock"
    if root.is_symlink() or lock_path.is_symlink():
        return
    gate = FileLock(lock_path)
    for directory in root.glob("work-*"):
        with gate:
            if directory.is_symlink() or not directory.is_dir():
                continue
            lease = directory / ".owner.lock"
            if lease.is_symlink() or (not lease.is_file() and any(directory.iterdir())):
                continue
            owner = FileLock(lease, preserve_lock_file=True)
            try:
                owner.acquire(timeout=0)
            except Timeout:
                continue
        try:
            if recover:
                recover(directory)
            with gate:
                owner.release()
                rmtree(directory)
        finally:
            owner.release()
