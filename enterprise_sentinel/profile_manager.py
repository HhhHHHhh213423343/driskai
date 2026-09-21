from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path


# 这些目录体积大且不影响登录态，复制时跳过可以显著缩短启动准备时间。
PROFILE_EXCLUDES = shutil.ignore_patterns(
    "Cache",
    "Code Cache",
    "GPUCache",
    "blob_storage",
    "Service Worker",
    "GrShaderCache",
    "GraphiteDawnCache",
    "DawnGraphiteCache",
)


@dataclass(frozen=True)
class PreparedProfile:
    """运行期浏览器配置目录。"""

    user_data_dir: Path
    is_temporary: bool = False


def prepare_runtime_profile(
    source_user_data_dir: Path,
    profile_directory: str,
    clone_profile: bool,
    clone_root_dir: Path | None = None,
) -> PreparedProfile:
    """准备浏览器运行目录。

    - `clone_profile=True` 时会复制一份独立目录，避免和正在使用的浏览器冲突。
    - `clone_profile=False` 时直接使用用户原始目录。
    """

    source_user_data_dir = source_user_data_dir.expanduser().resolve()
    if not source_user_data_dir.exists():
        raise FileNotFoundError(f"浏览器用户数据目录不存在：{source_user_data_dir}")

    if not clone_profile:
        return PreparedProfile(user_data_dir=source_user_data_dir, is_temporary=False)

    clone_root_dir = (
        clone_root_dir.expanduser().resolve()
        if clone_root_dir
        else Path(tempfile.gettempdir()).resolve()
    )
    clone_root_dir.mkdir(parents=True, exist_ok=True)
    target_dir = Path(
        tempfile.mkdtemp(prefix="enterprise_sentinel_profile_", dir=str(clone_root_dir))
    )

    local_state = source_user_data_dir / "Local State"
    if local_state.exists():
        shutil.copy2(local_state, target_dir / "Local State")

    source_profile_dir = source_user_data_dir / profile_directory
    if not source_profile_dir.exists():
        raise FileNotFoundError(f"浏览器配置目录不存在：{source_profile_dir}")

    shutil.copytree(source_profile_dir, target_dir / profile_directory, ignore=PROFILE_EXCLUDES)
    return PreparedProfile(user_data_dir=target_dir, is_temporary=True)


def cleanup_prepared_profile(prepared_profile: PreparedProfile | None) -> None:
    """清理临时克隆目录。"""

    if not prepared_profile or not prepared_profile.is_temporary:
        return
    shutil.rmtree(prepared_profile.user_data_dir, ignore_errors=True)
