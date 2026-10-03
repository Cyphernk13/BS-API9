# Released under the MIT License. See LICENSE for details.

from playersdata import pdata

import bascenev1 as bs

# ---------------------------------------------------------------------------
# Role hierarchy.
#
# Previously every role's `commands` list in roles.json was its own island:
# an admin could only run what was literally written in the "admin" role's
# command list, even though admins should obviously also be able to do
# anything a vip can. This maps role *names* (as they appear in roles.json)
# to a tier, highest first. Any role name not listed here is simply not
# part of the hierarchy (things like "top5"/"pros"/"smoothy"/"bypass-warn"
# keep working exactly as before -- purely additive, per-role command
# grants, no inheritance).
#
# To add a differently-named staff role later (e.g. a literal "leadstaff"
# role), just add its name to the "staff" set below -- no other code needs
# to change.
ROLE_HIERARCHY = [
    # (tier key, rank [higher = more powerful], role names in roles.json,
    #  human label used in "you need X access" messages)
    ("owner", 4, {"owner"}, "Owner"),
    ("staff", 3, {
        "moderator", "trial-moderator",
        "complaint-staff", "trial-complaint-staff",
        "leadstaff", "lead-staff", "lead-staff", "leadstaffs",
    }, "Staff"),
    ("admin", 2, {"admin"}, "Admin"),
    ("vip", 1, {"vip"}, "VIP"),
]


def clientid_to_accountid(clientid):
    """
    Transform Clientid To Accountid

    Parameters:
        clientid : int

    Returns:
        None
    """
    for i in bs.get_game_roster():
        if i['client_id'] == clientid:
            return i['account_id']
    return None


def get_account_tier(accountid):
    """Returns (tier_key, rank, label) for the HIGHEST hierarchy tier this
    account belongs to, or (None, 0, "Member") if they're not in any
    hierarchy role. A player in multiple tiered roles (e.g. both "admin"
    and "vip") gets the highest one."""
    if not accountid:
        return (None, 0, "Member")

    roles = pdata.get_roles()
    best = (None, 0, "Member")
    for tier_key, rank, names, label in ROLE_HIERARCHY:
        for name in names:
            role = roles.get(name)
            if role and accountid in role.get("ids", []) and rank > best[1]:
                best = (tier_key, rank, label)
    return best


def _tier_rank_of_role(role_name):
    for tier_key, rank, names, _label in ROLE_HIERARCHY:
        if role_name in names:
            return rank
    return -1  # not part of the hierarchy at all


def check_permissions(accountid, command):
    """
    Checks The Permission To Player To Executive Command.

    Hierarchy-aware: a player's effective command set is the UNION of
    every role they're personally in, PLUS -- if they're in a hierarchy
    role (owner/staff/admin/vip) -- every command granted to any
    hierarchy role at or below their own rank. So an admin automatically
    gets everything vip has, staff automatically gets everything admin
    and vip have, etc, even if the admin/staff role's own command list in
    roles.json doesn't explicitly repeat those commands.

    Parameters:
        accountid : str
        command : str

    Returns:
        Boolean
    """
    if is_server(accountid):
        return True

    roles = pdata.get_roles()
    _tier_key, my_rank, _label = get_account_tier(accountid)

    for role_name, role in roles.items():
        in_role = accountid in role.get("ids", [])
        # Either they're personally in this role, OR this role is part of
        # the hierarchy at-or-below their own rank (inherited access).
        inherited = my_rank > 0 and 0 <= _tier_rank_of_role(role_name) <= my_rank
        if not (in_role or inherited):
            continue

        commands = role.get("commands", [])
        if "ALL" in commands or command in commands:
            return True

    return False


def is_server(accid):
    for i in bs.get_game_roster():
        if i['account_id'] == accid and i['client_id'] == -1:
            return True
    return False
