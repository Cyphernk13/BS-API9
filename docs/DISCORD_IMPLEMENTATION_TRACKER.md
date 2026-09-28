# Cypher Duels Discord Implementation Tracker

## Current Phase

**Discord Command Completion — Phase 2C**

Status: **IN PROGRESS**

### Foundation

- [x] Discord connection
- [x] Protected token file
- [x] Externalized deployment configuration
- [x] Configurable prefix
- [x] Persistent live dashboard
- [x] Rich dashboard controls
- [x] Compact event logs
- [x] Discord -> BombSquad chat bridge
- [x] Mobile-copyable values
- [x] Canonical command architecture
- [x] Category browser
- [x] Command detail browser
- [x] No redundant aliases

### Phase 2A

- [x] c!help
- [x] c!help <category>
- [x] c!help <category> <command>
- [x] c!status
- [x] c!players
- [x] c!join
- [x] c!panel

### Phase 2B — PlayerData

- [x] c!playerdata
- [x] c!findplayer
- [x] c!findplayerall
- [x] c!findip
- [x] c!findipall
- [x] c!finddevice
- [x] c!finddeviceall
- [x] c!compareplayer
- [x] c!gp
- [x] c!verifiedmembers

### Phase 2B — PlayerStats

- [x] c!pstats
- [x] c!top

### Phase 2B — Playtime

- [x] c!playtime
- [x] c!topplaytime

### Phase 2B validation

- [x] playerdata
- [x] findplayer
- [x] findplayerall
- [x] findip
- [x] findipall
- [x] finddevice
- [x] finddeviceall
- [x] compareplayer
- [x] gp
- [x] verifiedmembers
- [x] pstats
- [x] top
- [x] playtime
- [x] topplaytime
- [x] sensitive commands rejected for non-staff
- [x] no server-side errors
- [x] help category counts correct

## Upcoming

### Bans
- [x] ban
- [x] bancheck
- [x] banlist
- [x] unban
- [x] bandetails
- [x] banrelated

### Mutes
- [x] mute
- [x] mutecheck
- [x] mutelist
- [x] unmute
- [x] mutedetails

### DKV
- [ ] dkv
- [ ] dkvcheck
- [ ] dkvlist
- [ ] ekv

### Roles
- [ ] role
- [ ] roleadd
- [ ] roleremove
- [ ] rolecreate
- [ ] roledelete
- [ ] rolemembers
- [ ] rolehier
- [ ] rolecommands
- [ ] getroles
- [ ] cmdadd
- [ ] cmdremove
- [ ] cmdlist
- [ ] cmddesc

### Tags
- [ ] tag
- [ ] tagadd
- [ ] tagremove
- [ ] tagcheck
- [ ] tagusers

### Effects
- [ ] effect
- [ ] effectadd
- [ ] effectremove
- [ ] effectscheck
- [ ] effectsused

### Powerups
- [ ] powerup

### MaxDevice
- [ ] changemaxdevice
- [ ] getmaxdevice
- [ ] maxdevicelist
- [ ] resetmaxdevice
- [ ] setmaxdevice

### Server Ops
- [ ] disconnectplayer
- [ ] getplaylistcode
- [ ] kickplayer
- [ ] maxplayer
- [ ] maxplayeroverride
- [ ] playlist
- [ ] quit
- [ ] rejoincooldown
- [ ] removeplayer
- [ ] servername
- [ ] setmaxplayer
- [ ] setplaylistcode
- [ ] setrejoincooldown
- [ ] setservername
- [ ] endgame

### Server Management
- [ ] info
- [ ] announcements
- [ ] compdata
- [ ] insertmessage
- [ ] recents
- [ ] whitelist
- [ ] whitelistcheck
- [ ] whitelists
- [ ] unwhitelist

### ChatLogs
- [x] alm — browse ALL chat logs with pagination
- [x] hlm — browse ALL host messages with pagination
- [x] lm — show latest player messages
- [x] plm — show messages from a specific PBID

### Mail
- [ ] mail
- [ ] mailclear
- [ ] mailget
- [ ] maillastget
- [ ] maillastlist
- [ ] maillist
- [ ] mailremove

### Season
- [ ] season
- [ ] setseasoninterval
- [ ] startnewseason

