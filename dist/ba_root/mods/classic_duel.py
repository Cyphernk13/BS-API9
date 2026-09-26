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
    return {0: 10}


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

        self.slow_motion = True
        self.default_music = bs.MusicType.EPIC

        # Refresh ping labels using app-time so the display interval is not
        # itself slowed down by Epic Mode.
        self._ping_timer: bs.AppTimer | None = None

    def get_instance_description(self) -> str | Sequence:
        return 'First to ${ARG1} points wins.', self.WINNING_SCORE

    def get_instance_description_short(self) -> str | Sequence:
        return 'first to ${ARG1} points', self.WINNING_SCORE

    def on_begin(self) -> None:
        super().on_begin()

        # A new Activity means a new 10-point match, so round scores reset.
        # The Session itself remains alive across maps, preserving the series.
        self.session.customdata[self._ROUND_SCORE_STORE_KEY] = {}
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

        self._ping_timer = bs.AppTimer(
            0.5,
            babase.Call(self._update_ping_labels),
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

        if player in self._queue:
            self._queue.remove(player)

        if player in self._active_players:
            self._active_players.remove(player)

        player.in_game = False
        player.playervs1 = False
        player.playervs2 = False
        player.duel_slot = None
        player.icons = []
        self._delete_ping_label(player)

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

        # Score text is intentionally NOT shown on spawn. It is shown only
        # by the kill event in handlemessage().
        self._create_ping_label(player)

        return spaz

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

            # Keep the stock layout but force the player name to white so a
            # dark profile color cannot make it unreadable.
            try:
                entry = self._scoreboard._entries[team.id]
                if entry._name_text.node:
                    entry._name_text.node.color = (1.0, 1.0, 1.0, 1.0)
            except (KeyError, AttributeError):
                pass

    def _update_icons(self) -> None:
        for player in self.players:
            player.icons = []

        # Active duelists stay in the traditional left/right positions.
        for player in self._active_players:
            xval = -60 if player.playervs1 else 60
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

        # Queue: exactly one icon per waiting player.  The old code created
        # two icons per player (left and right), which causes names to collide
        # badly with a 5-player queue.
        queue_positions = (-160, -80, 0, 80, 160)

        for index, player in enumerate(self._queue[:5]):
            player.icons.append(
                Icon(
                    player,
                    position=(queue_positions[index], 24),
                    scale=0.48,
                    name_maxwidth=70,
                    name_scale=0.72,
                    flatness=1.0,
                    shadow=1.0,
                    show_death=False,
                    show_lives=False,
                )
            )

    def _delete_ping_label(self, player: Player) -> None:
        node = player.ping_text
        player.ping_text = None
        if node is not None:
            try:
                node.delete()
            except Exception:
                pass

    def _create_ping_label(self, player: Player) -> None:
        self._delete_ping_label(player)

        try:
            client_id = player.sessionplayer.inputdevice.client_id
        except Exception:
            return

        if client_id < 0:
            return

        actor = player.actor
        if not isinstance(actor, PlayerSpaz) or not actor.node:
            return

        player.ping_text = bs.newnode(
            'text',
            attrs={
                'text': '-- ms',
                'position': actor.node.position,
                'h_attach': 'center',
                'h_align': 'center',
                'v_attach': 'center',
                'scale': 0.0075,
                'shadow': 1.0,
                'flatness': 1.0,
                'color': (1.0, 1.0, 1.0, 1.0),
                'vr_depth': 0.0,
            },
        )

    def _update_ping_labels(self) -> None:
        # Keep the label under each active player's feet and refresh the RTT.
        # get_client_ping() returns RTT in milliseconds; -1 means invalid id.
        for player in self._active_players:
            actor = player.actor
            if not isinstance(actor, PlayerSpaz) or not actor.node:
                self._delete_ping_label(player)
                continue

            if player.ping_text is None or not player.ping_text:
                self._create_ping_label(player)

            node = player.ping_text
            if node is None:
                continue

            try:
                client_id = player.sessionplayer.inputdevice.client_id
                ping = bs.get_client_ping(client_id)
                if ping < 0:
                    node.text = '-- ms'
                else:
                    node.text = f'{round(ping):d} ms'

                pos = actor.node.position
                node.position = (
                    pos[0],
                    pos[1] - 1.35,
                    pos[2],
                )
            except Exception:
                self._delete_ping_label(player)

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
        player.icons = []
        self._delete_ping_label(player)

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
        results = bs.GameResults()

        for team in self.teams:
            results.set_team_score(team, team.score)

        self.end(results=results)
