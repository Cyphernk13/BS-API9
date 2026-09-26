from pathlib import Path
import json

CONFIG_PATH = Path('/home/ubuntu/BS-API9/config.json')
BACKUP_PATH = CONFIG_PATH.with_name('config.json.before-duel-v2')

with CONFIG_PATH.open('r', encoding='utf-8') as f:
    data = json.load(f)

if not BACKUP_PATH.exists():
    BACKUP_PATH.write_text(
        json.dumps(data, indent=4) + '\n', encoding='utf-8'
    )

# Dedicated public Classic Duel settings.
data['party_name'] = 'Cypher Classic Duels'
data['party_is_public'] = True
data['max_party_size'] = 5
data['session_max_players_override'] = 5

data['session_type'] = 'ffa'
data['playlist_code'] = None
data['playlist_inline'] = [
    {
        'type': 'classic_duel.DuelClassicGame',
        'settings': {
            'map': 'Doom Shroom',
            'Time Limit': 0,
            'Enable Powerups': True,
        },
    },
    {
        'type': 'classic_duel.DuelClassicGame',
        'settings': {
            'map': 'Bridgit',
            'Time Limit': 0,
            'Enable Powerups': True,
        },
    },
    {
        'type': 'classic_duel.DuelClassicGame',
        'settings': {
            'map': 'Courtyard',
            'Time Limit': 0,
            'Enable Powerups': True,
        },
    },
    {
        'type': 'classic_duel.DuelClassicGame',
        'settings': {
            'map': 'Rampage',
            'Time Limit': 0,
            'Enable Powerups': True,
        },
    },
    {
        'type': 'classic_duel.DuelClassicGame',
        'settings': {
            'map': 'Monkey Face',
            'Time Limit': 0,
            'Enable Powerups': True,
        },
    },
    {
        'type': 'classic_duel.DuelClassicGame',
        'settings': {
            'map': 'The Pad',
            'Time Limit': 0,
            'Enable Powerups': True,
        },
    },
    {
        'type': 'classic_duel.DuelClassicGame',
        'settings': {
            'map': 'Rampage',
            'Time Limit': 0,
            'Enable Powerups': False,
        },
    },
]

data['playlist_shuffle'] = True
data['auto_balance_teams'] = False
# Four 10-point wins = 40 series points.
data['ffa_series_length'] = 40
# Minimize intentional clean restarts; the server wrapper supports up to 360 min.
data['clean_exit_minutes'] = 360

with CONFIG_PATH.open('w', encoding='utf-8') as f:
    json.dump(data, f, indent=4)
    f.write('\n')

print(f'Updated {CONFIG_PATH}')
print(f'Backup: {BACKUP_PATH}')
print('party_name:', data['party_name'])
print('session_type:', data['session_type'])
print('max players:', data['session_max_players_override'])
print('playlist entries:', len(data['playlist_inline']))
print('playlist shuffle:', data['playlist_shuffle'])
print('series goal:', data['ffa_series_length'])
