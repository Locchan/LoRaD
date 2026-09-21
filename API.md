# LoRaD REST / WebSocket API

This is the complete HTTP API for the LoRaD backend. The audio stream (`GET /` as `audio/mpeg` on `LISTEN_PORT`, typically 5475) is **not** part of this API.

Live copies of a thinner catalog also exist at `GET /apidoc` (HTML) and `GET /openapi` (OpenAPI 3.0). Those are generated from endpoint metadata and miss WebSocket protocol, status codes, and feature gates. This file is the source of truth.

## Servers

| Server | Config | Default (images) | Threading |
|---|---|---|---|
| REST | `REST.LISTEN_PORT` | 5476 | Single-threaded `HTTPServer` |
| WebSocket | `REST.WS_LISTEN_PORT` | 5478 | Threaded (`WS#N` workers) |

Both bind `0.0.0.0`. REST handlers must stay short; they run on the one REST thread.

## Conventions

- Path matching is **literal**. `/foo` ≠ `/foo/`. Query strings are stripped before matching (`/admin/get_config?key=…` matches `/admin/get_config`).
- Methods: `GET`, `POST`, and `OPTIONS`. Other methods are not implemented.
- `POST` body is JSON. Over `REST.MAX_DATA_LEN_BYTES` → **413** (empty body). Invalid JSON → **400** `{"error": "Malformed data"}`.
- Successful JSON responses are a JSON object. There is no envelope (`rc` / `data` are internal).
- `GET` may take query parameters. `impl_GET` is called as `impl_GET(headers)` or `impl_GET(headers, query_dict)` when a query string is present. Each query key is a string if it appears once, otherwise a list of strings.
- `OPTIONS` returns **204** with CORS headers (no body).
- CORS: `Access-Control-Allow-Origin` is the request `Origin` or `*`; methods `GET, POST, OPTIONS`; headers `Authorization, Content-Type, X-Requested-With`.
- Client IP for logs and similar uses `X-Real-IP` when present (reverse proxy).
- Unknown path: **404** `{"error": "No such endpoint: '…'"}`.
- Uncaught handler error: **500** `{"error": "Server error: …"}` or `{"error": "Error (…). Details are in the server log."}`.

## Authentication

Header (REST):

```
Authorization: <username>, <token>
```

Comma-separated, **not** Bearer. Token is 32 hex characters, stored in `api_token`, TTL `REST.TOKEN_EXPIRATION_MIN`.

| Code | Meaning |
|---|---|
| 401 | Missing, unknown, or expired token |
| 403 | Authenticated, wrong capability |
| 400 | `Authorization` is present but not exactly two comma-separated parts |

`LOGIN_REQUIRED` on a module is documentation / OpenAPI only. Enforcement is `@lrd_auth`.

Capabilities (comma-separated string on `api_group`):

| Constant | Stored as | Who |
|---|---|---|
| Basic user | `BU` | All logged-in users (group `default`) |
| Admin | `ADMIN` | Admins |
| Bypass | `ALL` | Satisfies any `@lrd_auth` check |

New users from `POST /user/register` land in group `default` with `BU`.

## Feature gates

`@lrd_feat_req` requires the named string (or **any** of a list) to be in config `ENABLED_FEATURES`. Missing feature → **405**:

```json
{"error": "<feature> feature is not enabled. Enable it in order to use this endpoint."}
```

Relevant features:

| Feature | Endpoints |
|---|---|
| `FILESTREAMER:YANDEX` | `/yandex/*` |
| `RESTREAMER` | `/radio/*` and `POST /switch_player` |

`POST /switch_player` is gated on `RESTREAMER` even though it can switch to any registered player.

## Switching lock

Player and station switches take `SWITCH_LOCK` for **10 seconds** after a successful change (`forbid_switching(10)`). While locked, switch endpoints return **406**:

```json
{"message": "Cannot switch right now. Try later."}
```

Programs call `forbid_switching()` with no duration at start and `allow_switching()` in `finally`, so the lock lasts the whole show (news included). FileStreamer also 406s while `player.switching` (Yandex station prefetch in flight). `/whatsplaying` exposes this as `can_switch`.

## WebSocket protocol

WebSocket endpoints live **only** on `REST.WS_LISTEN_PORT`.

