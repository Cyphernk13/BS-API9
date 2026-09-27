from __future__ import annotations

import json
import threading
import time
import uuid

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import bascenev1 as bs

from playersdata import pdata
from serverdata import serverdata
from tools import logger


ROOT_MODS = Path(__file__).resolve().parents[1]
SETTING_PATH = ROOT_MODS / "setting.json"


def _load_config() -> dict[str, Any]:
    try:
        root = json.loads(
            SETTING_PATH.read_text(
                encoding="utf-8"
            )
        )
    except Exception:
        root = {}

    return (
        root
        .get("discordbot", {})
        .get("commandConfig", {})
        .get("muteSystem", {})
    )


CFG = _load_config()

MIN_DURATION = int(
    CFG.get(
        "min_duration_days",
        1,
    )
)

MAX_LIST = int(
    CFG.get(
        "max_list_entries",
        10,
    )
)

MAX_DETAILS = int(
    CFG.get(
        "max_details_accounts",
        25,
    )
)

DISPLAY_TZ = ZoneInfo(
    str(
        CFG.get(
            "display_timezone",
            "Asia/Kolkata",
        )
    )
)

RECORD_PATH = (
    ROOT_MODS
    / str(
        CFG.get(
            "record_file",
            "playersdata/mute_records.json",
        )
    )
)

RECORD_PATH.parent.mkdir(
    parents=True,
    exist_ok=True,
)

LOCK = threading.RLock()


class AlreadyMuted(Exception):
    pass


def _load_store() -> dict[str, Any]:
    if not RECORD_PATH.exists():
        return {
            "version": 1,
            "mutes": {},
        }

    try:
        data = json.loads(
            RECORD_PATH.read_text(
                encoding="utf-8"
            )
        )
    except Exception:
        data = {}

    if not isinstance(data, dict):
        data = {}

    if not isinstance(
        data.get("mutes"),
        dict,
    ):
        data["mutes"] = {}

    data.setdefault(
        "version",
        1,
    )

    return data


STORE = _load_store()


def _save_store() -> None:
    temp = RECORD_PATH.with_suffix(
        RECORD_PATH.suffix + ".tmp"
    )

    temp.write_text(
        json.dumps(
            STORE,
            indent=4,
            ensure_ascii=False,
        ) + "\n",
        encoding="utf-8",
    )

    temp.replace(
        RECORD_PATH
    )


def get_config() -> dict[str, Any]:
    return dict(CFG)


def _now() -> float:
    return time.time()


def format_time(
    epoch: float | int | None,
) -> str:
    if epoch is None:
        return "unknown"

    try:
        return (
            datetime.fromtimestamp(
                float(epoch),
                timezone.utc,
            )
            .astimezone(
                DISPLAY_TZ
            )
            .strftime(
                "%d %b %Y %H:%M %Z"
            )
        )
    except Exception:
        return "unknown"


def _profile_data() -> dict[str, Any]:
    try:
        value = pdata.get_profiles()
    except Exception:
        return {}

    return (
        value
        if isinstance(value, dict)
        else {}
    )


def _identity_value(
    value: Any,
) -> str | None:
    if value is None:
        return None

    # IMPORTANT:
    # Do not strip, decode, normalize or transform lastIP.
    # These values are stored exactly as Ballistica provides them.
    value = str(value)

    if value == "":
        return None

    return value


def _profile_name(
    pbid: str,
    profiles: dict[str, Any] | None = None,
) -> str:
    profiles = (
        profiles
        if profiles is not None
        else _profile_data()
    )

    profile = profiles.get(
        pbid,
        {},
    )

    if isinstance(
        profile,
        dict,
    ):
        name = profile.get(
            "name"
        )

        if name:
            return str(name)

    return "Unknown"


