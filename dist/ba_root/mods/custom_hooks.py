"""Custom hooks to pull of the in-game functions."""

# ba_meta require api 9
# (see https://ballistica.net/wiki/meta-tag-system)

# pylint: disable=import-error
# pylint: disable=import-outside-toplevel
# pylint: disable=protected-access

from __future__ import annotations

import _thread
import importlib
import logging
import os
import time
from datetime import datetime

import _babase
from typing import TYPE_CHECKING

import babase
import bascenev1 as bs
import _bascenev1
from baclassic._appmode import ClassicAppMode
import bauiv1 as bui
import setting
from baclassic._servermode import ServerController
from bascenev1._activitytypes import ScoreScreenActivity
from bascenev1._map import Map
from bascenev1._session import Session
from bascenev1lib.activity import dualteamscore, multiteamscore, drawscore
from bascenev1lib.activity.coopscore import CoopScoreScreen
from bascenev1lib.actor import playerspaz
from chathandle import handlechat
from features import map_fun
from features import team_balancer, afk_check, dual_team_score as newdts
from features import text_on_map, announcement
from features import votingmachine
from playersdata import pdata
from serverdata import serverdata
from spazmod import modifyspaz
from stats import mystats
from features import discord_ban_commands
from tools import account
from tools import notification_manager
from tools import servercheck, server_update, logger, playlist, servercontroller

if TYPE_CHECKING:
    from typing import Any

settings = setting.get_settings_data()


_cypher_original_check_ban_v2 = getattr(
    servercheck,
    "check_ban",
    None,
)


def _cypher_check_ban_v2(
    ip,
    device_id,
    pbid,
):
    if discord_ban_commands.is_identity_banned(
        ip,
        device_id,
        pbid,
    ):
        return True

    if _cypher_original_check_ban_v2 is not None:
        return bool(
            _cypher_original_check_ban_v2(
                ip,
                device_id,
                pbid,
            )
        )

    return False


if _cypher_original_check_ban_v2 is not None:
    servercheck.check_ban = (
        _cypher_check_ban_v2
    )


def filter_chat_message(
    msg: str,
    client_id: int,
) -> str | None:
    """Block muted clients before normal chat processing."""

    try:
        from features import mute_system

        (
            muted,
            name,
            expires_at,
            reason,
        ) = mute_system.get_client_mute_state(
            client_id
        )

        if muted:
            try:
                mute_system.notify_muted(
                    client_id,
                    name,
                    expires_at,
                    reason,
                )
            except Exception:
                logging.exception(
                    "Failed to notify muted client."
                )

            return None

    except Exception:
        # Never break the entire chat system if the mute subsystem
        # encounters an unexpected problem.
        logging.exception(
            "Mute chat check failed."
        )

    return handlechat.filter_chat_message(
        msg,
        client_id,
    )



# ba_meta export babase.Plugin
class modSetup(babase.Plugin):
    def on_app_running(self):
        """Runs when app is launched."""
        plus = bui.app.plus
        bootstraping()
        servercheck.checkserver().start()
        server_update.check()
        # bs.apptimer(5, account.updateOwnerIps)
        if settings["afk_remover"]['enable']:
            afk_check.checkIdle().start()
        if (settings["useV2Account"]):

            if (plus.get_v1_account_state() ==
                    'signed_in' and plus.get_v1_account_type() == 'V2'):
                logging.debug("Account V2 is active")
            else:
                logging.warning("Account V2 login require ....stay tuned.")
                bs.apptimer(3, babase.Call(logging.debug,
                                           "Starting Account V2 login process...."))
                bs.apptimer(6, account.AccountUtil)
        else:
            plus.accounts.set_primary_credentials(None)
            plus.sign_in_v1('Local')
        bs.apptimer(60, playlist.flush_playlists)

    # it works sometimes , but it blocks shutdown so server raise runtime
    # exception,   also dump server logs
    def on_app_shutdown(self):
        print("Server shutting down , lets save cache")
        # lets try  threading here
        # _thread.start_new_thread(pdata.dump_cache, ())
        # _thread.start_new_thread(notification_manager.dump_cache, ())
        # print("Done dumping memory")