- REST `GET` of a WebSocket path → **426** `{"error": "This endpoint is a WebSocket. Connect to port <WS_LISTEN_PORT>."}`
- WS port `POST` → **405** `{"error": "WebSocket port accepts GET upgrades only."}`
- Non-upgrade `GET` on a WS path → **426** `{"error": "This endpoint is a WebSocket. Send Upgrade: websocket."}`
- Handshake is **HTTP/1.1 101**, `Sec-WebSocket-Version: 13`.
- Failed `@lrd_auth` / `@lrd_feat_req` on a WS endpoint (if those run before handshake) returns a normal HTTP JSON error, not a half-open socket.

`/whatsplaying` authenticates **after** the handshake (browsers cannot set `Authorization` on the upgrade). See that endpoint.

---

## Endpoints

Unauthenticated unless noted. Capability is listed when `@lrd_auth` is present.

### `GET /version`

Backend version string from `/version` in the image, or `"Unknown version"` outside Docker.

```json
{"version": "LoRaD 0.0.1"}
```

### `GET /apidoc`

HTML catalog generated from endpoint modules (`text/html`).

### `POST /apidoc`

Plain-text catalog by default. Optional JSON body:

| Field | Required | Notes |
|---|---|---|
| `format` | no | `"plain"` (default) or `"html"` |

Unknown format → **400**. HTML response uses `Content-Type: text/html`.

### `GET /openapi`

OpenAPI 3.0 object. Security scheme `AuthHeader` is `Authorization` as `username, token`. Generated metadata treats POST fields as query parameters; prefer this file for request bodies.

---

### `POST /user/auth`

Login. No `Authorization` header.

| Field | Required |
|---|---|
| `username` | yes |
| `password` | yes |

Success:

```json
{"token": "32-hex-chars"}
```

Unknown user or bad password → **401** `{"error": "Login failed"}` (same message either way).

### `GET /user/whoami`

Auth: `BU`.

```json
{"whoami": "admin"}
```

### `POST /user/register`

Auth: `ADMIN`.

| Field | Required | Rules |
|---|---|---|
| `username` | yes | length ≥ 3 |
| `password` | yes | length ≥ 8 |

```json
{"success": true}
```

Validation failure → **400**. Duplicate username → **409** `{"error": "User '<name>' already exists"}`. Internal failure → **500**.

### `POST /user/remove`

Auth: `ADMIN`.

| Field | Required | Rules |
|---|---|---|
| `username` | yes | length ≥ 3 (shorter is rejected as impossible) |

```json
{"success": true}
```

Missing user → **404** `{"error": "User <name> not found."}`.

---

### `GET /locale`

Auth: `BU`. Server `LOCALE` (`EN` or `RU`).

```json
{"locale": "RU"}
```

### `GET /enabled_features`

Auth: `BU`. Copy of config `ENABLED_FEATURES`.

```json
{"features": ["REST", "RESTREAMER", "FILESTREAMER", "FILESTREAMER:YANDEX"]}
```

### `GET /available_players`

Auth: `BU`. Map of technical name → localized display name. Typical keys: `player_streaming` (file / Yandex carousel), `player_radio` (restreamer). Only players that were started are listed.

```json
{"player_radio": "Radio Player", "player_streaming": "Streaming player"}
```

### `GET /current_player`

Auth: `BU`. Technical name of the active player, or `null` before one is started.

```json
{"player": "player_radio"}
```

### `POST /switch_player`

Auth: `ADMIN`. Feature: `RESTREAMER`.

| Field | Required | Notes |
|---|---|---|
| `new_player` | yes | Technical name from `/available_players` |

```json
{"success": true}
```

Unknown player → **400**. Switch lock → **406**. After success, switching is locked for 10 seconds.

---

### WebSocket `GET /whatsplaying`

**Port:** `REST.WS_LISTEN_PORT` (not the REST port). Auth: first text frame, then `BU`. The server **pushes**; the client does not poll.

After `101`, send one JSON text frame within 10 seconds:

```json
{"username": "admin", "token": "<token>"}
```

Bad/expired token or missing `BU` → server sends `{"error": "Unauthorized"}` and closes. Token is rechecked every 30 seconds the same way.

The server then sends a JSON object whenever the serialized state changes, and at least every 30 seconds even if unchanged.

Common fields:

| Field | Type | When |
|---|---|---|
| `player_readable` | string or `null` | Localized player name; `null` if no player |
| `player_tech` | string or `null` | e.g. `player_streaming`, `player_radio` |
| `playing` | string or `null` | Current track / station label |
| `can_skip` | bool | `true` if the current player supports skip and is running (Yandex file player) |
| `can_switch` | bool | `false` while `SWITCH_LOCK` is held or the current player is mid-station-switch. Always present. A change in this field is a push. |

When the file/Yandex player is current, extra fields:

