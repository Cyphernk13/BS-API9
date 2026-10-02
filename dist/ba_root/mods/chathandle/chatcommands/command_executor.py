# Released under the MIT License. See LICENSE for details.


from datetime import datetime

import _babase
import setting
from playersdata import pdata
from serverdata import serverdata
from tools import logger
from .commands import normal_commands , management, fun , cheats
import bascenev1 as bs
from .handlers import check_permissions, clientid_to_accountid
from .commands.handlers import send, send_usage, COMMAND_USAGE

settings = setting.get_settings_data()


def command_type(command):
    """
    Checks The Command Type

    Parameters:
        command : str

    Returns:
        any
    """
    if command in normal_commands.Commands or command in normal_commands.CommandAliases:
        return "Normal"

    if command in management.Commands or command in management.CommandAliases:
        return "Manage"

    if command in fun.Commands or command in fun.CommandAliases:
        return "Fun"

    if command in cheats.Commands or command in cheats.CommandAliases:
        return "Cheats"


def execute(msg, clientid):
    parts = msg.strip().lower().split()
    if not parts:
        return None

    command = parts[0].lstrip("/")
    arguments = parts[1:]
    accountid = clientid_to_accountid(clientid)

    # Public player-facing command information.
    if command == "help":
        normal_commands.ExcelCommand(command, arguments, clientid, accountid)
        return None

    if command in ("acl", "vcl"):
        roles = pdata.get_roles()
        role_name = "admin" if command == "acl" else "vip"
        role = roles.get(role_name)

        if role is None:
            send(f"{role_name.title()} command list unavailable.", clientid)
            return None

        commands = sorted(set(role.get("commands", [])))
        title = "Admin Command List" if command == "acl" else "VIP Command List"

        lines = [f"{title} ({len(commands)})"]
        for i in range(0, len(commands), 6):
            lines.append("  ".join(f"/{x}" for x in commands[i:i + 6]))

        send("\n".join(lines), clientid)
        return None

    ctype = command_type(command)

    if ctype is None:
        send(f"Unknown command: /{command}\nUse /help.", clientid)
        return None

    # Permission check before argument validation.
    if ctype != "Normal" and not check_permissions(accountid, command):
        send("Access denied.", clientid)
        return None

    usage = COMMAND_USAGE.get(command)
    required = {
        "speed": (1, 1),
        "tint": (3, 3),
        "maxplayers": (1, 1),
        "max": (1, 1),
        "createteam": (1, 1),
        "playlist": (1, 1),
        "kick": (1, 1),
        "ban": (1, 2),
        "unban": (1, 1),
        "info": (1, 1),
        "gp": (1, 1),
        "party": (1, 1),
        "kickvote": (2, 2),
        "addrole": (2, 2),
        "removerole": (2, 2),
        "getroles": (1, 1),
        "addcommand": (2, 2),
        "addcmd": (2, 2),
        "removecommand": (2, 2),
        "removecmd": (2, 2),
        "changetag": (2, 2),
        "customtag": (2, 2),
        "customeffect": (2, 2),
        "effect": (2, 2),
        "removetag": (1, 1),
        "removeeffect": (1, 1),
        "spectators": (1, 1),
        "lobbytime": (1, 1),
        "celeb": (1, 1),
        "celebrate": (1, 1),
        "inv": (1, 1),
        "invisible": (1, 1),
        "headless": (1, 1),
        "creepy": (1, 1),
        "creep": (1, 1),
    }

    if command in required:
        min_args, max_args = required[command]
        if not (min_args <= len(arguments) <= max_args):
            send_usage(command, clientid)
            return None

    try:
        if ctype == "Normal":
            normal_commands.ExcelCommand(command, arguments, clientid, accountid)

        elif ctype == "Manage":
            management.ExcelCommand(command, arguments, clientid, accountid)

        elif ctype == "Fun":
            fun.ExcelCommand(command, arguments, clientid, accountid)

        elif ctype == "Cheats":
            cheats.ExcelCommand(command, arguments, clientid, accountid)

        send(f"OK: /{command}", clientid)

    except Exception as exc:
        logger.log(f"Chat command /{command} failed: {exc}")
        send(f"Command failed: /{command}", clientid)

    now = datetime.now()
    if accountid in pdata.get_blacklist()[
        "muted-ids"] and now < datetime.strptime(
        pdata.get_blacklist()["muted-ids"][accountid]["till"],
        "%Y-%m-%d %H:%M:%S"):
        send("You are on mute.", clientid)
        return None

    if serverdata.muted:
        return None

    if settings["ChatCommands"]["BrodcastCommand"]:
        return msg

    return None

def QuickAccess(msg, client_id):
    from bascenev1lib.actor import popuptext
    if msg.startswith(","):
        name = ""
        teamid = 0
        for i in bs.get_foreground_host_session().sessionplayers:
            if i.inputdevice.client_id == client_id:
                teamid = i.sessionteam.id
                name = i.getname(True)

        for i in bs.get_foreground_host_session().sessionplayers:
            if hasattr(i,
                       'sessionteam') and i.sessionteam and teamid == i.sessionteam.id and i.inputdevice.client_id != client_id:
                bs.broadcastmessage(name + ":" + msg[1:],
                                    clients=[i.inputdevice.client_id],
                                    color=(0.3, 0.6, 0.3), transient=True)

        return None
    elif msg.startswith("."):
        msg = msg[1:]
        msgAr = msg.split(" ")
        if len(msg) > 25 or int(len(msg) / 5) > len(msgAr):
            bs.broadcastmessage("msg/word length too long",
                                clients=[client_id], transient=True)
            return None
        msgAr.insert(int(len(msgAr) / 2), "\n")
        for player in _babase.get_foreground_host_activity().players:
            if player.sessionplayer.inputdevice.client_id == client_id and player.actor.exists() and hasattr(
                player.actor.node, "position"):
                pos = player.actor.node.position
                with bs.get_foreground_host_activity().context:
                    popuptext.PopupText(
                        " ".join(msgAr),
                        (pos[0], pos[1] + 1, pos[2])).autoretain()
                return None
        return None
