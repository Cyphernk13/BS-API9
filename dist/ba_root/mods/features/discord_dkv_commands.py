from __future__ import annotations

from datetime import datetime
from pathlib import Path
import json
import re
from typing import Any

import discord
from discord.ext import commands

from playersdata import pdata

try:
    # Reuse the exact staff permission check already used by
    # the working ban system.
    from features.discord_ban_commands import _staff
except Exception:
    def _staff(ctx):
        perms = getattr(ctx.author, "guild_permissions", None)
        return bool(
            perms and (
                getattr(perms, "administrator", False)
                or getattr(perms, "manage_guild", False)
                or getattr(perms, "manage_messages", False)
            )
        )


PBID_RE = re.compile(r"^pb-[A-Za-z0-9+/=_-]+$")


def _valid_pbid(value: str) -> bool:
    return bool(PBID_RE.fullmatch(value.strip()))


def _blacklist() -> dict[str, Any]:
    try:
        data = pdata.get_blacklist()
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


def _dkv_records() -> dict[str, Any]:
    data = _blacklist().get("kick-vote-disabled", {})
    return data if isinstance(data, dict) else {}


def _profiles() -> dict[str, Any]:
    try:
        data = pdata.get_profiles()
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


def _player_name(pbid: str) -> str:
    profiles = _profiles()
    profile = profiles.get(pbid)

    if isinstance(profile, dict):
        for key in ("display_string", "name"):
            value = profile.get(key)
            if value:
                return str(value)

    return "Unknown"


def _parse_until(value: Any):
    if not value:
        return None

    value = str(value).strip()

    try:
        return datetime.fromisoformat(value)
    except Exception:
        pass

    for fmt in (
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
    ):
        try:
            return datetime.strptime(value, fmt)
        except Exception:
            pass

    return None


def _active(record: Any) -> bool:
    if not isinstance(record, dict):
        return False

    until = _parse_until(record.get("till"))

    if until is None:
        # Keep legacy records usable if their expiry cannot be parsed.
        return True

    return datetime.now() < until


def _duration_text(record: dict[str, Any]) -> str:
    until = record.get("till")
    return str(until) if until else "Unknown"


def _embed(title: str, description: str, emoji: str = "🗳️"):
    return discord.Embed(
        title=f"{emoji} {title}",
        description=description,
        colour=discord.Colour.blurple(),
    )


@commands.command(name="dkv")
@commands.check(_staff)
async def dkv(ctx, pbid: str, days: int, *, reason: str):
    pbid = pbid.strip()
    reason = reason.strip()

    if not _valid_pbid(pbid):
        await ctx.send("Invalid PB-ID.")
        return

    if days <= 0:
        await ctx.send("Duration must be greater than 0 days.")
        return

    if not reason:
        await ctx.send("A reason is required.")
        return

    try:
        pdata.disable_kick_vote(pbid, days, reason)
    except TypeError:
        # Compatibility fallback in case the function signature
        # differs slightly on an older loaded module.
        pdata.disable_kick_vote(
            account_id=pbid,
            duration=days,
            reason=reason,
        )

    record = _dkv_records().get(pbid, {})

    name = _player_name(pbid)
    until = _duration_text(record)

    embed = _embed(
        "Kick Vote Disabled",
        (
            f"**Player:** `{name}`\n"
            f"**PB-ID:** `{pbid}`\n"
            f"**Duration:** `{days} days`\n"
            f"**Reason:** {reason}\n"
            f"**Until:** `{until}`"
        ),
    )

    await ctx.send(embed=embed)


@commands.command(name="dkvcheck")
@commands.check(_staff)
async def dkvcheck(ctx, pbid: str):
    pbid = pbid.strip()

    if not _valid_pbid(pbid):
        await ctx.send("Invalid PB-ID.")
        return

    record = _dkv_records().get(pbid)

    if not record or not _active(record):
        await ctx.send(f"`{pbid}` does not currently have kick-vote disabled.")
        return

    name = _player_name(pbid)

    embed = _embed(
        "Kick Vote Status",
        (
            f"**Player:** `{name}`\n"
            f"**PB-ID:** `{pbid}`\n"
            f"**Status:** ✅ Kick vote disabled\n"
            f"**Reason:** {record.get('reason', 'Unknown')}\n"
            f"**Until:** `{_duration_text(record)}`"
        ),
    )

    await ctx.send(embed=embed)


@commands.command(name="dkvlist")
@commands.check(_staff)
async def dkvlist(ctx):
    records = _dkv_records()

    active_records = [
        (pbid, record)
        for pbid, record in records.items()
        if _active(record)
    ]

    if not active_records:
        await ctx.send("No accounts currently have kick vote disabled.")
        return

    # Oldest first is not required; preserve stored order.
    lines = []

    for pbid, record in active_records:
        name = _player_name(pbid)
        reason = str(record.get("reason", "Unknown"))
        until = _duration_text(record)

        lines.append(
            f"**{name}**\n"
            f"`{pbid}`\n"
            f"Reason: {reason}\n"
            f"Until: `{until}`"
        )

    description = "\n\n".join(lines)

    # Discord embed description limit protection.
    if len(description) > 4000:
        description = description[:3990] + "\n..."

    embed = _embed(
        f"Disabled Kick Votes • {len(active_records)}",
        description,
    )

    await ctx.send(embed=embed)


@commands.command(name="ekv")
@commands.check(_staff)
async def ekv(ctx, pbid: str):
    pbid = pbid.strip()

    if not _valid_pbid(pbid):
        await ctx.send("Invalid PB-ID.")
        return

    records = _dkv_records()
    existed = pbid in records

    try:
        pdata.enable_kick_vote(pbid)
    except TypeError:
        pdata.enable_kick_vote(account_id=pbid)

    if not existed:
        await ctx.send(f"`{pbid}` does not currently have kick vote disabled.")
        return

    name = _player_name(pbid)

    embed = _embed(
        "Kick Vote Enabled",
        (
            f"**Player:** `{name}`\n"
            f"**PB-ID:** `{pbid}`\n"
            f"**Status:** ✅ Kick vote enabled"
        ),
        emoji="✅",
    )

    await ctx.send(embed=embed)


def register(bot):
    # Prevent duplicate registration after reloads.
    for name in ("dkv", "dkvcheck", "dkvlist", "ekv"):
        existing = bot.get_command(name)
        if existing is not None:
            bot.remove_command(name)

    bot.add_command(dkv)
    bot.add_command(dkvcheck)
    bot.add_command(dkvlist)
    bot.add_command(ekv)