| Field | Type | Notes |
|---|---|---|
| `station_tech` | string | Station id, e.g. `user:onyourwave`, `genre:pop` |
| `station_readable` | string | Display name. `user:onyourwave` is always `"Моя волна"` even if it is not in `/yandex/available_stations` |
| `liked` | bool or `null` | Only if the current source supports liking (Yandex track). `null` if the like lookup failed |
| `length_s` | float | Track length in seconds. Absent when unknown, and always absent for radio (a live restream has no track) |
| `position_s` | float | Playhead in seconds, already corrected for the hub's decode lead. Sent only alongside `length_s` |

Radio (`player_radio`) does **not** include `station_tech` / `station_readable` / playhead / `liked`. Use `/radio/current_station` and `/radio/available_stations` for those. `playing` is whatever `currently_playing` is set to (often empty or a station label).

`position_s` is **not** part of change detection: the server pushes on any other change (including `can_switch`), and otherwise every 30 seconds, so a client should count seconds locally and resync when the two disagree.

Example:

```json
{
  "player_readable": "File Player",
  "player_tech": "player_streaming",
  "playing": "Artist - Track",
  "can_skip": true,
  "can_switch": true,
  "station_tech": "user:onyourwave",
  "station_readable": "Моя волна",
  "liked": true,
  "length_s": 267.0,
  "position_s": 41.5
}
```

No player yet:

```json
{
  "player_readable": null,
  "player_tech": null,
  "playing": null,
  "can_skip": false,
  "can_switch": false
}
```

---

### `GET /yandex/available_stations`

Auth: `BU`. Feature: `FILESTREAMER:YANDEX`.

Map of **readable name → technical id**. Not inverted. Served from the shm pin written at startup (`YaMu.cache_stations_async`); a miss falls through to a live fetch.

```json
{"Pop": "genre:pop", "Meditation": "genre:meditation"}
```

Yandex not initialized → **406** `{"message": "Yandex is not initialized."}`.

`user:onyourwave` (“Моя волна”) may be current without appearing in this map.

### `GET /yandex/current_station`

Auth: `BU`. Feature: `FILESTREAMER:YANDEX`.

```json
{"station": "genre:pop"}
```

Same **406** if Yandex is not initialized.

### `POST /yandex/switch_station`

Auth: `ADMIN`. Feature: `FILESTREAMER:YANDEX`. Current player must be the file/Yandex player.

| Field | Required | Notes |
|---|---|---|
| `new_station` | yes | Technical id (value from `/yandex/available_stations`, not the readable name) |

```json
{"success": true}
```

| Code | Body |
|---|---|
| 400 | Unknown station / missing field |
| 406 | Wrong current player, Yandex not initialized, switch lock, or a station switch already in progress |

Locks switching for 10 seconds on success.

### `POST /yandex/next_track`

Auth: `BU`. Feature: `FILESTREAMER:YANDEX`. JSON body may be `{}`.

Skips to the next buffered Yandex track. One skip at a time (`_skip_busy`).

```json
{"success": true, "playing": "Artist - Track"}
```

| Code | Body |
|---|---|
| 406 | Current source cannot skip |
| 409 | Skip already in progress, or skip failed (busy / buffer) |

### `POST /yandex/like_track`

Auth: `BU`. Feature: `FILESTREAMER:YANDEX`.

| Field | Required | Type |
|---|---|---|
| `liked` | yes | JSON boolean (`true` / `false`) |

```json
{"success": true, "liked": true}
```

Missing or non-boolean `liked` → **400** `{"error": "'liked' must be a boolean."}`. Not a Yandex track → **406** `{"error": "Current source is not a Yandex track."}`. After a successful change, `/whatsplaying` will push an updated `liked` field.

---

### `GET /radio/available_stations`

Auth: `BU`. Feature: `RESTREAMER`.

Map of **readable name → station id** from the stations file (`STATIONS_FILE_PATH`).

```json
{"Love Radio": "love", "Euroradio": "euro"}
```

(Exact keys depend on `stations.json` / `stations.jsonc`.)

### `GET /radio/current_station`

Auth: `BU`. Feature: `RESTREAMER`.

```json
{"station": "love"}
```

The value is the station **id**, not the display name.

### `POST /radio/switch_station`

Auth: `ADMIN`. Feature: `RESTREAMER`. Current player must be the restreamer.

| Field | Required | Notes |
|---|---|---|
| `new_station` | yes | Station id (value from `/radio/available_stations`) |

```json
{"success": true}
```

| Code | Body |
|---|---|
| 400 | Unknown station / missing field |
| 406 | Radio is not the current player, or switch lock |