def score_screen_on_begin(func) -> None:
    """Runs when score screen is displayed."""

    def wrapper(self, *args, **kwargs):
        result = func(self, *args, **kwargs)  # execute the original method
        team_balancer.balanceTeams()
        mystats.update(self._stats)
        announcement.showScoreScreenAnnouncement()
        return result

    return wrapper


ScoreScreenActivity.on_begin = score_screen_on_begin(
    ScoreScreenActivity.on_begin)


def on_map_init(func):
    def wrapper(self, *args, **kwargs):
        func(self, *args, **kwargs)
        text_on_map.textonmap()
        modifyspaz.setTeamCharacter()

    return wrapper


Map.__init__ = on_map_init(Map.__init__)


def playerspaz_init(playerspaz: bs.Player, node: bs.Node, player: bs.Player):
    """Runs when player is spawned on map."""
    modifyspaz.main(playerspaz, node, player)


def bootstraping():
    """Bootstarps the server."""
    logging.warning("Bootstraping mods...")
    # server related

    # check for auto update stats
    _thread.start_new_thread(mystats.refreshStats, ())
    pdata.load_cache()
    _thread.start_new_thread(pdata.dump_cache, ())
    _thread.start_new_thread(notification_manager.dump_cache, ())

    # import plugins
    if settings["elPatronPowerups"]["enable"]:
        from plugins import elPatronPowerups
        elPatronPowerups.enable()
    if settings["mikirogQuickTurn"]["enable"]:
        from plugins import wavedash  # pylint: disable=unused-import
    if settings["colorful_explosions"]["enable"]:
        from plugins import color_explosion
        color_explosion.enable()
    if settings["ballistica_web"]["enable"]:
        from plugins import bcs_plugin
        bcs_plugin.enable(settings["ballistica_web"]["server_password"])
    if settings["character_chooser"]["enable"]:
        from plugins import character_chooser
        character_chooser.enable()
    if settings["custom_characters"]["enable"]:
        from plugins import importcustomcharacters
        importcustomcharacters.enable()
    if settings["StumbledScoreScreen"]:
        pass
        # from features import StumbledScoreScreen
    if settings["colorfullMap"]:
        from plugins import colorfulmaps2
    try:
        pass
        # from tools import healthcheck
        # healthcheck.main()
    except Exception as e:
        print(e)
        try:
            import subprocess
            # Install psutil package
            # Download get-pip.py
            curl_process = subprocess.Popen(
                ["curl", "-sS", "https://bootstrap.pypa.io/get-pip.py"],
                stdout=subprocess.PIPE)

            # Install pip using python3.10
            python_process = subprocess.Popen(
                ["python3.10"], stdin=curl_process.stdout)

            # Wait for the processes to finish
            curl_process.stdout.close()
            python_process.wait()

            subprocess.check_call(
                ["python3.10", "-m", "pip", "install", "psutil"])
            # restart after installation
            print("dependency installed , restarting server")
            _babase.quit()
            from tools import healthcheck
            healthcheck.main()
        except BaseException:
            logging.warning("please install psutil to enable system monitor.")

    # import features
    if settings["whitelist"]:
        pdata.load_white_list()

    import_discord_bot()
    import_games()
    import_dual_team_score()
    logger.log("Server started")


