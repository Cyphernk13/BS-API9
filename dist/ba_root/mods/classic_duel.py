# To learn more, see https://ballistica.net/wiki/meta-tag-system
# ba_meta require api 9

from __future__ import annotations

from typing import Any, Sequence

import babase
import bascenev1 as bs
from bascenev1lib.actor.playerspaz import PlayerSpaz
from bascenev1lib.actor.scoreboard import Scoreboard
from bascenev1lib.game.elimination import Icon


# Classic Duel uses a 10-point match.  The normal FFA session assigns
# placement-based series points (for example, 6 points for first place in
# a standard 2-player FFA).  This dedicated server should award exactly 10
# series points to the match winner, so four match wins reach a 40-point
# series.  The server hosts only this game, so changing the FFA session's
# point-award hook here is intentional.
def _cypher_duel_ffa_point_awards(
    session: bs.FreeForAllSession,
) -> dict[int, int]:
    del session
    return {}


bs.FreeForAllSession.get_ffa_point_awards = _cypher_duel_ffa_point_awards


class ModLang:
    lang = babase.app.lang.language

    if lang == 'Spanish':
        name = 'Duelo Clásico'
        enable_powerups = 'Habilitar Potenciadores'
        boxing_gloves = 'Guantes de Boxeo'
    elif lang == 'Chinese':
        name = '经典决斗'
        enable_powerups = '启用助推器'
        boxing_gloves = '拳击手套'
    else:
        name = 'Classic Duel'
        enable_powerups = 'Enable Powerups'
        boxing_gloves = 'Boxing Gloves'


class Player(bs.Player['Team']):
    """Player type for Classic Duel."""

    def __init__(self) -> None:
        self.icons: list[Icon] = []
        self.in_game = False
        self.playervs1 = False
        self.playervs2 = False
        self.duel_slot: int | None = None
        self.ping_text: bs.Node | None = None
        self.ping_position: bs.Node | None = None
        self.round_kills = 0


class Team(bs.Team[Player]):
    """FFA team type; each player has their own score."""

    def __init__(self) -> None:
        self.score = 0