### Discord Management
- [ ] reloadcogmodule
- [ ] useradd
- [ ] userlist
- [ ] userremove

### Additional
- [ ] Discord <-> PBID linking
- [ ] Join notifications
- [ ] Leave notifications
- [ ] Complaint workflow
- [ ] Advanced staff permissions
- [ ] Duel management controls

## Known investigation items

- servercontroller.py inventory parser reported a syntax error; running server currently loads servercontroller functionality, so source/runtime discrepancy needs investigation before Server Ops implementation.
- features/complaints.py is not present in the current API9 checkout; complaint implementation will be based on the actual complaint subsystem available in this build.

## Production rules

- Deployment values belong in configuration.
- User-facing strings belong in configuration.
- Secrets stay outside tracked files.
- One capability = one canonical command.
- API9 operations must use API9-native interfaces.
- Discord asyncio code must not directly manipulate Ballistica state.
- Sensitive player data is staff-only.
- Mutating operations require explicit authorization and confirmation.


## Phase 2C — Bans

### Ban System v2
- [x] Account → same-IP associated accounts
- [x] Account → same-device associated accounts
- [x] Persistent IP ban rules
- [x] Persistent device ban rules
- [x] Immediate disconnect of affected connected players
- [x] Ban case IDs
- [x] Issued/expiry timestamps
- [x] Issued-by audit data
- [x] Rich banlist
- [x] `c!banip`
- [x] `c!bandevice`
- [x] `c!unbanip`
- [x] `c!unbandevice`
- [x] `c!bandetails`
- [x] `c!banrelated`
- [ ] Validate propagation
- [ ] Validate future IP/device account blocking
- [ ] Validate expiry
- [ ] Validate unban behavior

- [x] Hard ban enforcement at session join
- [x] Immediate disconnect when banning a connected client
- [x] Fixed API9 ban join-handler chat call


- [x] `c!ban`
- [x] `c!unban`
- [x] `c!bancheck`
- [x] `c!banlist`
- [ ] Validate ban persistence
- [ ] Validate bancheck/list output
- [ ] Validate unban persistence
- [ ] Validate rejoin enforcement


## 2026-09-28 Progress Checkpoint

### Verified Complete

- Discord core commands: `c!help`, `c!status`, `c!players`, `c!join`, `c!panel`.
- Bans: `6/6`.
  - Ban V2 implemented.
  - Recursive identity closure across PBIDs, opaque `lastIP` identities and device UUIDs.
  - Persistent `ban_records.json`.
  - Live join enforcement.
  - Restart persistence.
  - `c!ban`, `c!unban`, `c!bancheck`, `c!banlist`, `c!bandetails`, `c!banrelated`.
  - API9 account-ID compatibility.
  - API9 kick-vote verification crash fixed.
  - Profile persistence handled explicitly because legacy `commit_profiles()` is a no-op.
- Mutes: `5/5`.
- Chat Logs: `4/4`.
- Help: `1/1`.
- Status: `1/1`.
- Staff: `1/1`.
- General: `2/2`.
- Existing Classic Duel work remains implemented:
  - winner-stays 1v1 flow
  - 5-player queue
  - persistent series scoring
  - first-to-10 match scoring
  - 40-point series target
  - suicide `-1`, floor at `0`
  - boxing gloves
  - epic/slow mode
  - daytime
  - stock scoreboard
  - player name colors
  - post-kill score display
  - live ping
- Discord live dashboard / live statistics infrastructure remains implemented.
- Discord ↔ BombSquad command bridge remains implemented.
- Ban V2 commit pushed: `7bc5ecd`.

### Parked / Not Complete

- DKV: `0/4`.
  - `c!dkv`, `c!dkvcheck`, `c!dkvlist`, `c!ekv` exist.
  - Persistent DKV records exist.
  - API9 native `disable_kickvote()` behavior is not enforcing the intended live restriction reliably.
  - Live enable/disable behavior remains unresolved.
  - Do not mark DKV complete until verified with real players.

### Current Issue

- Repeated account-less `BSM` connections are generating unwanted join notifications.
- The BSM client presents no PBID and changes its device UUID.
- Next security task: identify the BSM handshake signature/source IP and block it at the earliest network/request layer without affecting normal players.
