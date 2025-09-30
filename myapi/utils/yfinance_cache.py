import logging
import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Optional

import yfinance as yf

try:
    from yfinance import cache as yf_cache
except ImportError:  # pragma: no cover - safety guard for older releases
    yf_cache = None  # type: ignore[assignment]

_logger = logging.getLogger(__name__)
_CACHE_ENV_VAR = "YFINANCE_CACHE_DIR"
_DEFAULT_CACHE_DIR = Path(os.environ.get(_CACHE_ENV_VAR, "/tmp/py-yfinance")).expanduser()
_configured = False
_cache_path: Optional[Path] = None


def _as_dict(data: Any) -> dict[str, Any]:
    if data is None:
        return {}
    if isinstance(data, Mapping):
        return dict(data)
    if hasattr(data, "_asdict"):
        try:
            return dict(data._asdict())
        except Exception:
            return {}
    if hasattr(data, "__dict__"):
        return {
            key: value
            for key, value in vars(data).items()
            if not key.startswith("_")
        }
    return {}


def _ensure_dir(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        _logger.warning("Could not create yfinance cache directory %s: %s", path, exc)
        return False
    return True


def configure_yfinance_cache(cache_dir: Optional[Path | str] = None) -> Optional[Path]:
    """Ensure yfinance caches live in a writable location."""
    global _configured, _cache_path

    if _configured:
        return _cache_path

    target = Path(cache_dir).expanduser() if cache_dir else _DEFAULT_CACHE_DIR

    if not _ensure_dir(target):
        _configured = True
        _cache_path = None
        return None

    if yf_cache is not None:
        try:
            yf_cache.set_cache_location(str(target))
        except Exception as exc:
            _logger.warning(
                "Failed to set yfinance cache location to %s: %s", target, exc
            )
        else:
            if hasattr(yf, "set_tz_cache_location"):
                tz_dir = target / "tz"
                if _ensure_dir(tz_dir):
                    try:
                        yf.set_tz_cache_location(str(tz_dir))
                    except Exception as exc:  # pragma: no cover - defensive
                        _logger.debug(
                            "Could not set yfinance tz cache location: %s", exc
                        )
    else:  # pragma: no cover - defensive guard
        _logger.debug("yfinance cache module not available")

    _configured = True
    _cache_path = target
    return _cache_path


configure_yfinance_cache()


def safe_get_ticker_info(
    tk: yf.Ticker, keys: Sequence[str] | None = None
) -> dict[str, Any]:
    """Retrieve ticker info while tolerating missing fundamentals."""
    accessors = (
        "get_info",
        "get_fast_info",
        "info",
        "fast_info",
    )
    failures: list[str] = []
    for name in accessors:
        attr = getattr(tk, name, None)
        if attr is None:
            continue
        try:
            payload = attr() if callable(attr) else attr
        except Exception as exc:  # pragma: no cover - network dependent
            failures.append(f"{name}: {exc}")
            continue
        info_map = _as_dict(payload)
        if not info_map:
            continue
        if keys is None:
            return info_map
        subset = {key: info_map.get(key) for key in keys if key in info_map}
        if subset:
            return subset
    if failures:
        _logger.debug(
            "yfinance info lookups failed for %s: %s",
            getattr(tk, "ticker", ""),
            "; ".join(failures),
        )
    return {}
