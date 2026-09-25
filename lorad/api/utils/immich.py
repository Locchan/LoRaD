import json
import random
import ssl
import threading
import urllib.error
import urllib.request
from collections import Counter
from urllib.parse import urljoin

from lorad.common.utils.logger import get_logger
from lorad.common.utils.misc import read_config
from lorad.common.utils.shm import read_immich_backgrounds, write_immich_backgrounds

logger = get_logger()

_refresh_lock = threading.Lock()
_refreshing = False


def _immich_block(config=None) -> dict:
    config = config if config is not None else read_config()
    return config.get("IMMICH") or {}


def _backgrounds_block(config=None) -> dict:
    return _immich_block(config).get("BACKGROUNDS") or {}


def immich_configured(config=None) -> bool:
    immich = _immich_block(config)
    return bool(immich.get("BASE_URL") and immich.get("API_KEY"))


def backgrounds_configured(config=None) -> bool:
    return immich_configured(config) and bool(_backgrounds_block(config).get("PERSON_IDS"))


def start_immich_cache() -> None:
    config = read_config()
    if "IMMICH_BACKGROUNDS" not in config.get("ENABLED_FEATURES", []):
        return
    if not backgrounds_configured(config):
        return
    Thread = threading.Thread
    Thread(name="ImmichBg", target=refresh_immich_cache, daemon=True).start()


def refresh_immich_cache(force: bool = False) -> list[dict]:
    global _refreshing
    with _refresh_lock:
        if _refreshing:
            cached = read_immich_backgrounds()
            return cached or []
        if not force:
            cached = read_immich_backgrounds()
            if cached:
                return cached
        _refreshing = True
    try:
        assets = _scan_eligible_assets()
        write_immich_backgrounds(assets)
        logger.info(f"Pinned {len(assets)} Immich background assets")
        return assets
    except Exception as e:
        logger.warn(f"Immich background scan failed: {e.__class__.__name__}: {e}")
        cached = read_immich_backgrounds()
        return cached or []
    finally:
        with _refresh_lock:
            _refreshing = False


def pick_background_jpeg() -> tuple[bytes, str | None] | None:
    """(jpeg, "YYYY-MM-DD") for a random eligible asset. The date is None if Immich has none."""
    config = read_config()
    if not backgrounds_configured(config):
        return None
    assets = read_immich_backgrounds()
    if not assets:
        threading.Thread(name="ImmichBg", target=refresh_immich_cache, daemon=True).start()
        return None
    order = list(assets)
    random.shuffle(order)
    for asset in order[:2]:
        data = _download_preview(config, asset["id"])
        if data:
            return data, asset.get("date")
    threading.Thread(name="ImmichBg", target=lambda: refresh_immich_cache(True), daemon=True).start()
    return None


def _immich_url(base: str, path: str) -> str:
    return urljoin(base.rstrip("/") + "/", path.lstrip("/"))


def _immich_request(config, method: str, path: str, body=None, timeout: float = 20) -> tuple[int, bytes, str]:
    immich = config["IMMICH"]
    url = _immich_url(str(immich["BASE_URL"]), path)
    headers = {
        "x-api-key": str(immich["API_KEY"]),
        "Accept": "application/json, image/*",
    }
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    context = ssl.create_default_context()
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
            content_type = response.headers.get("Content-Type", "")
            return response.getcode(), response.read(), content_type
    except urllib.error.HTTPError as e:
        return e.code, e.read() if e.fp else b"", e.headers.get("Content-Type", "") if e.headers else ""


def _scan_eligible_assets() -> list[dict]:
    config = read_config()
    backgrounds = _backgrounds_block(config)
    person_ids = [str(item) for item in backgrounds.get("PERSON_IDS") or [] if item]
    min_people = int(backgrounds.get("MIN_PEOPLE") or 3)
    counts: Counter[str] = Counter()
    dates: dict[str, str | None] = {}
    for person_id in person_ids:
        for asset_id, date in _assets_for_person(config, person_id):
            counts[asset_id] += 1
            dates.setdefault(asset_id, date)
    return [
        {"id": asset_id, "date": dates.get(asset_id)}
        for asset_id, count in counts.items()
        if count >= min_people
    ]


def _asset_date(item: dict) -> str | None:
    """Day the photo was taken, as Immich knows it. None if it has no usable timestamp."""
    exif = item.get("exifInfo") or {}
    for value in (item.get("localDateTime"), exif.get("dateTimeOriginal"), item.get("fileCreatedAt")):
        text = str(value or "")
        # ISO-8601, and we only want the date part
        if len(text) >= 10 and text[4] == "-" and text[7] == "-" and text[:4].isdigit():
            return text[:10]
    return None


def _assets_for_person(config, person_id: str) -> list[tuple[str, str | None]]:
    found = []
    page = 1
    while page <= 5:
        status, payload, _ = _immich_request(
            config,
            "POST",
            "/api/search/metadata",
            {"personIds": [person_id], "size": 250, "page": page},
        )
        if status != 200:
            logger.warn(f"Immich search for person {person_id} failed: HTTP {status}")
            break
        try:
            body = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            break
        items = ((body.get("assets") or {}).get("items") or [])
        for item in items:
            asset_id = item.get("id")
            if asset_id:
                found.append((str(asset_id), _asset_date(item)))
        next_page = (body.get("assets") or {}).get("nextPage")
        if not next_page:
            break
        try:
            page = int(next_page)
        except (TypeError, ValueError):
            page += 1
    return found


def _download_preview(config, asset_id: str) -> bytes | None:
    for path in (
        f"/api/assets/{asset_id}/thumbnail?size=preview",
        f"/api/assets/{asset_id}/original",
    ):
        status, payload, content_type = _immich_request(config, "GET", path, timeout=30)
        if status == 200 and payload:
            if "json" in (content_type or "").lower():
                continue
            return payload
    return None
