""" Some useful handlers to reduce lot of code """
import _babase

import bascenev1 as bs


def send(msg, clientid):
    """Send private server chat messages to one client."""
    for m in str(msg).split("\n"):
        bs.chatmessage(m, clients=[clientid])


def send_popup(msg, clientid, color=(1.0, 1.0, 1.0)):
    """Send a temporary private popup to one client."""
    bs.screenmessage(str(msg), color=color, clients=[clientid])



COMMAND_USAGE = {
    "help": "/help [command]",
    "acl": "/acl",
    "vcl": "/vcl",

    "ping": "/ping [all|client_id]",
    "list": "/list",
    "l": "/l",
    "uniqeid": "/uniqeid [player_id]",
    "id": "/id [player_id]",

    "fly": "/fly [all|player_id]",
    "inv": "/inv <player_id|all>",
    "invisible": "/invisible <player_id|all>",
    "headless": "/headless <player_id|all>",
    "creepy": "/creepy <player_id|all>",
    "creep": "/creep <player_id|all>",
    "celebrate": "/celebrate <player_id|all>",
    "celeb": "/celeb <player_id|all>",
    "speed": "/speed <value>",
    "floater": "/floater [client_id]",

    "kill": "/kill [player_id|all]",
    "heal": "/heal [player_id|all]",
    "curse": "/curse [player_id|all]",
    "sleep": "/sleep [player_id|all]",
    "superpunch": "/superpunch [player_id|all]",
    "sp": "/sp [player_id|all]",
    "gloves": "/gloves [player_id|all]",
    "shield": "/shield [player_id|all]",
    "freeze": "/freeze [player_id|all]",
    "unfreeze": "/unfreeze [player_id|all]",
    "thaw": "/thaw [player_id|all]",
    "godmode": "/godmode [player_id|all]",
    "gm": "/gm [player_id|all]",

    "recents": "/recents",
    "info": "/info <client_id>",
    "maxplayers": "/maxplayers <number>",
    "max": "/max <number>",
    "createteam": "/createteam <name>",
    "playlist": "/playlist <name|code>",
    "kick": "/kick <client_id>",
    "ban": "/ban <client_id> [days]",
    "unban": "/unban <client_id>",
    "end": "/end",
    "next": "/next",
    "kickvote": "/kickvote <enable|disable> <all|client_id>",
    "hideid": "/hideid",
    "showid": "/showid",
    "lm": "/lm",
    "gp": "/gp <player_id>",
    "party": "/party <public|private>",
    "quit": "/quit",
    "mute": "/mute [client_id] [days]",
    "unmute": "/unmute [client_id]",
    "remove": "/remove <client_id|all>",
    "rm": "/rm <client_id|all>",
    "sm": "/sm",
    "slow": "/slow",
    "slowmo": "/slowmo",
    "nv": "/nv",
    "tint": "/tint <r> <g> <b>",
    "pause": "/pause",
    "pausegame": "/pausegame",
    "cameramode": "/cameramode",
    "camera_mode": "/camera_mode",
    "rotate_camera": "/rotate_camera",

    "createrole": "/createrole <role>",
    "addrole": "/addrole <role> <client_id>",
    "removerole": "/removerole <role> <client_id>",
    "getroles": "/getroles <client_id>",
    "addcommand": "/addcommand <role> <command>",
    "addcmd": "/addcmd <role> <command>",
    "removecommand": "/removecommand <role> <command>",
    "removecmd": "/removecmd <role> <command>",
    "changetag": "/changetag <role> <tag>",
    "customtag": "/customtag <tag> <client_id>",
    "customeffect": "/customeffect <effect> <client_id>",
    "effect": "/effect <effect> <client_id>",
    "removetag": "/removetag <client_id>",
    "removeeffect": "/removeeffect <client_id>",
    "spectators": "/spectators <on|off>",
    "lobbytime": "/lobbytime <seconds>",
}


def send_usage(command, clientid):
    usage = COMMAND_USAGE.get(command)
    if usage:
        send(f"Usage: {usage}", clientid)
    else:
        send(f"Usage unavailable for /{command}", clientid)


def send_error(message, clientid):
    send(f"Error: {message}", clientid)

def clientid_to_myself(clientid):
    """Return Player Index Of Self Player"""

    for i, player in enumerate(_babase.get_foreground_host_activity().players):
        if player.sessionplayer.inputdevice.client_id == clientid:
            return i


def handlemsg(client, msg):
    """Handles Spaz Msg For Single Player"""
    activity = bs.get_foreground_host_activity()
    activity.players[client].actor.node.handlemessage(msg)


def handlemsg_all(msg):
    """Handle Spaz message for all players in activity"""

    activity = bs.get_foreground_host_activity()

    for i in activity.players:
        i.actor.node.handlemessage(msg)
