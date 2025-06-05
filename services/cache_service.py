import json
import pickle
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from config import Config
from utils.logging_config import get_logger


class CacheService:
    """Smart cache service with configurable TTL for different data types."""

    def __init__(self, config: Config):
        self.config = config
        self.cache_dir = Path(config.CACHE_DIR)
        self.enabled = config.CACHE_ENABLED
        self.logger = get_logger(__name__)

        # Cache TTL configurations for different data types
        self.cache_ttl_config = {
            "tle_current": config.TLE_CACHE_MAX_AGE_HOURS,
            "tle_history": config.HISTORICAL_DATA_CACHE_HOURS,
            "tle_age": config.TLE_DATA_FRESHNESS_THRESHOLD_HOURS,
            "satellite_metadata": config.METADATA_CACHE_HOURS,
            "default": config.CACHE_TTL_HOURS,
        }

        if self.enabled:
            self.cache_dir.mkdir(exist_ok=True)
            self.logger.info(
                f"Smart cache service initialized - Default TTL: {config.CACHE_TTL_HOURS}h"
            )
        else:
            self.logger.info("Cache service disabled")

    def _get_cache_type(self, key: str) -> str:
        """Determine cache type based on key pattern."""
        if "celestrak_tle_" in key or "spacetrack_tle_current_" in key:
            return "tle_current"
        elif "tle_history_" in key:
            return "tle_history"
        elif "tle_age_" in key:
            return "tle_age"
        elif "satellite_info_" in key or "satellite_meta_" in key:
            return "satellite_metadata"
        else:
            return "default"

    def _get_ttl_hours(self, cache_type: str) -> int:
        """Get TTL hours for specific cache type."""
        return self.cache_ttl_config.get(cache_type, self.cache_ttl_config["default"])

    def _get_cache_path(self, key: str) -> Path:
        """Get cache file path for given key."""
        safe_key = "".join(c for c in key if c.isalnum() or c in ("_", "-"))
        return self.cache_dir / f"{safe_key}.cache"

    def _get_cache_metadata_path(self, key: str) -> Path:
        """Get cache metadata file path."""
        safe_key = "".join(c for c in key if c.isalnum() or c in ("_", "-"))
        return self.cache_dir / f"{safe_key}.meta"

    def _is_cache_valid(self, cache_path: Path, key: str) -> bool:
        """Check if cache file is still valid based on its type."""
        if not cache_path.exists():
            return False

        cache_type = self._get_cache_type(key)
        ttl_hours = self._get_ttl_hours(cache_type)

        mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
        expiry_time = mtime + timedelta(hours=ttl_hours)
        is_valid = datetime.now() < expiry_time

        if not is_valid:
            self.logger.debug(
                f"Cache expired for {cache_path.name} (type: {cache_type}, TTL: {ttl_hours}h)"
            )

        return is_valid

    def _is_tle_data_fresh(self, cached_data: Any, key: str) -> bool:
        """Check if cached TLE data is still fresh based on epoch."""
        if not hasattr(cached_data, "epoch") or not cached_data.epoch:
            return True  # Can't determine freshness, assume valid

        try:
            # Parse epoch from TLE data
            epoch_str = cached_data.epoch
            if "T" in epoch_str:
                epoch_dt = datetime.fromisoformat(epoch_str.replace("Z", "+00:00"))
            else:
                epoch_dt = datetime.strptime(epoch_str[:19], "%Y-%m-%d %H:%M:%S")

            # Check if TLE epoch is older than our freshness threshold
            age_hours = (datetime.now() - epoch_dt).total_seconds() / 3600
            freshness_threshold = self.config.TLE_DATA_FRESHNESS_THRESHOLD_HOURS

            is_fresh = age_hours < freshness_threshold

            if not is_fresh:
                self.logger.debug(
                    f"TLE data epoch is stale for {key}: {age_hours:.1f}h old (threshold: {freshness_threshold}h)"
                )

            return is_fresh

        except Exception as e:
            self.logger.warning(f"Could not check TLE freshness for {key}: {e}")
            return True  # Assume valid if we can't parse

    def get(self, key: str) -> Optional[Any]:
        """Get data from cache with smart validation."""
        if not self.enabled:
            return None

        try:
            cache_path = self._get_cache_path(key)

            # First check basic cache validity (TTL)
            if not self._is_cache_valid(cache_path, key):
                return None

            with open(cache_path, "rb") as f:
                data = pickle.load(f)

            # Additional freshness check for TLE data
            cache_type = self._get_cache_type(key)
            if cache_type == "tle_current" and not self._is_tle_data_fresh(data, key):
                self.logger.debug(f"TLE data is stale, invalidating cache for {key}")
                return None

            self.logger.debug(f"Cache HIT for key: {key} (type: {cache_type})")
            return data

        except Exception as e:
            self.logger.warning(f"Failed to read cache for key {key}: {e}")
            return None

    def set(self, key: str, data: Any) -> None:
        """Store data in cache with metadata."""
        if not self.enabled:
            return

        try:
            cache_path = self._get_cache_path(key)
            cache_type = self._get_cache_type(key)

            # Store the data
            with open(cache_path, "wb") as f:
                pickle.dump(data, f)

            # Store metadata
            metadata = {
                "key": key,
                "cache_type": cache_type,
                "ttl_hours": self._get_ttl_hours(cache_type),
                "created_at": datetime.now().isoformat(),
                "tle_epoch": getattr(data, "epoch", None)
                if hasattr(data, "epoch")
                else None,
            }

            metadata_path = self._get_cache_metadata_path(key)
            with open(metadata_path, "w") as f:
                json.dump(metadata, f, indent=2)

            self.logger.debug(
                f"Cache SET for key: {key} (type: {cache_type}, TTL: {metadata['ttl_hours']}h)"
            )

        except Exception as e:
            self.logger.error(f"Failed to write cache for key {key}: {e}")

    def cleanup_expired_cache(self) -> dict[str, int]:
        """Clean up expired cache files."""
        stats = {"removed": 0, "errors": 0}

        try:
            for cache_file in self.cache_dir.glob("*.cache"):
                key = cache_file.stem
                if not self._is_cache_valid(cache_file, key):
                    try:
                        cache_file.unlink()
                        # Also remove metadata file if exists
                        meta_file = cache_file.with_suffix(".meta")
                        if meta_file.exists():
                            meta_file.unlink()
                        stats["removed"] += 1
                    except Exception:
                        stats["errors"] += 1

            if stats["removed"] > 0:
                self.logger.info(f"Cleaned up {stats['removed']} expired cache files")

        except Exception as e:
            self.logger.error(f"Failed to cleanup cache: {e}")
            stats["errors"] += 1

        return stats

    def get_cache_info(self) -> dict[str, Any]:
        """Get detailed cache statistics."""
        if not self.enabled:
            return {"enabled": False}

        try:
            cache_files = list(self.cache_dir.glob("*.cache"))
            total_size = sum(f.stat().st_size for f in cache_files)

            # Categorize by cache type
            type_stats = {}
            for cache_file in cache_files:
                key = cache_file.stem
                cache_type = self._get_cache_type(key)

                if cache_type not in type_stats:
                    type_stats[cache_type] = {"count": 0, "valid": 0, "expired": 0}

                type_stats[cache_type]["count"] += 1

                if self._is_cache_valid(cache_file, key):
                    type_stats[cache_type]["valid"] += 1
                else:
                    type_stats[cache_type]["expired"] += 1

            info = {
                "enabled": True,
                "total_files": len(cache_files),
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "cache_types": type_stats,
                "ttl_config": self.cache_ttl_config,
            }

            return info

        except Exception as e:
            self.logger.error(f"Failed to get cache info: {e}")
            return {"enabled": True, "error": str(e)}
