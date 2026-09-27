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