def collect_identity_closure(
    pbid: str,
) -> tuple[
    dict[str, list[str]],
    set[str],
    set[str],
    set[str],
]:
    profiles = _profile_data()

    accounts = {
        str(pbid)
    }

    ips: set[str] = set()
    devices: set[str] = set()

    matched_by: dict[str, list[str]] = {
        str(pbid): ["account"]
    }

    changed = True

    while changed:
        changed = False

        for key, raw_profile in profiles.items():
            account = str(key)

            if not isinstance(
                raw_profile,
                dict,
            ):
                continue

            ip = _identity_value(
                raw_profile.get(
                    "lastIP"
                )
            )

            device = _identity_value(
                raw_profile.get(
                    "deviceUUID"
                )
            )

            if account in accounts:
                if ip is not None and ip not in ips:
                    ips.add(ip)
                    changed = True

                if (
                    device is not None
                    and device not in devices
                ):
                    devices.add(device)
                    changed = True

            matched = matched_by.setdefault(
                account,
                [],
            )

            if (
                ip is not None
                and ip in ips
            ):
                if account not in accounts:
                    accounts.add(account)
                    changed = True

                if "ip" not in matched:
                    matched.append("ip")

            if (
                device is not None
                and device in devices
            ):
                if account not in accounts:
                    accounts.add(account)
                    changed = True

                if "device" not in matched:
                    matched.append("device")

    # Make sure every final account has a stable matched_by entry.
    for account in accounts:
        matched_by.setdefault(
            account,
            ["account"]
            if account == str(pbid)
            else [],
        )

    return (
        matched_by,
        accounts,
        ips,
        devices,
    )


def _record_active(
    record: dict[str, Any],
) -> bool:
    try:
        return float(
            record.get(
                "expires_at",
                0,
            )
        ) > _now()
    except Exception:
        return False


def active_records() -> list[dict[str, Any]]:
    with LOCK:
        result = []

        for record in STORE.get(
            "mutes",
            {},
        ).values():
            if not isinstance(
                record,
                dict,
            ):
                continue

            if _record_active(record):
                result.append(record)

        result.sort(
            key=lambda item: float(
                item.get(
                    "created_at",
                    0,
                )
            ),
            reverse=True,
        )

        return result


def matching_records(
    pbid: str | None = None,
    ip: str | None = None,
    device: str | None = None,
) -> list[dict[str, Any]]:
    result = []

    for record in active_records():
        identities = record.get(
            "identities",
            {},
        )

        if not isinstance(
            identities,
            dict,
        ):
            identities = {}

        accounts = identities.get(
            "accounts",
            [],
        )

        ips = identities.get(
            "ips",
            [],
        )

        devices = identities.get(
            "devices",
            [],
        )

        if (
            pbid
            and pbid in accounts
        ):
            result.append(record)
            continue

        if (
            ip is not None
            and ip in ips
        ):
            result.append(record)
            continue

        if (
            device is not None
            and device in devices
        ):
            result.append(record)
            continue

    return result


def _legacy_mute_info(
    pbid: str,
) -> dict[str, Any] | None:
    try:
        data = pdata.get_blacklist()

        if not isinstance(
            data,
            dict,
        ):
            return None

        values = data.get(
            "muted-ids",
            {},
        )

        if not isinstance(
            values,
            dict,
        ):
            return None

        entry = values.get(
            pbid
        )

        if entry is None:
            return None

        if not isinstance(
            entry,
            dict,
        ):
            return {
                "expires_at": None,
                "reason": "Legacy mute",
            }

        till = entry.get(
            "till"
        )

        expires_at = None

        if till:
            try:
                expires_at = (
                    datetime.strptime(
                        str(till),
                        "%Y-%m-%d %H:%M:%S",
                    )
                    .replace(
                        tzinfo=DISPLAY_TZ
                    )
                    .timestamp()
                )
            except Exception:
                expires_at = None

        if (
            expires_at is not None
            and expires_at <= _now()
        ):
            return None

        return {
            "expires_at": expires_at,
            "reason": str(
                entry.get(
                    "reason",
                    "Legacy mute",
                )
            ),
        }

    except Exception:
        return None


def legacy_mute_info(
    pbid: str,
) -> dict[str, Any] | None:
    return _legacy_mute_info(
        pbid
    )


def is_account_muted(
    pbid: str,
) -> bool:
    if matching_records(
        pbid=pbid
    ):
        return True

    return (
        _legacy_mute_info(
            pbid
        )
        is not None
    )