# ba_meta export bascenev1.GameActivity
class DuelClassicGame(bs.TeamGameActivity[Player, Team]):
    """Classic winner-stays-on 1v1 duel."""

    name = ModLang.name
    description = 'Winner stays. First to 10 points wins.'

    WINNING_SCORE = 10
    MAX_ACTIVE_PLAYERS = 2

    announce_player_deaths = True

    # Round score is kept in the Session so an accidental disconnect/rejoin
    # during the current 10-point match does not reset the score.
    _ROUND_SCORE_STORE_KEY = babase.storagename('cypher_duel_round_scores')
    _ROUND_KILLS_STORE_KEY = babase.storagename(
        'cypher_duel_round_kills'
    )

    # Series score is backed by account-id as an extra safety net for players
    # who disconnect between map activities.  Connected players also retain
    # their normal SessionTeam score automatically.
    _SERIES_SCORE_STORE_KEY = babase.storagename('cypher_duel_series_scores')

    @classmethod
    def get_available_settings(
        cls, sessiontype: type[bs.Session]
    ) -> list[bs.Setting]:
        del sessiontype
        return [
            bs.IntChoiceSetting(
                'Time Limit',
                choices=[
                    ('None', 0),
                    ('1 Minute', 60),
                    ('2 Minutes', 120),
                    ('5 Minutes', 300),
                    ('10 Minutes', 600),
                    ('20 Minutes', 1200),
                ],
                default=0,
            ),
            bs.BoolSetting(ModLang.enable_powerups, default=True),
        ]

    @classmethod
    def supports_session_type(cls, sessiontype: type[bs.Session]) -> bool:
        return issubclass(sessiontype, bs.FreeForAllSession)

    @classmethod
    def get_supported_maps(
        cls, sessiontype: type[bs.Session]
    ) -> list[str]:
        del sessiontype
        return bs.app.classic.getmaps('melee')

    def __init__(self, settings: dict) -> None:
        super().__init__(settings)

        # Use the stock FFA scoreboard layout.
        self._scoreboard = Scoreboard()
        self._vs_text: bs.Actor | None = None
        self._time_limit = float(settings['Time Limit'])
        self._enable_powerups = bool(
            settings.get(ModLang.enable_powerups, True)
        )

        # Dedicated-server Duel rules: always epic/slow and always boxing gloves.
        self._boxing_gloves = True
        self._epic_mode = True

        self._queue: list[Player] = []
        self._active_players: list[Player] = []
        self._initial_duel_complete = False
        self._series_points_awarded = False

        self.slow_motion = True
        self.default_music = bs.MusicType.EPIC

        # Refresh ping labels using app-time so the display interval is not
        # itself slowed down by Epic Mode.
        self._ping_timer: bs.AppTimer | None = None

    def get_instance_description(self) -> str | Sequence:
        return 'First to ${ARG1} points wins.', self.WINNING_SCORE

    def get_instance_description_short(self) -> str | Sequence:
        return 'first to ${ARG1} points', self.WINNING_SCORE

    # Disable Ballistica's repetitive game-start info displays.
    # This removes the top-left "Classic Duel / first to 10 points"
    # message and the larger center-screen start announcement.
    def _show_scoreboard_info(self) -> None:
        # Keep BombSquad's normal small top-left game information.
        super()._show_scoreboard_info()

    def _show_info(self) -> None:
        # Disable only the large center-screen round-start announcement.
        pass

    def on_begin(self) -> None:
        super().on_begin()

        # A new Activity means a new 10-point match, so round scores reset.
        # The Session itself remains alive across maps, preserving the series.
        self.session.customdata[self._ROUND_SCORE_STORE_KEY] = {}
        self.session.customdata[self._ROUND_KILLS_STORE_KEY] = {}
        self._series_points_awarded = False
        series_scores = self.session.customdata.setdefault(
            self._SERIES_SCORE_STORE_KEY, {}
        )
        if not isinstance(series_scores, dict):
            self.session.customdata[self._SERIES_SCORE_STORE_KEY] = {}
            series_scores = self.session.customdata[
                self._SERIES_SCORE_STORE_KEY
            ]

        # On the first game of a new series, clear the safety-net store.
        # get_game_number() restarts at 0 when a new FFA series begins.
        if self.session.get_game_number() == 0:
            series_scores.clear()

        # Synchronize currently connected SessionTeam series scores into the
        # account store before players are restored.
        for sessionteam in self.session.sessionteams:
            if len(sessionteam.players) != 1:
                continue
            sessionplayer = sessionteam.players[0]
            account_id = self._get_sessionplayer_account_id(sessionplayer)
            if account_id:
                series_scores[account_id] = int(
                    sessionteam.customdata.get('score', 0)
                )

        self.setup_standard_time_limit(self._time_limit)

        # Update pings independently of slow-motion timing.
        self._ping_timer = babase.AppTimer(
            0.2,
            babase.WeakCall(self._update_ping_labels),
            repeat=True,
        )

        if self._enable_powerups:
            self.setup_standard_powerup_drops()

        self._vs_text = bs.NodeActor(
            bs.newnode(
                'text',
                attrs={
                    'position': (0, 105),
                    'h_attach': 'center',
                    'h_align': 'center',
                    'maxwidth': 200,
                    'shadow': 0.5,
                    'vr_depth': 390,
                    'scale': 0.6,
                    'v_attach': 'bottom',
                    'color': (0.8, 0.8, 0.3, 1.0),
                    'text': bs.Lstr(resource='vsText'),
                },
            )
        )

        self._update_scoreboard()

        # Players existing when the game begins are already in self.players
        # and need to be queued/activated manually because we intentionally do
        # not call GameActivity.on_player_join().
        for player in self.players:
            self._restore_player_score(player)
            self._enqueue_player(player)

        self._start_next_duel()

    def on_player_join(self, player: Player) -> None:
        # The session-level max_players setting enforces the simultaneous
        # 5-player server limit; this queue handles which 2 are active.
        self._restore_player_score(player)
        self._enqueue_player(player)
        self._start_next_duel()
        self._update_scoreboard()
        self._update_icons()

    def on_player_leave(self, player: Player) -> None:
        # Save before the base class tears down the player/team association.
        self._save_player_score(player)
        self._delete_ping_label(player)

        if player in self._queue:
            self._queue.remove(player)

        if player in self._active_players:
            self._active_players.remove(player)

        player.in_game = False
        player.playervs1 = False
        player.playervs2 = False
        player.duel_slot = None
        player.icons = []
        super().on_player_leave(player)

        self._start_next_duel()
        self._update_icons()
        self._update_scoreboard()

    def on_team_join(self, team: Team) -> None:
        if self.has_begun():
            self._update_scoreboard()

    def spawn_player(self, player: Player) -> bs.Actor:
        position = self._get_spawn_point(player)
        spaz = self.spawn_player_spaz(player, position)

        if self._boxing_gloves:
            spaz.equip_boxing_gloves()

        self._create_ping_label(player)

        # Score text is intentionally NOT shown on spawn.
        # It is shown only by the kill event.
        return spaz

    def _delete_ping_label(self, player: Player) -> None:
        if player.ping_text is not None:
            try:
                player.ping_text.delete()
            except Exception:
                pass
            player.ping_text = None

        if player.ping_position is not None:
            try:
                player.ping_position.delete()
            except Exception:
                pass
            player.ping_position = None

    def _create_ping_label(self, player: Player) -> None:
        # Same attachment method as BS-Duels:
        # torso_position -> math node -> in-world text.
        self._delete_ping_label(player)

        spaz = player.actor

        if not isinstance(spaz, PlayerSpaz):
            return

        if not spaz.node:
            return

        mnode = bs.newnode(
            'math',
            owner=spaz.node,
            attrs={
                'input1': (0.0, -0.8, 0.0),
                'operation': 'add',
            },
        )

        spaz.node.connectattr(
            'torso_position',
            mnode,
            'input2',
        )

        player.ping_position = mnode

        player.ping_text = bs.newnode(
            'text',
            owner=spaz.node,
            attrs={
                'text': '...',
                'in_world': True,
                'shadow': 0.5,
                'flatness': 1.0,
                'color': (1.0, 1.0, 1.0),
                'scale': 0.009,
                'h_align': 'center',
                'v_align': 'center',
            },
        )

        mnode.connectattr(
            'output',
            player.ping_text,
            'position',
        )

    @staticmethod
    def _get_ping_color(
        ping_ms: float,
    ) -> tuple[float, float, float]:
        # Legacy BS-Duels ping colors.
        if ping_ms < 50:
            return (0.0, 1.0, 0.2)      # Cyan-green
        elif ping_ms < 100:
            return (0.2, 1.0, 0.0)      # Green
        elif ping_ms < 150:
            return (0.9, 1.0, 0.0)      # Yellow
        elif ping_ms < 200:
            return (1.0, 0.5, 0.0)      # Orange
        else:
            return (1.0, 0.1, 0.1)      # Red

    def _update_ping_labels(self) -> None:
        for player in list(self._active_players):
            spaz = player.actor

            if (
                not isinstance(spaz, PlayerSpaz)
                or not spaz.node
                or not spaz.is_alive()
            ):
                self._delete_ping_label(player)
                continue

            if player.ping_text is None:
                self._create_ping_label(player)

            text = player.ping_text
            if text is None:
                continue

            try:
                sessionplayer = player.sessionplayer
                if sessionplayer is None:
                    text.text = '--ms'
                    continue

                device = sessionplayer.inputdevice
                if device is None:
                    text.text = '--ms'
                    continue

                client_id = int(device.client_id)

                # Local devices do not have a network client id.
                if client_id < 0:
                    text.text = '--ms'
                    continue

                # API 9 public method.
                ping_func = getattr(bs, 'get_client_ping', None)

                # Fallback to the native API-9 module if needed.
                if ping_func is None:
                    try:
                        import _bascenev1
                        ping_func = getattr(
                            _bascenev1,
                            'get_client_ping',
                            None,
                        )
                    except Exception:
                        ping_func = None

                if ping_func is None:
                    raise RuntimeError(
                        'get_client_ping() is not available'
                    )

                ping_val = ping_func(client_id)

                if ping_val is None:
                    text.text = '--ms'
                    continue

                ping_value = float(ping_val)

                if ping_value < 0:
                    text.text = '--ms'
                else:
                    text.text = f'{int(round(ping_value))}ms'
                    text.color = self._get_ping_color(ping_value)

            except Exception as exc:
                text.text = '--ms'
                text.color = (1.0, 1.0, 1.0)

                # Print the real error so we can diagnose the engine/API
                # without breaking gameplay.
                print(
                    '[CYDUEL PING ERROR]',
                    type(exc).__name__,
                    str(exc),
                )

    def _get_spawn_point(self, player: Player) -> bs.Vec3 | None:
        # The first two players use the first two team-start positions so they
        # begin on opposite sides of the map.
        if not self._initial_duel_complete and player.duel_slot is not None:
            return bs.Vec3(self.map.get_start_position(player.duel_slot))

        # For every subsequent challenger, use Ballistica's FFA spawn helper.
        # It chooses a spawn area as far from the supplied living player(s) as
        # possible.
        living_players = [
            p for p in self._active_players
            if p is not player and p.is_alive()
        ]

        if living_players:
            return bs.Vec3(
                self.map.get_ffa_start_position(living_players)
            )

        return bs.Vec3(self.map.get_ffa_start_position([]))

    def _enqueue_player(self, player: Player) -> None:
        if player in self._active_players or player in self._queue:
            return
        self._queue.append(player)

    def _start_next_duel(self) -> None:
        # Only two players can be active at once.
        while len(self._active_players) < self.MAX_ACTIVE_PLAYERS:
            while self._queue and not self._queue[0].exists():
                self._queue.pop(0)

            if not self._queue:
                break

            player = self._queue.pop(0)
            if not player.exists():
                continue

            player.in_game = True
            player.duel_slot = len(self._active_players)

            if player.duel_slot == 0:
                player.playervs1 = True
            else:
                player.playervs2 = True

            self._active_players.append(player)
            self.spawn_player(player)

            if len(self._active_players) == self.MAX_ACTIVE_PLAYERS:
                self._initial_duel_complete = True

        self._update_icons()

    def _get_round_score_store(self) -> dict[str, int]:
        data = self.session.customdata.get(self._ROUND_SCORE_STORE_KEY)
        if not isinstance(data, dict):
            data = {}
            self.session.customdata[self._ROUND_SCORE_STORE_KEY] = data
        return data

    def _get_series_score_store(self) -> dict[str, int]:
        data = self.session.customdata.get(self._SERIES_SCORE_STORE_KEY)
        if not isinstance(data, dict):
            data = {}
            self.session.customdata[self._SERIES_SCORE_STORE_KEY] = data
        return data

    def _get_round_kills_store(self) -> dict[str, int]:
        data = self.session.customdata.get(self._ROUND_KILLS_STORE_KEY)
        if not isinstance(data, dict):
            data = {}
            self.session.customdata[self._ROUND_KILLS_STORE_KEY] = data
        return data

    def _get_sessionplayer_account_id(
        self, sessionplayer: bs.SessionPlayer
    ) -> str | None:
        # BS 1.7.61/API 9 on protocol 35 exposes get_v1_account_id().
        # Newer API 9 builds may expose get_account_id(); support both.
        getter = getattr(sessionplayer, 'get_account_id', None)
        if callable(getter):
            try:
                return getter()
            except Exception:
                pass

        getter = getattr(sessionplayer, 'get_v1_account_id', None)
        if callable(getter):
            try:
                return getter()
            except Exception:
                pass

        return None

    def _get_account_id(self, player: Player) -> str | None:
        try:
            return self._get_sessionplayer_account_id(player.sessionplayer)
        except Exception:
            return None

    def _save_player_score(self, player: Player) -> None:
        account_id = self._get_account_id(player)
        if account_id is None:
            return

        self._get_round_score_store()[account_id] = int(player.team.score)
        self._get_round_kills_store()[account_id] = int(
            getattr(player, 'round_kills', 0)
        )

        # Save the current FFA series score too when available.
        try:
            sessionteam = player.sessionplayer.sessionteam
        except Exception:
            sessionteam = None

        if sessionteam is not None:
            self._get_series_score_store()[account_id] = int(
                sessionteam.customdata.get('score', 0)
            )

    def _restore_player_score(
        self, player: Player, retries: int = 5
    ) -> None:
        if not player.exists():
            return

        account_id = self._get_account_id(player)

        # Account verification can briefly lag behind the player joining.
        if account_id is None:
            if retries > 0:
                bs.timer(
                    1.0,
                    babase.Call(
                        self._restore_player_score, player, retries - 1
                    ),
                )
            return

        round_score = int(
            self._get_round_score_store().get(account_id, 0)
        )
        player.team.score = max(
            0, min(self.WINNING_SCORE, round_score)
        )
        player.round_kills = max(
            0,
            int(self._get_round_kills_store().get(account_id, 0)),
        )

        # Restore the series score for a player who has rejoined after a
        # disconnect.  For players who never left, the SessionTeam score is
        # already intact across activities.
        series_score = int(
            self._get_series_score_store().get(account_id, 0)
        )
        try:
            sessionteam = player.sessionplayer.sessionteam
        except Exception:
            sessionteam = None

        if sessionteam is not None and series_score > int(
            sessionteam.customdata.get('score', 0)
        ):
            sessionteam.customdata['score'] = series_score
            sessionteam.customdata['previous_score'] = series_score

        if self.has_begun():
            self._update_scoreboard()

    def _update_scoreboard(self) -> None:
        for team in self.teams:
            self._scoreboard.set_team_value(
                team, team.score, self.WINNING_SCORE
            )


    def _clear_icons(self) -> None:
        for player in self.players:
            for icon in list(player.icons):
                try:
                    icon.handlemessage(bs.DieMessage())
                except Exception:
                    try:
                        if icon.node:
                            icon.node.delete()
                    except Exception:
                        pass
            player.icons = []

    def _update_icons(self) -> None:
        for player in self.players:
            player.icons = []

        # Active duelists.
        for player in self._active_players:
            if player.playervs1:
                xval = -60
            elif player.playervs2:
                xval = 60
            else:
                continue

            player.icons.append(
                Icon(
                    player,
                    position=(xval, 40),
                    scale=1.0,
                    name_maxwidth=130,
                    name_scale=0.8,
                    flatness=0.0,
                    shadow=0.5,
                    show_death=True,
                    show_lives=False,
                )
            )

        # Original BS-Duels queue.
        x_right = 125.0
        x_left = -125.0
        x_step = 78.0 * 0.56

        for player in self._queue[:5]:
            player.icons.append(
                Icon(
                    player,
                    position=(x_right, 25),
                    scale=0.5,
                    name_maxwidth=75,
                    name_scale=1.0,
                    flatness=1.0,
                    shadow=1.0,
                    show_death=False,
                    show_lives=False,
                )
            )

            player.icons.append(
                Icon(
                    player,
                    position=(x_left, 25),
                    scale=0.5,
                    name_maxwidth=75,
                    name_scale=1.0,
                    flatness=1.0,
                    shadow=1.0,
                    show_death=False,
                    show_lives=False,
                )
            )

            x_right += x_step
            x_left -= x_step

    def handlemessage(self, msg: Any) -> Any:
        if not isinstance(msg, bs.PlayerDiedMessage):
            return super().handlemessage(msg)

        # Keep standard death handling/stat processing.
        super().handlemessage(msg)

        player = msg.getplayer(Player)

        if player in self._active_players:
            self._active_players.remove(player)

        player.in_game = False
        player.playervs1 = False
        player.playervs2 = False
        player.duel_slot = None
        self._delete_ping_label(player)
        player.icons = []
        # The loser goes to the back of the queue.
        if player.exists():
            self._queue.append(player)

        killer = msg.getkillerplayer(Player)

        # Ballistica reports a suicide by using the dead player as the
        # killer-player. Suicides cost exactly one point, never below 0.
        if killer is player:
            player.team.score = max(0, int(player.team.score) - 1)
            self._save_player_score(player)
        elif killer is not None:
            # A genuine opponent kill awards one point.
            if killer in self.players and killer.team is not player.team:
                killer.team.score += 1
                killer.round_kills = int(
                    getattr(killer, 'round_kills', 0)
                ) + 1
                account_id = self._get_account_id(killer)
                if account_id:
                    self._get_round_kills_store()[account_id] = (
                        killer.round_kills
                    )
                self._save_player_score(killer)

                if isinstance(killer.actor, PlayerSpaz) and killer.actor:
                    killer.actor.set_score_text(
                        f'{killer.team.score}/{self.WINNING_SCORE}',
                        color=killer.team.color,
                        flash=True,
                    )

        self._update_scoreboard()

        if any(
            team.score >= self.WINNING_SCORE
            for team in self.teams
        ):
            bs.timer(0.5, self.end_game)
        else:
            bs.timer(0.1, self._start_next_duel)

        return None


    def end_game(self) -> None:
        if self.has_ended() or self._series_points_awarded:
            return

        self._series_points_awarded = True

        # Award 1 SERIES point per genuine opponent kill from this match.
        # Suicide penalties only affect the 10-point round score; they do not
        # erase a kill already earned.
        series_scores = self._get_series_score_store()
        round_kills = self._get_round_kills_store()

        for sessionteam in self.session.sessionteams:
            if len(sessionteam.players) != 1:
                continue

            sessionplayer = sessionteam.players[0]
            account_id = self._get_sessionplayer_account_id(sessionplayer)
            if not account_id:
                continue

            kills = max(0, int(round_kills.get(account_id, 0)))
            old_score = int(sessionteam.customdata.get('score', 0))
            new_score = old_score + kills

            sessionteam.customdata['previous_score'] = old_score
            sessionteam.customdata['score'] = new_score
            series_scores[account_id] = new_score

        results = bs.GameResults()
        for team in self.teams:
            results.set_team_score(team, team.score)

        self.end(results=results)