def import_discord_bot() -> None:
    """Imports the Discord bot from external configuration."""
    if not settings["discordbot"]["enable"]:
        return

    from features import discord_bot

    cfg = settings["discordbot"]

    token_file = os.path.expanduser(
        cfg["token_file"]
    )

    try:
        with open(
            token_file,
            "r",
            encoding="utf-8",
        ) as token_handle:
            discord_token = (
                token_handle.read().strip()
            )
    except OSError as exc:
        raise RuntimeError(
            "Discord token file could not be read."
        ) from exc

    if not discord_token:
        raise RuntimeError(
            "Discord token file is empty."
        )

    discord_bot.token = discord_token

    discord_bot.guildID = int(
        cfg["guildID"]
    )

    discord_bot.liveStatsChannelID = int(
        cfg["liveStatsChannelID"]
    )

    discord_bot.logsChannelID = int(
        cfg["logsChannelID"]
    )

    discord_bot.notifyChannelID = int(
        cfg["notifyChannelID"]
    )

    discord_bot.complaintChannelID = int(
        cfg["complaintChannelID"]
    )

    discord_bot.liveChat = bool(
        cfg["liveChat"]
    )

    discord_bot.bot_prefix = str(
        cfg["prefix"]
    )

    discord_bot.refresh_interval = max(
        float(
            cfg["refreshInterval"]
        ),
        1.0,
    )

    discord_bot.stats_refresh_interval = max(
        float(
            cfg["statsRefreshInterval"]
        ),
        1.0,
    )

    discord_bot.channel_history_limit = max(
        int(
            cfg["channelHistoryLimit"]
        ),
        1,
    )

    discord_bot.state_file = str(
        cfg["state_file"]
    )

    discord_bot.commandConfig = dict(
        cfg.get(
            "commandConfig",
            {},
        )
    )

    discord_bot.discord_messages = dict(
        cfg["messages"]
    )


    discord_bot.log_config = dict(
        cfg.get(
            "logs",
            {},
        )
    )

    discord_bot.logs_batch_interval = max(
        float(
            cfg.get(
                "logs",
                {},
            ).get(
                "batchInterval",
                3,
            )
        ),
        1.0,
    )

    discord_bot.ui_config = dict(
        cfg.get("ui", {})
    )

    discord_bot.server_connect = dict(
        cfg.get(
            "serverConnect",
            {},
        )
    )

    discord_bot.max_players = int(
        cfg.get(
            "maxPlayers",
            5,
        )
    )

    discord_bot.allowed_user_ids = {
        int(user_id)
        for user_id in cfg.get(
            "allowed_user_ids",
            [],
        )
    }

    from features import discord_commands
    discord_commands.register(discord_bot)
    from features import discord_data_commands
    discord_data_commands.register(discord_bot)
    discord_ban_commands.register(discord_bot.client)
    from features import discord_chatlog_commands
    discord_chatlog_commands.register(discord_bot.client)
    from features import discord_data_commands
    discord_data_commands.register(discord_bot)
    from features import discord_dkv_commands
    discord_dkv_commands.register(discord_bot.client)


    discord_bot.BsDataThread()
    discord_bot.init()





def import_games():
    """Imports the custom games from games directory."""
    import sys
    sys.path.append(_babase.env()['python_directory_user'] + os.sep + "games")
    games = os.listdir("ba_root/mods/games")
    for game in games:
        if game.endswith(".so"):
            importlib.import_module("games." + game.replace(".so", ""))

    maps = os.listdir("ba_root/mods/maps")
    for _map in maps:
        if _map.endswith(".py") or _map.endswith(".so"):
            importlib.import_module(
                "maps." + _map.replace(".so", "").replace(".py", ""))


def import_dual_team_score() -> None:
    """Imports the dual team score."""
    if settings["newResultBoard"]:
        dualteamscore.TeamVictoryScoreScreenActivity = newdts.TeamVictoryScoreScreenActivity
        multiteamscore.MultiTeamScoreScreenActivity.show_player_scores = newdts.show_player_scores
        drawscore.DrawScoreScreenActivity = newdts.DrawScoreScreenActivity


org_begin = bs._activity.Activity.on_begin


def new_begin(self):
    """Runs when game is began."""
    org_begin(self)
    night_mode()
    if settings["colorfullMap"]:
        map_fun.decorate_map()
    votingmachine.reset_votes()
    votingmachine.game_started_on = time.time()


bs._activity.Activity.on_begin = new_begin

org_end = bs._activity.Activity.end


def new_end(self, results: Any = None,
            delay: float = 0.0, force: bool = False):
    """Runs when game is ended."""
    activity = bs.get_foreground_host_activity()

    if isinstance(activity, CoopScoreScreen):
        team_balancer.checkToExitCoop()
    org_end(self, results, delay, force)


bs._activity.Activity.end = new_end

org_player_join = bs._activity.Activity.on_player_join


def on_player_join(self, player) -> None:
    """Runs when player joins the game."""
    team_balancer.on_player_join()
    org_player_join(self, player)