def create_mute(
    pbid: str,
    days: int,
    reason: str,
    created_by: dict[str, str],
) -> dict[str, Any]:

    (
        matched_by,
        accounts,
        ips,
        devices,
    ) = collect_identity_closure(
        pbid
    )

    # A target already covered through PBID, IP or device
    # must not create another overlapping mute.
    target_ip = None
    target_device = None

    profiles = _profile_data()
    target_profile = profiles.get(
        pbid,
        {},
    )

    if isinstance(
        target_profile,
        dict,
    ):
        target_ip = _identity_value(
            target_profile.get(
                "lastIP"
            )
        )
        target_device = _identity_value(
            target_profile.get(
                "deviceUUID"
            )
        )

    if (
        matching_records(
            pbid=pbid,
            ip=target_ip,
            device=target_device,
        )
        or _legacy_mute_info(pbid)
    ):
        raise AlreadyMuted()

    created = _now()
    expires = (
        created
        + days * 86400
    )

    mute_id = (
        "MUTE-"
        + datetime.now(
            timezone.utc
        ).strftime(
            "%Y%m%d"
        )
        + "-"
        + uuid.uuid4().hex[
            :8
        ].upper()
    )

    linked_accounts = []

    for account in sorted(
        accounts
    ):
        linked_accounts.append(
            {
                "pbid": account,
                "name": _profile_name(
                    account,
                    profiles,
                ),
                "matched_by": list(
                    matched_by.get(
                        account,
                        [],
                    )
                ),
            }
        )

    record = {
        "mute_id": mute_id,
        "source_type": "account",
        "source": pbid,
        "source_name": _profile_name(
            pbid,
            profiles,
        ),
        "reason": reason,
        "created_at": created,
        "expires_at": expires,
        "created_by": dict(
            created_by
        ),
        "identities": {
            "accounts": sorted(
                accounts
            ),
            "ips": sorted(
                ips
            ),
            "devices": sorted(
                devices
            ),
        },
        "linked_accounts": linked_accounts,
    }

    with LOCK:
        STORE.setdefault(
            "mutes",
            {},
        )[mute_id] = record

        _save_store()

    # Keep the legacy account mute system in sync.
    for account in accounts:
        try:
            pdata.mute(
                account,
                days,
                reason,
            )
        except Exception:
            logger.log(
                f"Failed to apply legacy mute to {account}.",
                mtype="sys",
            )

        profile = profiles.get(
            account
        )

        if isinstance(
            profile,
            dict,
        ):
            profile["isMuted"] = True

    try:
        pdata.commit_profiles(
            profiles
        )
    except Exception:
        pass

    return record


def _account_has_other_active_mute(
    pbid: str,
) -> bool:
    return bool(
        matching_records(
            pbid=pbid
        )
    )


def unmute_pbid(
    pbid: str,
) -> dict[str, Any]:
    records = matching_records(
        pbid=pbid
    )

    removed_ids = []
    accounts: set[str] = set()

    for record in records:
        mute_id = str(
            record.get(
                "mute_id",
                "",
            )
        )

        if mute_id:
            removed_ids.append(
                mute_id
            )

        identities = record.get(
            "identities",
            {},
        )

        if isinstance(
            identities,
            dict,
        ):
            for account in identities.get(
                "accounts",
                [],
            ):
                accounts.add(
                    str(account)
                )

    # Also support old account-only mute entries.
    legacy_exists = (
        _legacy_mute_info(pbid)
        is not None
    )

    if not records and not legacy_exists:
        return {
            "removed": 0,
            "accounts": [],
        }

    accounts.add(
        pbid
    )

    with LOCK:
        for mute_id in removed_ids:
            STORE.get(
                "mutes",
                {},
            ).pop(
                mute_id,
                None,
            )

        _save_store()

    profiles = _profile_data()

    unmuted = []

    for account in sorted(
        accounts
    ):
        if _account_has_other_active_mute(
            account
        ):
            continue

        try:
            pdata.unmute(
                account
            )
        except Exception:
            logger.log(
                f"Failed to remove legacy mute from {account}.",
                mtype="sys",
            )

        profile = profiles.get(
            account
        )

        if isinstance(
            profile,
            dict,
        ):
            profile["isMuted"] = False

        unmuted.append(
            account
        )

    try:
        pdata.commit_profiles(
            profiles
        )
    except Exception:
        pass

    return {
        "removed": len(
            removed_ids
        ),
        "accounts": unmuted,
    }


