from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import discord
from discord.ext import commands


ROOT_MODS = Path(__file__).resolve().parents[1]
SETTING_PATH = ROOT_MODS / "setting.json"


def _load_config() -> dict[str, Any]:
    try:
        with SETTING_PATH.open("r", encoding="utf-8") as f:
            root = json.load(f)

        return (
            root
            .get("discordbot", {})
            .get("commandConfig", {})
            .get("chatLogSystem", {})
        )
    except Exception:
        return {}


CFG = _load_config()

PAGE_SIZE = max(
    1,
    int(CFG.get("page_size", 15)),
)

MAX_PLAYER_RESULTS = max(
    1,
    int(CFG.get("max_player_results", 5000)),
)

MESSAGES = CFG.get(
    "messages",
    {},
)


def _message(
    key: str,
    **values: Any,
) -> str:
    template = str(
        MESSAGES.get(
            key,
            key,
        )
    )
    return template.format(**values)


def _staff(ctx: commands.Context) -> bool:
    permissions = getattr(
        ctx.author,
        "guild_permissions",
        None,
    )

    if permissions is None:
        return False

    for name in CFG.get(
        "required_discord_permissions",
        ["administrator"],
    ):
        if bool(
            getattr(
                permissions,
                name,
                False,
            )
        ):
            return True

    return False


def _log_root() -> Path:
    try:
        import _babase

        python_user = Path(
            str(
                _babase.env()["python_directory_user"]
            )
        )

        return python_user / "serverdata"
    except Exception:
        return ROOT_MODS / "serverdata"


def _log_files() -> list[Path]:
    root = _log_root()

    if not root.exists():
        return []

    files = [
        p
        for p in root.glob("Chat Logs.log*")
        if p.is_file()
    ]

    # Oldest file first. This gives us deterministic ordering when
    # timestamps in different files overlap.
    files.sort(
        key=lambda p: (
            p.stat().st_mtime,
            p.name,
        )
    )

    return files


def _read_all_logs() -> list[str]:
    entries: list[tuple[str, int, int, str]] = []

    for file_index, path in enumerate(_log_files()):
        try:
            with path.open(
                "r",
                encoding="utf-8",
                errors="replace",
            ) as f:
                for line_index, line in enumerate(f):
                    line = line.rstrip("\r\n")

                    if not line.strip():
                        continue

                    # The first 19 chars are the log timestamp.
                    timestamp = line[:19]

                    entries.append(
                        (
                            timestamp,
                            file_index,
                            line_index,
                            line,
                        )
                    )
        except OSError:
            continue

    entries.sort(
        key=lambda item: (
            item[0],
            item[1],
            item[2],
        )
    )

    return [
        item[3]
        for item in entries
    ]


def _player_labels(lines: list[str]) -> set[str]:
    labels: set[str] = set()

    for line in lines:
        if "Host msg:" in line:
            continue

        try:
            payload = line.split(
                " + : ",
                1,
            )[1]
        except IndexError:
            continue

        parts = payload.split(
            " | ",
            3,
        )

        if len(parts) < 3:
            continue

        # Stored player-chat format:
        # PBID | display_string | current_name | message
        for value in (
            parts[1],
            parts[2],
        ):
            value = value.strip()

            if value:
                labels.add(value)

    return labels


def _is_host(
    line: str,
    player_labels: set[str] | None = None,
) -> bool:
    if "Host msg:" not in line:
        return False

    if player_labels is None:
        player_labels = _player_labels(
            _read_all_logs()
        )

    try:
        message = line.split(
            "Host msg: | ",
            1,
        )[1].strip()
    except IndexError:
        return True

    # /lm and similar commands replay player chat through the
    # host chat path, producing entries such as:
    # Host msg: | PlayerName: hello
    #
    # Do not classify those as genuine server/host messages.
    if ": " in message:
        prefix = message.split(
            ": ",
            1,
        )[0].strip()

        if prefix in player_labels:
            return False

    return True


def _extract_pbid(line: str) -> str | None:
    try:
        payload = line.split(
            " + : ",
            1,
        )[1]
    except IndexError:
        return None

    if payload.startswith("Host msg:"):
        return None

    parts = payload.split(
        " | ",
        3,
    )

    if not parts:
        return None

    pbid = parts[0].strip()

    if pbid.startswith("pb-"):
        return pbid

    return None