bs._activity.Activity.on_player_join = on_player_join


def night_mode() -> None:
    """Checks the time and enables night mode."""

    if settings['autoNightMode']['enable']:

        start = datetime.strptime(
            settings['autoNightMode']['startTime'], "%H:%M")
        end = datetime.strptime(settings['autoNightMode']['endTime'], "%H:%M")
        now = datetime.now()

        if now.time() > start.time() or now.time() < end.time():
            activity = bs.get_foreground_host_activity()

            activity.globalsnode.tint = (0.5, 0.7, 1.0)

            if settings['autoNightMode']['fireflies']:
                try:
                    activity.fireflies_generator(
                        20, settings['autoNightMode']["fireflies_random_color"])
                except:
                    pass


def kick_vote_started(started_by: str, started_to: str) -> None:
    """Logs the kick vote."""
    logger.log(f"{started_by} started kick vote for {started_to}.")


def on_kicked(account_id: str) -> None:
    """Runs when someone is kicked by kickvote."""
    logger.log(f"{account_id} kicked by kickvotes.")


def on_kick_vote_end():
    """Runs when kickvote is ended."""
    logger.log("Kick vote End")


def on_join_request(ip):
    servercheck.on_join_request(ip)


def shutdown(func) -> None:
    """Set the app to quit either now or at the next clean opportunity."""

    def wrapper(*args, **kwargs):
        # add screen text and tell players we are going to restart soon.
        bs.chatmessage(
            "Server will restart on next opportunity. (series end)")
        _babase.restart_scheduled = True
        bs.get_foreground_host_activity().restart_msg = bs.newnode('text',
                                                                   attrs={
                                                                       'text': "Server going to restart after this series.",
                                                                       'flatness': 1.0,
                                                                       'h_align': 'right',
                                                                       'v_attach': 'bottom',
                                                                       'h_attach': 'right',
                                                                       'scale': 0.5,
                                                                       'position': (
                                                                           -25,
                                                                           54),
                                                                       'color': (
                                                                           1,
                                                                           0.5,
                                                                           0.7)
                                                                   })
        func(*args, **kwargs)

    return wrapper


ServerController.shutdown = shutdown(ServerController.shutdown)


def _get_sessionplayer_account_id(sessionplayer) -> str | None:
    """Return the API 9 session player's PB-ID."""
    for method_name in (
        "get_v1_account_id",
        "get_account_id",
    ):
        method = getattr(sessionplayer, method_name, None)

        if callable(method):
            try:
                account_id = method()
            except Exception:
                continue

            if account_id:
                return str(account_id)

    return None


def _is_banned_account(account_id: str | None) -> bool:
    """Return whether the current player has an active ban."""
    if not account_id:
        return False

    # Prefer the profile's current isBan state. This avoids relying only
    # on a potentially stale blacklist entry.
    try:
        profile = pdata.get_info(account_id)

        if isinstance(profile, dict) and "isBan" in profile:
            return bool(profile.get("isBan"))
    except Exception:
        pass

    # Fallback to the persistent blacklist.
    try:
        blacklist = pdata.get_blacklist()

        if not isinstance(blacklist, dict):
            return False

        ban_data = blacklist.get("ban", {})

        if not isinstance(ban_data, dict):
            return False

        ids = ban_data.get("ids", [])

        if isinstance(ids, dict):
            return account_id in ids

        if isinstance(ids, (list, tuple, set)):
            return account_id in ids
    except Exception:
        pass

    return False


def _disconnect_banned_sessionplayer(sessionplayer) -> None:
    """Disconnect a banned client immediately."""
    try:
        client_id = sessionplayer.inputdevice.client_id
    except Exception:
        return

    if isinstance(client_id, int) and client_id >= 0:
        try:
            _bascenev1.disconnect_client(client_id)
        except Exception:
            logging.exception(
                "Unable to disconnect banned client %s.",
                client_id,
            )