def _client_identity(
    client_id: int,
) -> tuple[
    str | None,
    str,
    str | None,
    str | None,
]:
    pbid = None
    name = "<player>"
    ip = None
    device = None

    try:
        roster = bs.get_game_roster()
    except Exception:
        roster = []

    for entry in roster:
        if not isinstance(
            entry,
            dict,
        ):
            continue

        if entry.get(
            "client_id"
        ) != client_id:
            continue

        raw_pbid = entry.get(
            "account_id"
        )

        if raw_pbid:
            pbid = str(
                raw_pbid
            )

        players = entry.get(
            "players",
            [],
        )

        if isinstance(
            players,
            list,
        ) and players:
            player = players[0]

            if isinstance(
                player,
                dict,
            ):
                current_name = (
                    player.get(
                        "name_full"
                    )
                    or player.get(
                        "name"
                    )
                )

                if current_name:
                    name = str(
                        current_name
                    )

        break

    if pbid:
        profile = (
            serverdata.clients.get(
                pbid,
                {}
            )
        )

        if not isinstance(
            profile,
            dict,
        ):
            profile = {}

        ip = _identity_value(
            profile.get(
                "lastIP"
            )
        )

        device = _identity_value(
            profile.get(
                "deviceUUID"
            )
        )

        if (
            ip is None
            or device is None
        ):
            stored = _profile_data().get(
                pbid,
                {}
            )

            if isinstance(
                stored,
                dict,
            ):
                if ip is None:
                    ip = _identity_value(
                        stored.get(
                            "lastIP"
                        )
                    )

                if device is None:
                    device = _identity_value(
                        stored.get(
                            "deviceUUID"
                        )
                    )

    return (
        pbid,
        name,
        ip,
        device,
    )


def get_client_mute_state(
    client_id: int,
) -> tuple[
    bool,
    str,
    float | None,
    str,
]:
    (
        pbid,
        name,
        ip,
        device,
    ) = _client_identity(
        client_id
    )

    if not pbid:
        return (
            False,
            name,
            None,
            "",
        )

    records = matching_records(
        pbid=pbid,
        ip=ip,
        device=device,
    )

    if records:
        record = max(
            records,
            key=lambda item: float(
                item.get(
                    "expires_at",
                    0,
                )
            ),
        )

        return (
            True,
            name,
            float(
                record.get(
                    "expires_at",
                    0,
                )
            ),
            str(
                record.get(
                    "reason",
                    "",
                )
            ),
        )

    legacy = _legacy_mute_info(
        pbid
    )

    if legacy is not None:
        return (
            True,
            name,
            legacy.get(
                "expires_at"
            ),
            legacy.get(
                "reason",
                "Muted",
            ),
        )

    return (
        False,
        name,
        None,
        "",
    )


def notify_muted(
    client_id: int,
    name: str,
    expires_at: float | None,
    reason: str,
) -> None:
    messages = CFG.get(
        "messages",
        {},
    )

    template = str(
        messages.get(
            "chat_notice",
            "{name}: You are muted until {expires}. Reason: {reason}",
        )
    )

    safe_name = str(
        name
        or "<player>"
    ).replace(
        "\n",
        " ",
    )

    safe_reason = str(
        reason
        or "Muted"
    ).replace(
        "\n",
        " ",
    )

    message = template.format(
        name=safe_name,
        expires=format_time(
            expires_at
        ),
        reason=safe_reason,
    )

    try:
        bs.chatmessage(
            message,
            clients=[client_id],
        )
    except Exception as exc:
        logger.log(
            f"Failed to notify muted client {client_id}: {exc}",
            mtype="sys",
        )
