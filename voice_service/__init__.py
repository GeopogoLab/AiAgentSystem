"""Voice service shared modules hosted under the Whisper workspace."""

from __future__ import annotations

from pathlib import Path

__all__ = []  # Expose actual modules from the workspace path.

# Ensure Python looks inside the workspace-managed directory first.
workspace_voice_dir = Path(__file__).resolve().parent.parent / "whisper-workspace" / "voice_service"
if workspace_voice_dir.exists():
    __path__.insert(0, str(workspace_voice_dir))