Locks switching for 10 seconds on success.

---

### `GET /admin/get_config`

Auth: `ADMIN`. Query parameter (not POST):

| Param | Required | Notes |
|---|---|---|
| `key` | yes | Slash-separated path into the config object |

Example: `GET /admin/get_config?key=ENABLED_PROGRAMS/NewsSmall/start_times`

```json
{"ENABLED_PROGRAMS/NewsSmall/start_times": ["10:00", "11:00"]}
```

The response object has a **single** property whose name is the requested `key`.

| Code | When |
|---|---|
| 400 | Missing `key` |
| 401 | `key` contains a sensitive substring (case-insensitive): `username`, `password`, `token`, `key`, `private`, `address`, `database`, `auth` — body `{"message": "Nah."}` |
| 404 | Path segment not found — `{"message": "Could not find key <segment>"}` |

Any non-sensitive existing key can be read. This is **not** limited to `EDITABLE_CONFIG_KEYS`.

### `POST /admin/set_config`

Auth: `ADMIN` (module flag `LOGIN_REQUIRED` is stale; the decorator still requires admin).

| Field | Required | Notes |
|---|---|---|
| `key` | yes | Must be in `EDITABLE_CONFIG_KEYS` |
| `value` | yes | Type depends on the key |

Currently the only editable key is:

`ENABLED_PROGRAMS/NewsSmall/start_times`

`value` must be a JSON array of `H:MM` or `HH:MM` strings (hours 0–23, minutes 00–59), e.g. `["10:00", "11:00"]`. After a successful write, news programs are re-registered.

```json
{"success": true}
```

| Code | When |
|---|---|
| 400 | Missing fields; sensitive substring in `key` (`"Nah."`); key not in the allowlist; invalid `start_times` |
| 404 | Path does not exist in the current config |

Writes replace comments: `write_config` dumps strict JSON back to the loaded config file.

---

## Status code summary

| Code | Typical cause |
|---|---|
| 200 | Success (JSON or HTML) |
| 204 | `OPTIONS` CORS preflight |
| 400 | Bad JSON, bad `Authorization` shape, validation error |
| 401 | Auth failed |
| 403 | Authenticated, insufficient capability |
| 404 | Unknown path or missing config key |
| 405 | Feature disabled, or POST on the WebSocket port |
| 406 | Wrong player, uninitialized Yandex, cannot skip, switch lock |
| 409 | User already exists; skip already in progress |
| 413 | POST body larger than `REST.MAX_DATA_LEN_BYTES` |
| 426 | REST hit a WebSocket path, or WS path without Upgrade |
| 500 | Unhandled server error |

Error bodies are usually `{"error": "…"}`. Some older handlers use `{"message": "…"}` (406 switch lock, 404 config, 401 get_config sensitive key).

## Quick reference

| Method | Path | Port | Auth | Feature |
|---|---|---|---|---|
| GET | `/version` | REST | — | — |
| GET | `/apidoc` | REST | — | — |
| POST | `/apidoc` | REST | — | — |
| GET | `/openapi` | REST | — | — |
| POST | `/user/auth` | REST | — | — |
| GET | `/user/whoami` | REST | BU | — |
| POST | `/user/register` | REST | ADMIN | — |
| POST | `/user/remove` | REST | ADMIN | — |
| GET | `/locale` | REST | BU | — |
| GET | `/enabled_features` | REST | BU | — |
| GET | `/available_players` | REST | BU | — |
| GET | `/current_player` | REST | BU | — |
| POST | `/switch_player` | REST | ADMIN | `RESTREAMER` |
| GET (WS) | `/whatsplaying` | WS | first frame, BU | — |
| GET | `/yandex/available_stations` | REST | BU | `FILESTREAMER:YANDEX` |
| GET | `/yandex/current_station` | REST | BU | `FILESTREAMER:YANDEX` |
| POST | `/yandex/switch_station` | REST | ADMIN | `FILESTREAMER:YANDEX` |
| POST | `/yandex/next_track` | REST | BU | `FILESTREAMER:YANDEX` |
| POST | `/yandex/like_track` | REST | BU | `FILESTREAMER:YANDEX` |
| GET | `/radio/available_stations` | REST | BU | `RESTREAMER` |
| GET | `/radio/current_station` | REST | BU | `RESTREAMER` |
| POST | `/radio/switch_station` | REST | ADMIN | `RESTREAMER` |
| GET | `/admin/get_config` | REST | ADMIN | — |
| POST | `/admin/set_config` | REST | ADMIN | — |
