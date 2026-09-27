
"""PlayerData, PlayerStats and Playtime Discord commands."""

from __future__ import annotations

from typing import Any

import discord
from discord.ext import commands


def register(botmod: Any) -> None:
    """Register Phase 2B commands exactly once."""

    if getattr(
        botmod,
        "_phase2b_registered",
        False,
    ):
        return

    client = botmod.client

    # --------------------------------------------------------
    # Helpers
    # --------------------------------------------------------

    def is_staff(ctx) -> bool:
        try:
            user_id = int(
                ctx.author.id
            )
        except BaseException:
            return False

        if user_id in getattr(
            botmod,
            "allowed_user_ids",
            set(),
        ):
            return True

        if ctx.guild is not None:
            try:
                return user_id == int(
                    ctx.guild.owner_id
                )
            except BaseException:
                pass

        return False


    def safe(value) -> str:
        return (
            str(value)
            .replace("`", "'")
            .replace("@", "@\u200b")
        )


    def code(value) -> str:
        return f"`{safe(value)}`"


    def codeblock(value) -> str:
        return (
            "```text\n"
            + safe(value)
            + "\n```"
        )


    def embed(
        title: str,
        colour: int | None = None,
    ):
        if colour is None:
            try:
                colour = botmod._ui_color(
                    "colors.accent"
                )
            except BaseException:
                colour = 0x8B5CF6

        return discord.Embed(
            title=title,
            colour=discord.Colour(
                int(colour)
            ),
        )


    def footer(e):
        try:
            text = (
                botmod.commandConfig
                .get("text", {})
                .get("footer", "")
            )
        except BaseException:
            text = "Cypher Duels"

        if text:
            e.set_footer(
                text=text
            )


    def get_profiles():
        from playersdata import pdata

        return pdata.get_profiles()


    def profile_matches(
        query: str,
    ):
        query = str(
            query
        ).strip()

        if not query:
            return []

        query_cf = query.casefold()

        profiles = get_profiles()

        matches = []

        # Exact account id first.
        for account_id, profile in (
            profiles.items()
        ):
            if str(
                account_id
            ).casefold() == query_cf:
                matches.append(
                    (
                        str(account_id),
                        profile,
                    )
                )

        if matches:
            return matches

        # Exact current name/display string.
        for account_id, profile in (
            profiles.items()
        ):
            name = str(
                profile.get(
                    "name",
                    "",
                )
            )

            displays = profile.get(
                "display_string",
                [],
            )

            if isinstance(
                displays,
                str,
            ):
                displays = [
                    displays
                ]

            if (
                name.casefold()
                == query_cf
            ):
                matches.append(
                    (
                        str(account_id),
                        profile,
                    )
                )
                continue

            if any(
                str(display).casefold()
                == query_cf
                for display in displays
            ):
                matches.append(
                    (
                        str(account_id),
                        profile,
                    )
                )

        if matches:
            return matches

        # Finally substring matching.
        for account_id, profile in (
            profiles.items()
        ):
            name = str(
                profile.get(
                    "name",
                    "",
                )
            )

            displays = profile.get(
                "display_string",
                [],
            )

            if isinstance(
                displays,
                str,
            ):
                displays = [
                    displays
                ]

            search_values = [
                name,
                *[
                    str(display)
                    for display in displays
                ],
            ]

            if any(
                query_cf in value.casefold()
                for value in search_values
            ):
                matches.append(
                    (
                        str(account_id),
                        profile,
                    )
                )

        return matches


    def all_profiles():
        return get_profiles()


    def format_duration(seconds):
        try:
            seconds = max(
                0,
                int(
                    float(seconds)
                ),
            )
        except (
            TypeError,
            ValueError,
        ):
            return str(
                seconds
            )

        days, remainder = divmod(
            seconds,
            86400,
        )

        hours, remainder = divmod(
            remainder,
            3600,
        )

        minutes, seconds = divmod(
            remainder,
            60,
        )

        parts = []

        if days:
            parts.append(
                f"{days}d"
            )

        if hours:
            parts.append(
                f"{hours}h"
            )

        if minutes:
            parts.append(
                f"{minutes}m"
            )

        if not parts:
            parts.append(
                f"{seconds}s"
            )

        return " ".join(
            parts
        )


    def player_identity(
        account_id,
        profile,
    ):
        name = str(
            profile.get(
                "name",
                "<unknown>",
            )
        )

        displays = profile.get(
            "display_string",
            [],
        )

        if isinstance(
            displays,
            str,
        ):
            displays = [
                displays
            ]

        return (
            name,
            displays,
        )


    def stats_for_account(
        account_id,
    ):
        from stats import mystats

        try:
            result = mystats.get_stats_by_id(
                account_id
            )

            if isinstance(
                result,
                dict,
            ):
                return result
        except BaseException:
            pass

        try:
            cached = mystats.get_cached_stats()

            if isinstance(
                cached,
                dict,
            ):
                return cached.get(
                    account_id
                )
        except BaseException:
            pass

        try:
            all_stats = mystats.get_all_stats()

            if isinstance(
                all_stats,
                dict,
            ):
                return all_stats.get(
                    account_id
                )
        except BaseException:
            pass

        return None


    def stat_value(
        data,
        *keys,
        default="N/A",
    ):
        if not isinstance(
            data,
            dict,
        ):
            return default

        for key in keys:
            if key in data:
                return data[key]

        return default


    def leaderboard_stats():
        from stats import mystats

        try:
            all_stats = mystats.get_all_stats()

            if not isinstance(
                all_stats,
                dict,
            ):
                return []

        except BaseException:
            return []

        # Prefer the server's own ordering implementation.
        try:
            sorted_stats = (
                mystats.get_sorted_stats(
                    all_stats
                )
            )

            if sorted_stats:
                normalized = []

                for item in sorted_stats:

                    if (
                        isinstance(
                            item,
                            (tuple, list),
                        )
                        and len(item) == 2
                    ):
                        normalized.append(
                            (
                                str(item[0]),
                                item[1],
                            )
                        )

                    elif isinstance(
                        item,
                        dict,
                    ):
                        account_id = (
                            item.get(
                                "aid"
                            )
                            or item.get(
                                "account_id"
                            )
                            or item.get(
                                "id"
                            )
                        )

                        if account_id is not None:
                            normalized.append(
                                (
                                    str(
                                        account_id
                                    ),
                                    item,
                                )
                            )

                if normalized:
                    return normalized

        except BaseException:
            pass

        # Flexible fallback for existing stats schemas.
        items = list(
            all_stats.items()
        )

        def score_key(item):
            data = item[1]

            try:
                return float(
                    stat_value(
                        data,
                        "rank",
                        default=10**12,
                    )
                )
            except (
                TypeError,
                ValueError,
            ):
                try:
                    return -float(
                        stat_value(
                            data,
                            "scores",
                            "score",
                            default=0,
                        )
                    )
                except (
                    TypeError,
                    ValueError,
                ):
                    return 10**12

        return sorted(
            items,
            key=score_key,
        )


    # --------------------------------------------------------
    # PlayerData commands
    # --------------------------------------------------------

    async def playerdata(
        ctx,
        *,
        query="",
    ):
        if not is_staff(
            ctx
        ):
            await ctx.send(
                "⛔ This command is restricted to staff."
            )
            return

        matches = profile_matches(
            query
        )

        if not matches:
            await ctx.send(
                f"Player `{safe(query)}` not found."
            )
            return

        account_id, profile = matches[0]

        name, displays = player_identity(
            account_id,
            profile,
        )

        verified = profile.get(
            "verified",
            False,
        )

        banned = profile.get(
            "isBan",
            False,
        )

        muted = profile.get(
            "isMuted",
            False,
        )

        ip = profile.get(
            "lastIP",
            "",
        )

        device = profile.get(
            "deviceUUID",
            "",
        )

        embed_msg = embed(
            f"🧑 PLAYER DATA • {safe(name)}"
        )

        embed_msg.add_field(
            name="🆔 Account ID",
            value=codeblock(
                account_id
            ),
            inline=False,
        )

        embed_msg.add_field(
            name="👤 Current Name",
            value=code(name),
            inline=True,
        )

        embed_msg.add_field(
            name="🎭 Status",
            value=(
                f"{'✅ Verified' if verified else '❌ Unverified'}\n"
                f"{'🔨 Banned' if banned else '🟢 Not banned'}\n"
                f"{'🔇 Muted' if muted else '🔊 Not muted'}"
            ),
            inline=True,
        )

        if displays:
            display_text = "\n".join(
                code(display)
                for display in displays
            )

            embed_msg.add_field(
                name="📝 Display Names",
                value=display_text[
                    :1024
                ],
                inline=False,
            )

        if ip:
            embed_msg.add_field(
                name="🌐 Last IP",
                value=codeblock(ip),
                inline=False,
            )

        if device:
            embed_msg.add_field(
                name="📱 Device ID",
                value=codeblock(device),
                inline=False,
            )

        embed_msg.add_field(
            name="⏱️ Playtime",
            value=code(
                format_duration(
                    profile.get(
                        "totaltimeplayer",
                        0,
                    )
                )
            ),
            inline=True,
        )

        embed_msg.add_field(
            name="⚠️ Warnings",
            value=code(
                profile.get(
                    "warnCount",
                    0,
                )
            ),
            inline=True,
        )

        footer(
            embed_msg
        )

        await ctx.send(
            embed=embed_msg
        )


    async def findplayer(
        ctx,
        *,
        query="",
    ):
        if not is_staff(
            ctx
        ):
            await ctx.send(
                "⛔ This command is restricted to staff."
            )
            return

        matches = profile_matches(
            query
        )

        if not matches:
            await ctx.send(
                f"No player matching `{safe(query)}` was found."
            )
            return

        account_id, profile = matches[0]
        name, _ = player_identity(
            account_id,
            profile,
        )

        await ctx.send(
            "**🧑 PLAYER FOUND**\n"
            "```text\n"
            f"Name: {name}\n"
            f"Account ID: {account_id}\n"
            "```"
        )


    async def findplayerall(
        ctx,
        *,
        query="",
    ):
        if not is_staff(
            ctx
        ):
            await ctx.send(
                "⛔ This command is restricted to staff."
            )
            return

        matches = profile_matches(
            query
        )

        if not matches:
            await ctx.send(
                f"No players matching `{safe(query)}` were found."
            )
            return

        lines = []

        for index, (
            account_id,
            profile,
        ) in enumerate(
            matches,
            start=1,
        ):
            name, _ = player_identity(
                account_id,
                profile,
            )

            lines.append(
                f"{index}. {name} | {account_id}"
            )

        await ctx.send(
            "🧑 **PLAYER SEARCH**\n"
            "```text\n"
            + "\n".join(lines)[:1800]
            + "\n```"
        )


    def search_field(
        field,
        query,
    ):
        query = str(
            query
        ).strip().casefold()

        if not query:
            return []

        results = []

        for account_id, profile in (
            all_profiles().items()
        ):
            value = profile.get(
                field,
                "",
            )

            if value is None:
                continue

            if query in str(
                value
            ).casefold():
                results.append(
                    (
                        str(account_id),
                        profile,
                    )
                )

        return results


    async def findip(
        ctx,
        query="",
    ):
        if not is_staff(
            ctx
        ):
            await ctx.send(
                "⛔ This command is restricted to staff."
            )
            return

        matches = search_field(
            "lastIP",
            query,
        )

        if not matches:
            await ctx.send(
                f"No player found for IP `{safe(query)}`."
            )
            return

        account_id, profile = matches[0]
        name, _ = player_identity(
            account_id,
            profile,
        )

        await ctx.send(
            "**🌐 IP MATCH**\n"
            f"Player: {code(name)}\n"
            f"IP: {codeblock(query)}\n"
            f"Account: {codeblock(account_id)}"
        )


    async def findipall(
        ctx,
        query="",
    ):
        if not is_staff(
            ctx
        ):
            await ctx.send(
                "⛔ This command is restricted to staff."
            )
            return

        matches = search_field(
            "lastIP",
            query,
        )

        if not matches:
            await ctx.send(
                f"No players found for IP `{safe(query)}`."
            )
            return

        lines = []

        for index, (
            account_id,
            profile,
        ) in enumerate(
            matches,
            start=1,
        ):
            name, _ = player_identity(
                account_id,
                profile,
            )

            ip = profile.get(
                "lastIP",
                "",
            )

            lines.append(
                f"{index}. {name} | {ip} | {account_id}"
            )

        await ctx.send(
            "🌐 **ALL IP MATCHES**\n"
            "```text\n"
            + "\n".join(lines)[:1800]
            + "\n```"
        )


    async def finddevice(
        ctx,
        *,
        query="",
    ):
        if not is_staff(
            ctx
        ):
            await ctx.send(
                "⛔ This command is restricted to staff."
            )
            return

        matches = search_field(
            "deviceUUID",
            query,
        )

        if not matches:
            await ctx.send(
                f"No player found for device `{safe(query)}`."
            )
            return

        account_id, profile = matches[0]
        name, _ = player_identity(
            account_id,
            profile,
        )

        await ctx.send(
            "📱 **DEVICE MATCH**\n"
            f"Player: {code(name)}\n"
            f"Device: {codeblock(query)}\n"
            f"Account: {codeblock(account_id)}"
        )


    async def finddeviceall(
        ctx,
        *,
        query="",
    ):
        if not is_staff(
            ctx
        ):
            await ctx.send(
                "⛔ This command is restricted to staff."
            )
            return

        matches = search_field(
            "deviceUUID",
            query,
        )

        if not matches:
            await ctx.send(
                f"No players found for device `{safe(query)}`."
            )
            return

        lines = []

        for index, (
            account_id,
            profile,
        ) in enumerate(
            matches,
            start=1,
        ):
            name, _ = player_identity(
                account_id,
                profile,
            )

            device = profile.get(
                "deviceUUID",
                "",
            )

            lines.append(
                f"{index}. {name} | {device} | {account_id}"
            )

        await ctx.send(
            "📱 **ALL DEVICE MATCHES**\n"
            "```text\n"
            + "\n".join(lines)[:1800]
            + "\n```"
        )


    async def compareplayer(
        ctx,
        player1,
        player2,
    ):
        if not is_staff(
            ctx
        ):
            await ctx.send(
                "⛔ This command is restricted to staff."
            )
            return

        first = profile_matches(
            player1
        )

        second = profile_matches(
            player2
        )

        if not first or not second:
            await ctx.send(
                "One or both players could not be found."
            )
            return

        account1, profile1 = first[0]
        account2, profile2 = second[0]

        name1, _ = player_identity(
            account1,
            profile1,
        )

        name2, _ = player_identity(
            account2,
            profile2,
        )

        ip1 = profile1.get(
            "lastIP"
        )

        ip2 = profile2.get(
            "lastIP"
        )

        device1 = profile1.get(
            "deviceUUID"
        )

        device2 = profile2.get(
            "deviceUUID"
        )

        shared_ip = (
            bool(ip1)
            and bool(ip2)
            and ip1 == ip2
        )

        shared_device = (
            bool(device1)
            and bool(device2)
            and device1 == device2
        )

        e = embed(
            "🔎 PLAYER COMPARISON"
        )

        e.add_field(
            name="PLAYER 1",
            value=(
                f"{code(name1)}\n"
                f"{codeblock(account1)}\n"
                f"IP: {code(ip1 or 'N/A')}\n"
                f"Device: {code(device1 or 'N/A')}"
            )[:1024],
            inline=True,
        )

        e.add_field(
            name="PLAYER 2",
            value=(
                f"{code(name2)}\n"
                f"{codeblock(account2)}\n"
                f"IP: {code(ip2 or 'N/A')}\n"
                f"Device: {code(device2 or 'N/A')}"
            )[:1024],
            inline=True,
        )

        e.add_field(
            name="RESULT",
            value=(
                f"Shared IP: "
                f"{'✅ YES' if shared_ip else '❌ NO'}\n"
                f"Shared Device: "
                f"{'✅ YES' if shared_device else '❌ NO'}"
            ),
            inline=False,
        )

        footer(e)

        await ctx.send(
            embed=e
        )


    async def gp(
        ctx,
        *,
        query="",
    ):
        if not is_staff(
            ctx
        ):
            await ctx.send(
                "⛔ This command is restricted to staff."
            )
            return

        matches = profile_matches(
            query
        )

        if not matches:
            await ctx.send(
                f"Player `{safe(query)}` not found."
            )
            return

        account_id, profile = matches[0]
        name, displays = player_identity(
            account_id,
            profile,
        )

        e = embed(
            f"👤 PROFILE • {safe(name)}"
        )

        e.add_field(
            name="Account",
            value=codeblock(
                account_id
            ),
            inline=False,
        )

        if displays:
            e.add_field(
                name="Display Strings",
                value="\n".join(
                    code(display)
                    for display in displays
                )[:1024],
                inline=False,
            )

        e.add_field(
            name="Verified",
            value=(
                "✅"
                if profile.get(
                    "verified",
                    False,
                )
                else "❌"
            ),
            inline=True,
        )

        e.add_field(
            name="Banned",
            value=(
                "🔨"
                if profile.get(
                    "isBan",
                    False,
                )
                else "🟢"
            ),
            inline=True,
        )

        e.add_field(
            name="Muted",
            value=(
                "🔇"
                if profile.get(
                    "isMuted",
                    False,
                )
                else "🔊"
            ),
            inline=True,
        )

        footer(e)

        await ctx.send(
            embed=e
        )


    async def verifiedmembers(
        ctx,
    ):
        if not is_staff(
            ctx
        ):
            await ctx.send(
                "⛔ This command is restricted to staff."
            )
            return

        profiles = all_profiles()

        total = sum(
            1
            for profile in profiles.values()
            if bool(
                profile.get(
                    "verified",
                    False,
                )
            )
        )

        await ctx.send(
            "✅ **VERIFIED MEMBERS**\n"
            f"Total verified profiles: `{total}`"
        )


    # --------------------------------------------------------
    # PlayerStats
    # --------------------------------------------------------

    async def pstats(
        ctx,
        *,
        query="",
    ):
        matches = profile_matches(
            query
        )

        if not matches:
            await ctx.send(
                f"Player `{safe(query)}` not found."
            )
            return

        account_id, profile = matches[0]

        name, _ = player_identity(
            account_id,
            profile,
        )

        data = stats_for_account(
            account_id
        )

        if not data:
            await ctx.send(
                "📊 No statistics found for "
                f"{code(name)}."
            )
            return

        score = stat_value(
            data,
            "scores",
            "score",
        )

        kills = stat_value(
            data,
            "kills",
        )

        deaths = stat_value(
            data,
            "deaths",
        )

        rank = stat_value(
            data,
            "rank",
        )

        games = stat_value(
            data,
            "games",
        )

        e = embed(
            f"📊 PLAYER STATS • {safe(name)}"
        )

        e.add_field(
            name="🏅 Rank",
            value=code(rank),
            inline=True,
        )

        e.add_field(
            name="⭐ Score",
            value=code(score),
            inline=True,
        )

        e.add_field(
            name="🎮 Games",
            value=code(games),
            inline=True,
        )

        e.add_field(
            name="⚔️ Kills",
            value=code(kills),
            inline=True,
        )

        e.add_field(
            name="💀 Deaths",
            value=code(deaths),
            inline=True,
        )

        if (
            isinstance(
                kills,
                (int, float),
            )
            and isinstance(
                deaths,
                (int, float),
            )
        ):
            kd = (
                kills / deaths
                if deaths
                else float(kills)
            )

            kd_text = (
                f"{kd:.2f}"
            )
        else:
            kd_text = "N/A"

        e.add_field(
            name="📈 K/D",
            value=code(
                kd_text
            ),
            inline=True,
        )

        e.add_field(
            name="🆔 Account",
            value=codeblock(
                account_id
            ),
            inline=False,
        )

        footer(e)

        await ctx.send(
            embed=e
        )


    async def top(
        ctx,
    ):
        rows = leaderboard_stats()

        if not rows:
            await ctx.send(
                "```text\nNo statistics available.\n```"
            )
            return

        limit = 10
        medals = (
            "🥇",
            "🥈",
            "🥉",
        )

        lines = []

        for position, (
            account_id,
            data,
        ) in enumerate(
            rows[:limit],
            start=1,
        ):
            profile = (
                all_profiles().get(
                    account_id,
                    {},
                )
            )

            name = str(
                data.get(
                    "name",
                    profile.get(
                        "name",
                        account_id,
                    )
                    if isinstance(
                        profile,
                        dict,
                    )
                    else account_id,
                )
            )

            score = stat_value(
                data,
                "scores",
                "score",
                default="N/A",
            )

            kills = stat_value(
                data,
                "kills",
                default="N/A",
            )

            deaths = stat_value(
                data,
                "deaths",
                default="N/A",
            )

            prefix = (
                medals[position - 1]
                if position <= 3
                else f"{position}."
            )

            lines.append(
                f"{prefix} "
                f"{safe(name)}"
                f" | S:{score}"
                f" | K:{kills}"
                f" D:{deaths}"
            )

        await ctx.send(
            "🏆 **CYPHER DUELS • TOP 10**\n"
            "```text\n"
            + "\n".join(lines)[:1800]
            + "\n```"
        )


    # --------------------------------------------------------
    # Playtime
    # --------------------------------------------------------

    async def playtime(
        ctx,
        *,
        query="",
    ):
        matches = profile_matches(
            query
        )

        if not matches:
            await ctx.send(
                f"Player `{safe(query)}` not found."
            )
            return

        account_id, profile = matches[0]

        name, _ = player_identity(
            account_id,
            profile,
        )

        raw_seconds = profile.get(
            "totaltimeplayer",
            0,
        )

        formatted = format_duration(
            raw_seconds
        )

        await ctx.send(
            "⏱️ **PLAYTIME**\n"
            f"Player: {code(name)}\n"
            f"Total: {code(formatted)}\n"
            f"Account: {codeblock(account_id)}"
        )


    async def topplaytime(
        ctx,
    ):
        profiles = all_profiles()

        rows = []

        for account_id, profile in (
            profiles.items()
        ):

            try:
                seconds = int(
                    float(
                        profile.get(
                            "totaltimeplayer",
                            0,
                        )
                    )
                )
            except (
                TypeError,
                ValueError,
            ):
                seconds = 0

            if seconds <= 0:
                continue

            name = str(
                profile.get(
                    "name",
                    account_id,
                )
            )

            rows.append(
                (
                    seconds,
                    name,
                    str(account_id),
                )
            )

        rows.sort(
            key=lambda item: item[0],
            reverse=True,
        )

        lines = []

        for position, (
            seconds,
            name,
            account_id,
        ) in enumerate(
            rows[:10],
            start=1,
        ):
            lines.append(
                f"{position}. "
                f"{safe(name)}"
                f" | {format_duration(seconds)}"
            )

        if not lines:
            await ctx.send(
                "```text\nNo playtime data available.\n```"
            )
            return

        await ctx.send(
            "⏱️ **TOP PLAYTIME**\n"
            "```text\n"
            + "\n".join(lines)[:1800]
            + "\n```"
        )


    # --------------------------------------------------------
    # Registration
    # --------------------------------------------------------

    def add(
        func,
        name,
        help_text,
    ):
        existing = client.get_command(
            name
        )

        if existing is not None:
            client.remove_command(
                existing.name
            )

        client.add_command(
            commands.Command(
                func,
                name=name,
                help=help_text,
            )
        )


    add(
        playerdata,
        "playerdata",
        "Get detailed player data.",
    )

    add(
        findplayer,
        "findplayer",
        "Find the first player by name.",
    )

    add(
        findplayerall,
        "findplayerall",
        "Find all players by name.",
    )

    add(
        findip,
        "findip",
        "Find the first player by IP.",
    )

    add(
        findipall,
        "findipall",
        "Find all players by IP.",
    )

    add(
        finddevice,
        "finddevice",
        "Find the first player by device.",
    )

    add(
        finddeviceall,
        "finddeviceall",
        "Find all players by device.",
    )

    add(
        compareplayer,
        "compareplayer",
        "Compare two player profiles.",
    )

    add(
        gp,
        "gp",
        "Get a player profile.",
    )

    add(
        verifiedmembers,
        "verifiedmembers",
        "Show verified profile count.",
    )

    add(
        pstats,
        "pstats",
        "Show player statistics.",
    )

    add(
        top,
        "top",
        "Show the player leaderboard.",
    )

    add(
        playtime,
        "playtime",
        "Show player playtime.",
    )

    add(
        topplaytime,
        "topplaytime",
        "Show the playtime leaderboard.",
    )

    botmod._phase2b_registered = True

    print(
        "Discord command system: Phase 2B registered"
    )
