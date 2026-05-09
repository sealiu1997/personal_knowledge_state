from __future__ import annotations

import os
from pathlib import Path

PKS_HOME_ENV = "PKS_HOME"


def resolve_pks_home(home: Path | None = None) -> Path:
    if home is not None:
        return home.expanduser()
    env_home = os.environ.get(PKS_HOME_ENV)
    if env_home:
        return Path(env_home).expanduser()
    return Path("~/.pks").expanduser()
