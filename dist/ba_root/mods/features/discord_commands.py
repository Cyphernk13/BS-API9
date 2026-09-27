
"""Config-driven Cypher Duels Discord command system."""

from __future__ import annotations

from typing import Any

import discord
from discord.ext import commands


def register(botmod: Any) -> None:
    """Register the canonical command set."""

    if getattr(
        botmod,
        "_command_system_registered",
        False,
    ):
        return

    config = botmod.commandConfig

    if not config.get(
        "enabled",
        True,
    ):
        return

    client = botmod.client

    # We own the help command.
    existing_help = client.get_command(
        "help"
    )

    if existing_help is not None:
        client.remove_command(
            existing_help.name
        )

    async def help_command(
        ctx,
        category: str = "",
        command_name: str = "",
    ):
        category = category.strip()
        command_name = command_name.strip()

        if not category:

            embed = discord.Embed(
                title=config["text"]["helpTitle"],
                description=config["text"]["helpDescription"].format(
                    prefix=botmod.bot_prefix
                ),
                colour=discord.Colour(
                    botmod._ui_color(
                        "colors.accent"
                    )
                ),
            )

            embed.add_field(
                name=config["text"]["prefixLabel"],
                value=f"`{botmod.bot_prefix}`",
                inline=True,
            )

            available = []

            for category_name, category_data in (
                config["categories"].items()
            ):

                for name, spec in (
                    category_data["commands"].items()
                ):

                    if spec.get(
                        "implemented",
                        False,
                    ):

                        marker = config["text"]["implemented"]

                        permission = spec.get(
                            "permission",
                            "public",
                        )

                        if permission == "staff":
                            marker += " "

                        available.append(
                            f"{marker} "
                            f"`{botmod.bot_prefix}{name}`"
                        )

            embed.add_field(
                name=config["text"]["availableLabel"],
                value=(
                    "\n".join(
                        available
                    )
                    if available
                    else config["text"]["noCommands"]
                )[:1024],
                inline=False,
            )

            category_lines = []

            for category_name, category_data in (
                config["categories"].items()
            ):
                commands_data = category_data.get(
                    "commands",
                    {},
                )

                total = len(
                    commands_data
                )

                implemented = sum(
                    1
                    for spec in commands_data.values()
                    if spec.get(
                        "implemented",
                        False,
                    )
                )

                emoji = category_data.get(
                    "emoji",
                    "📂",
                )

                category_lines.append(
                    f"{emoji} **{category_name}** "
                    f"`{implemented}/{total}`"
                )

            embed.add_field(
                name=config["text"]["categoriesLabel"],
                value="\n".join(
                    category_lines
                )[:1024],
                inline=False,
            )

            footer = config["text"].get(
                "footer",
                "",
            )

            if footer:
                embed.set_footer(
                    text=footer
                )

            await ctx.send(
                embed=embed
            )

            return

        matched_category = None

        for category_name in config["categories"]:

            if category_name.casefold() == category.casefold():

                matched_category = category_name
                break

        if matched_category is None:

            await ctx.send(
                config["text"]["categoryNotFound"].format(
                    category=category
                )
            )

            return

        category_data = config["categories"][
            matched_category
        ]

        commands_data = category_data.get(
            "commands",
            {},
        )

        if not command_name:

            embed = discord.Embed(
                title=config["text"]["categoryTitle"].format(
                    category=matched_category
                ),
                colour=discord.Colour(
                    botmod._ui_color(
                        "colors.accent"
                    )
                ),
            )

            lines = []

            for name, spec in commands_data.items():

                marker = (
                    config["text"]["implemented"]
                    if spec.get(
                        "implemented",
                        False,
                    )
                    else config["text"]["planned"]
                )

                permission = spec.get(
                    "permission",
                    "public",
                )

                permission_text = (
                    " • Staff"
                    if permission == "staff"
                    else ""
                )

                lines.append(
                    f"{marker} "
                    f"`{botmod.bot_prefix}{name}`"
                    f"{permission_text}"
                    f" — "
                    f"{spec.get('description', '')}"
                )

            embed.description = (
                "\n".join(lines)
                if lines
                else config["text"]["noCommands"]
            )

            footer = config["text"].get(
                "footer",
                "",
            )

            if footer:
                embed.set_footer(
                    text=footer
                )

            await ctx.send(
                embed=embed
            )

            return

        matched_command = None

        for command_key in commands_data:

            if command_key.casefold() == command_name.casefold():

                matched_command = command_key
                break

        if matched_command is None:

            await ctx.send(
                config["text"]["commandNotFound"].format(
                    command=command_name,
                    category=matched_category,
                )
            )

            return

        spec = commands_data[
            matched_command
        ]

        implemented = spec.get(
            "implemented",
            False,
        )

        permission = spec.get(
            "permission",
            "public",
        )

        embed = discord.Embed(
            title=(
                f"{category_data.get('emoji', '📂')} "
                f"{botmod.bot_prefix}{matched_command}"
            ),
            colour=discord.Colour(
                botmod._ui_color(
                    "colors.accent"
                )
            ),
        )

        embed.add_field(
            name=config["text"]["description"],
            value=spec.get(
                "description",
                "",
            ) or "—",
            inline=False,
        )

        embed.add_field(
            name=config["text"]["status"],
            value=(
                config["text"]["implemented"]
                if implemented
                else config["text"]["planned"]
            ),
            inline=True,
        )

        if permission == "staff":
            embed.add_field(
                name="Permission",
                value="`STAFF`",
                inline=True,
            )

        if spec.get(
            "usage"
        ):
            embed.add_field(
                name=config["text"]["usage"],
                value=(
                    "```text\n"
                    + str(
                        spec["usage"]
                    )
                    + "\n```"
                ),
                inline=False,
            )

        footer = config["text"].get(
            "footer",
            "",
        )

        if footer:
            embed.set_footer(
                text=footer
            )

        await ctx.send(
            embed=embed
        )

    async def status_command(ctx):
        playlist = botmod.stats.get(
            "playlist",
            {},
        )

        current = str(
            playlist.get(
                "current",
                "",
            )
        )

        next_game = str(
            playlist.get(
                "next",
                "",
            )
        )

        roster = []

        try:
            roster = botmod._roster()
        except AttributeError:

            for account_id, data in (
                botmod.stats.get(
                    "roster",
                    {},
                ).items()
            ):
                roster.append(
                    {
                        "account_id": account_id,
                        "name": data.get(
                            "name",
                            "<unknown>",
                        ),
                    }
                )

        def split_game(value):
            if " @ " in value:

                mode, game_map = value.split(
                    " @ ",
                    1,
                )

                return (
                    mode.strip(),
                    game_map.strip(),
                )

            return (
                value,
                "",
            )

        current_mode, current_map = (
            split_game(
                current
            )
        )

        next_mode, next_map = (
            split_game(
                next_game
            )
        )

        embed = discord.Embed(
            title=config["text"].get(
                "statusTitle",
                "⚔️ CYPHER DUELS • STATUS",
            ),
            colour=discord.Colour(
                botmod._ui_color(
                    "colors.accent"
                )
            ),
        )

        embed.add_field(
            name="🟢 Status",
            value="`ONLINE`",
            inline=True,
        )

        embed.add_field(
            name="👥 Players",
            value=(
                f"`{len(roster)} / "
                f"{botmod.max_players}`"
            ),
            inline=True,
        )

        embed.add_field(
            name="🎮 Game",
            value=(
                "`"
                + (
                    current_mode
                    or "Waiting"
                )
                + "`"
            ),
            inline=True,
        )

        embed.add_field(
            name="🗺️ Map",
            value=(
                "`"
                + (
                    current_map
                    or current_mode
                    or "Waiting"
                )
                + "`"
            ),
            inline=True,
        )

        embed.add_field(
            name="⏭️ Next",
            value=(
                "`"
                + (
                    next_map
                    or next_mode
                    or "N/A"
                )
                + "`"
            ),
            inline=True,
        )

        host = str(
            botmod.server_connect.get(
                "host",
                "",
            )
        )

        port = str(
            botmod.server_connect.get(
                "port",
                "",
            )
        )

        address = (
            f"{host}:{port}"
            if host and port
            else host or port
        )

        embed.add_field(
            name="🔗 Server Address",
            value=(
                "```text\n"
                + address
                + "\n```"
            ),
            inline=False,
        )

        footer = config["text"].get(
            "footer",
            "",
        )

        if footer:
            embed.set_footer(
                text=footer
            )

        await ctx.send(
            embed=embed
        )

    async def players_command(ctx):
        try:
            players = botmod._roster()
        except AttributeError:

            players = []

            for account_id, data in (
                botmod.stats.get(
                    "roster",
                    {},
                ).items()
            ):
                players.append(
                    {
                        "name": data.get(
                            "name",
                            "<unknown>",
                        )
                    }
                )

        if not players:
            await ctx.send(
                "```text\n"
                "No players connected.\n"
                "```"
            )
            return

        lines = []

        for index, player in enumerate(
            players,
            start=1,
        ):

            name = str(
                player.get(
                    "name",
                    "<unknown>",
                )
            ).replace(
                "`",
                "'",
            )

            lines.append(
                f"{index}. {name}"
            )

        await ctx.send(
            "```text\n"
            + "\n".join(lines)
            + "\n```"
        )

    async def join_command(ctx):
        host = str(
            botmod.server_connect.get(
                "host",
                "",
            )
        )

        port = str(
            botmod.server_connect.get(
                "port",
                "",
            )
        )

        address = (
            f"{host}:{port}"
            if host and port
            else host or port
        )

        await ctx.send(
            "🔗 **QUICK JOIN**\n"
            "```text\n"
            + address
            + "\n```"
        )

    async def panel_command(ctx):

        if not _is_staff(
            botmod,
            ctx.author,
            ctx.guild,
        ):

            await ctx.send(
                config["text"]["staffOnly"]
            )

            return

        embed = discord.Embed(
            title="🛠️ CYPHER DUELS • STAFF PANEL",
            description=(
                "Use the controls below."
            ),
            colour=discord.Colour(
                botmod._ui_color(
                    "colors.accent"
                )
            ),
        )

        # The existing live status view already contains the
        # tested refresh/restart controls.
        view = botmod.LiveStatusView()

        await ctx.send(
            embed=embed,
            view=view,
        )

    async def dispatch_panel(
        ctx,
        *args,
    ):
        await panel_command(
            ctx
        )

    # ---------------------------------------------------------
    # Only canonical commands are registered.
    # No aliases which duplicate another command.
    # ---------------------------------------------------------

    client.add_command(
        commands.Command(
            help_command,
            name="help",
            help=config["categories"]["Help"]["commands"]["help"]["description"],
        )
    )

    client.add_command(
        commands.Command(
            status_command,
            name="status",
            help=config["categories"]["Status"]["commands"]["status"]["description"],
        )
    )

    client.add_command(
        commands.Command(
            players_command,
            name="players",
            help=config["categories"]["General"]["commands"]["players"]["description"],
        )
    )

    client.add_command(
        commands.Command(
            join_command,
            name="join",
            help=config["categories"]["Server Management BS"]["commands"]["join"]["description"],
        )
    )

    client.add_command(
        commands.Command(
            dispatch_panel,
            name="panel",
            help=config["categories"]["Staff"]["commands"]["panel"]["description"],
        )
    )

    botmod._command_system_registered = True

    print(
        "Discord command system: canonical commands registered"
    )


def _is_staff(
    botmod,
    user,
    guild,
):
    try:
        user_id = int(
            user.id
        )
    except BaseException:
        return False

    if user_id in getattr(
        botmod,
        "allowed_user_ids",
        set(),
    ):
        return True

    if guild is not None:

        try:
            return user_id == int(
                guild.owner_id
            )
        except BaseException:
            pass

    return False