def _player_matches(
    line: str,
    pbid: str,
) -> bool:
    return _extract_pbid(line) == pbid


def _clean_line(line: str) -> str:
    # Prevent accidental code-block termination in Discord.
    return line.replace(
        "```",
        "'''",
    )


def _paginate(
    items: list[str],
    page: int,
) -> tuple[list[str], int]:
    total_pages = max(
        1,
        (len(items) + PAGE_SIZE - 1) // PAGE_SIZE,
    )

    page = max(
        1,
        min(page, total_pages),
    )

    start = (
        page - 1
    ) * PAGE_SIZE

    end = start + PAGE_SIZE

    return (
        items[start:end],
        total_pages,
    )


class LogJumpModal(
    discord.ui.Modal,
    title="Jump to Page",
):
    page_input = discord.ui.TextInput(
        label="Page number",
        placeholder="Enter a page number",
        required=True,
        min_length=1,
        max_length=8,
    )

    def __init__(
        self,
        view: "ChatLogView",
    ) -> None:
        super().__init__()
        self.view_ref = view

    async def on_submit(
        self,
        interaction: discord.Interaction,
    ) -> None:
        try:
            page = int(
                str(
                    self.page_input.value
                ).strip()
            )
        except ValueError:
            await interaction.response.send_message(
                _message("invalid_page"),
                ephemeral=True,
            )
            return

        page = max(
            1,
            page,
        )

        self.view_ref.page = page

        await self.view_ref.refresh(
            interaction,
        )


class ChatLogView(
    discord.ui.View,
):
    def __init__(
        self,
        ctx: commands.Context,
        mode: str,
        items: list[str],
        pbid: str | None = None,
    ) -> None:
        super().__init__(
            timeout=900,
        )

        self.ctx = ctx
        self.mode = mode
        self.items = items
        self.pbid = pbid
        self.page = max(
            1,
            (len(items) + PAGE_SIZE - 1) // PAGE_SIZE,
        )

        self._update_buttons()

    def _update_buttons(self) -> None:
        total_pages = max(
            1,
            (len(self.items) + PAGE_SIZE - 1) // PAGE_SIZE,
        )

        self.prev_button.disabled = (
            self.page <= 1
        )

        self.next_button.disabled = (
            self.page >= total_pages
        )

    def _title(
        self,
        total_pages: int,
    ) -> str:
        if self.mode == "host":
            base = _message(
                "host_title",
            )
        elif self.mode == "player":
            base = _message(
                "player_title",
                pbid=self.pbid or "unknown",
            )
        else:
            base = _message(
                "all_title",
            )

        return (
            f"{base}"
            f" | Page {self.page}/{total_pages}"
        )

    def _content(self) -> str:
        lines, total_pages = _paginate(
            self.items,
            self.page,
        )

        if not lines:
            body = _message(
                "empty",
            )
        else:
            body = "\n".join(
                _clean_line(line)
                for line in lines
            )

        return (
            f"**{self._title(total_pages)}**\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"{body}"
        )

    async def refresh(
        self,
        interaction: discord.Interaction,
    ) -> None:
        total_pages = max(
            1,
            (len(self.items) + PAGE_SIZE - 1)
            // PAGE_SIZE,
        )

        self.page = max(
            1,
            min(
                self.page,
                total_pages,
            ),
        )

        self._update_buttons()

        await interaction.response.edit_message(
            content=self._content(),
            view=self,
        )

    async def _replace(
        self,
        interaction: discord.Interaction,
    ) -> None:
        if self.mode == "host":
            all_logs = _read_all_logs()
            player_labels = _player_labels(
                all_logs
            )

            items = [
                line
                for line in all_logs
                if _is_host(
                    line,
                    player_labels,
                )
            ]
        elif self.mode == "player":
            items = [
                line
                for line in _read_all_logs()
                if self.pbid
                and _player_matches(
                    line,
                    self.pbid,
                )
            ]
        else:
            items = _read_all_logs()

        self.items = items

        await self.refresh(
            interaction,
        )

    @discord.ui.button(
        label="⬅️ Prev",
        style=discord.ButtonStyle.secondary,
    )
    async def prev_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        del button

        self.page -= 1

        await self.refresh(
            interaction,
        )

    @discord.ui.button(
        label="🔄",
        style=discord.ButtonStyle.primary,
    )
    async def refresh_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        del button

        await self._replace(
            interaction,
        )

    @discord.ui.button(
        label="➡️ Next",
        style=discord.ButtonStyle.secondary,
    )
    async def next_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        del button

        self.page += 1

        await self.refresh(
            interaction,
        )

    @discord.ui.button(
        label="📄 Jump to Page",
        style=discord.ButtonStyle.secondary,
        row=1,
    )
    async def jump_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        del button

        await interaction.response.send_modal(
            LogJumpModal(
                self,
            )
        )