def on_player_request(func) -> bool:
    def wrapper(*args, **kwargs):
        player = args[1]

        # Get PBID.
        getter = getattr(
            player,
            "get_account_id",
            None,
        )

        if callable(getter):
            try:
                pbid = getter()
            except Exception:
                pbid = None
        else:
            pbid = None

        if pbid is None:
            getter = getattr(
                player,
                "get_v1_account_id",
                None,
            )

            if callable(getter):
                try:
                    pbid = getter()
                except Exception:
                    pbid = None

        # Enforce only from the authoritative V2 identity store.
        try:
            import _bascenev1

            client_id = (
                player.inputdevice.client_id
            )

            ip = _bascenev1.get_client_ip(
                client_id
            )

            device_id = (
                _bascenev1.get_client_public_device_uuid(
                    client_id
                )
            )

            if device_id is None:
                device_id = (
                    _bascenev1.get_client_device_uuid(
                        client_id
                    )
                )

            from features import discord_ban_commands

            if discord_ban_commands.is_identity_banned(
                ip,
                device_id,
                pbid,
            ):
                try:
                    _bascenev1.disconnect_client(
                        client_id
                    )
                except Exception:
                    pass

                return False

        except Exception:
            logging.exception(
                "V2 ban check in on_player_request failed."
            )

        # The server-side verification runs asynchronously after join.
        # Do not block Session.on_player_request on the initial verified=False state.
        if not pbid or pbid not in serverdata.clients:
            return False

        count = 0

        for current_player in args[0].sessionplayers:
            try:
                current_pbid = (
                    current_player.get_v1_account_id()
                )
            except Exception:
                current_pbid = None

            if current_pbid == pbid:
                count += 1

        if count >= settings["maxPlayersPerDevice"]:
            try:
                _babase.screenmessage(
                    "Reached max players limit per device",
                    clients=[
                        player.inputdevice.client_id
                    ],
                    transient=True,
                )
            except Exception:
                pass

            return False

        return func(*args, **kwargs)

    return wrapper


Session.on_player_request = on_player_request(
    Session.on_player_request
)


def on_access_check_response(self, data):
    if data is not None:
        addr = data['address']
        port = data['port']
        if settings["ballistica_web"]["enable"]:
            bs.set_public_party_stats_url(
                f'https://bombsquad-community.web.app/server-manager/?host={addr}&port={port}')

    servercontroller._access_check_response(self, data)


ServerController._access_check_response = on_access_check_response


def wrap_player_spaz_init(original_class):
    """
    Modify the __init__ method of the player_spaz.
    """

    class WrappedClass(original_class):
        def __init__(self, *args, **kwargs):
            # Custom code before the original __init__

            # Modify args or kwargs as needed
            player = args[0] if args else kwargs.get('player')
            character = args[3] if len(
                args) > 3 else kwargs.get('character', 'Spaz')

            # Modify the character value
            modified_character = modifyspaz.getCharacter(player, character)
            if len(args) > 3:
                args = args[:3] + (modified_character,) + args[4:]
            else:
                kwargs['character'] = modified_character

            # Call the original __init__
            super().__init__(*args, **kwargs)
            playerspaz_init(self, self.node, self._player)

    # Return the modified class
    return WrappedClass


playerspaz.PlayerSpaz = wrap_player_spaz_init(playerspaz.PlayerSpaz)

original_classic_app_mode_activate = ClassicAppMode.on_activate


def new_classic_app_mode_activate(*args, **kwargs):
    # Call the original function
    result = original_classic_app_mode_activate(*args, **kwargs)

    # Perform additional actions after the original function call
    on_classic_app_mode_active()

    return result


ClassicAppMode.on_activate = new_classic_app_mode_activate


def on_classic_app_mode_active():
    _bascenev1.set_server_name(settings["HostName"])
    _bascenev1.set_transparent_kickvote(settings["ShowKickVoteStarterName"])
    _bascenev1.set_kickvote_msg_type(settings["KickVoteMsgType"])
    _bascenev1.hide_player_device_id(settings["Anti-IdRevealer"])


def bcs_verify_client_account_ip(account_id: str, ip: str, client_id: int) -> str | None:
    """Verify a client account ID and IP address.
    """
    if settings["mfa"]["enable"]:
        _thread.start_new_thread(servercheck.account_check,
                                 (account_id, ip, client_id))