async def _send_paginated(
    ctx: commands.Context,
    mode: str,
    items: list[str],
    pbid: str | None = None,
) -> None:
    view = ChatLogView(
        ctx,
        mode,
        items,
        pbid=pbid,
    )

    await ctx.send(
        view._content(),
        view=view,
    )


async def alm_command(
    ctx: commands.Context,
) -> None:
    if not _staff(ctx):
        await ctx.send(
            _message("no_permission")
        )
        return

    items = _read_all_logs()

    await _send_paginated(
        ctx,
        "all",
        items,
    )


async def hlm_command(
    ctx: commands.Context,
) -> None:
    if not _staff(ctx):
        await ctx.send(
            _message("no_permission")
        )
        return

    all_logs = _read_all_logs()
    player_labels = _player_labels(all_logs)

    items = [
        line
        for line in all_logs
        if _is_host(
            line,
            player_labels,
        )
    ]

    await _send_paginated(
        ctx,
        "host",
        items,
    )


async def lm_command(
    ctx: commands.Context,
    limit: str | None = None,
) -> None:
    if not _staff(ctx):
        await ctx.send(
            _message("no_permission")
        )
        return

    amount = PAGE_SIZE

    if limit is not None:
        try:
            amount = int(limit)
        except ValueError:
            await ctx.send(
                _message("invalid_limit")
            )
            return

    if amount < 1 or amount > 50:
        await ctx.send(
            _message("invalid_limit")
        )
        return

    items = _read_all_logs()

    items = items[
        -amount:
    ]

    if not items:
        await ctx.send(
            _message("empty")
        )
        return

    await ctx.send(
        f"**{_message('last_title', count=len(items))}**\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        + "\n".join(
            _clean_line(line)
            for line in items
        )
    )


_PBID_PATTERN = re.compile(
    r"^pb-[A-Za-z0-9+/=_-]+$"
)


async def plm_command(
    ctx: commands.Context,
    pbid: str | None = None,
) -> None:
    if not _staff(ctx):
        await ctx.send(
            _message("no_permission")
        )
        return

    if not pbid or not _PBID_PATTERN.fullmatch(
        pbid
    ):
        await ctx.send(
            _message("invalid_pbid")
        )
        return

    items = [
        line
        for line in _read_all_logs()
        if _player_matches(
            line,
            pbid,
        )
    ]

    items = items[
        -MAX_PLAYER_RESULTS:
    ]

    await _send_paginated(
        ctx,
        "player",
        items,
        pbid=pbid,
    )


def register(
    bot: commands.Bot,
) -> None:
    callbacks = {
        "alm": alm_command,
        "hlm": hlm_command,
        "lm": lm_command,
        "plm": plm_command,
    }

    for name, callback in callbacks.items():
        existing = bot.get_command(
            name
        )

        if existing is not None:
            bot.remove_command(
                existing.name
            )

        bot.add_command(
            commands.Command(
                callback,
                name=name,
                help=_help_text(name),
            )
        )

    # The main help command historically receives the category
    # as a single positional argument, so "ChatLogs" gets split
    # into "Chat" + "Logs". Replace it with a small wrapper that
    # resolves the longest configured category name first, then
    # delegates to the existing help implementation.
def _help_text(
    name: str,
) -> str:
    try:
        root = json.loads(
            SETTING_PATH.read_text(
                encoding="utf-8",
            )
        )

        return str(
            root
            .get("discordbot", {})
            .get("commandConfig", {})
            .get("categories", {})
            .get("ChatLogs", {})
            .get("commands", {})
            .get(name, {})
            .get("description", name)
        )
    except Exception:
        return name
