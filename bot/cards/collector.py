import discord
from bot.database.driver import Connection, USE_PG, q
from bot.cards.db import get_all_templates, get_card_counts_by_rarity
from bot.database.db import add_points

COLLECTOR_TIERS = {
    "F": {"base": 50, "shiny": 2, "mythical": 1, "points": 50},
    "D": {"base": 45, "shiny": 1, "mythical": 1, "points": 50},
    "C": {"base": 40, "shiny": 1, "mythical": 1, "points": 50},
    "B": {"base": 35, "shiny": 1, "mythical": 1, "points": 50},
    "A": {"base": 20, "shiny": 1, "mythical": 1, "points": 50},
    "S": {"base": 5, "shiny": 1, "mythical": 0, "points": 75},
}

COLLECTOR_ROLE_NAME = "Tier 1 Collector"


def _count_cards(owner_id, template_id):
    conn = Connection()
    cur = conn.execute(q(
        "SELECT "
        "  SUM(CASE WHEN (is_shiny = 0 OR is_shiny IS NULL) AND (is_mythical = 0 OR is_mythical IS NULL) THEN 1 ELSE 0 END) as base_count, "
        "  SUM(CASE WHEN is_shiny = 1 OR is_mythical = 1 THEN 1 ELSE 0 END) as shiny_count, "
        "  SUM(CASE WHEN is_mythical = 1 THEN 1 ELSE 0 END) as mythical_count "
        "FROM card_instances WHERE owner_id = ? AND template_id = ?"
    ), (owner_id, template_id))
    row = cur.fetchone()
    conn.close()
    if USE_PG:
        return {"base": row[0] or 0, "shiny": row[1] or 0, "mythical": row[2] or 0}
    return {"base": row[0] or 0, "shiny": row[1] or 0, "mythical": row[2] or 0}


def _is_claimed(user_id, template_id):
    conn = Connection()
    cur = conn.execute(q("SELECT 1 FROM collector_claims WHERE user_id = ? AND template_id = ?"), (user_id, template_id))
    row = cur.fetchone()
    conn.close()
    return row is not None


def _record_claim(user_id, template_id):
    conn = Connection()
    if USE_PG:
        conn.execute(q("INSERT INTO collector_claims (user_id, template_id) VALUES (?, ?) ON CONFLICT DO NOTHING"),
                     (user_id, template_id))
    else:
        conn.execute(q("INSERT OR IGNORE INTO collector_claims (user_id, template_id) VALUES (?, ?)"),
                     (user_id, template_id))
    conn.commit()
    conn.close()


def _delete_required_cards(owner_id, template_id, req):
    conn = Connection()

    cur = conn.execute(q(
        "SELECT id FROM card_instances WHERE owner_id = ? AND template_id = ? AND is_mythical = 1 ORDER BY id"
    ), (owner_id, template_id))
    mythical_ids = [r[0] for r in (cur.fetchall() if USE_PG else cur)]

    cur = conn.execute(q(
        "SELECT id FROM card_instances WHERE owner_id = ? AND template_id = ? AND is_shiny = 1 AND (is_mythical = 0 OR is_mythical IS NULL) ORDER BY id"
    ), (owner_id, template_id))
    shiny_ids = [r[0] for r in (cur.fetchall() if USE_PG else cur)]

    cur = conn.execute(q(
        "SELECT id FROM card_instances WHERE owner_id = ? AND template_id = ? AND (is_shiny = 0 OR is_shiny IS NULL) AND (is_mythical = 0 OR is_mythical IS NULL) ORDER BY id"
    ), (owner_id, template_id))
    normal_ids = [r[0] for r in (cur.fetchall() if USE_PG else cur)]

    to_delete = []

    taken_myth = mythical_ids[:req["mythical"]]
    to_delete.extend(taken_myth)

    remaining_shiny = max(0, req["shiny"] - req["mythical"])
    if remaining_shiny > 0:
        taken_shiny = shiny_ids[:remaining_shiny]
        to_delete.extend(taken_shiny)
        if len(taken_shiny) < remaining_shiny:
            leftover = remaining_shiny - len(taken_shiny)
            extra_myth = mythical_ids[len(taken_myth):len(taken_myth) + leftover]
            to_delete.extend(extra_myth)

    to_delete.extend(normal_ids[:req["base"]])

    if to_delete:
        placeholders = ",".join("?" * len(to_delete))
        conn.execute(q(f"DELETE FROM card_instances WHERE id IN ({placeholders})"), tuple(to_delete))
    conn.commit()
    conn.close()


def _get_claim_count(user_id):
    conn = Connection()
    cur = conn.execute(q("SELECT COUNT(*) FROM collector_claims WHERE user_id = ?"), (user_id,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else 0


def get_quest_progress(user_id, template_id):
    tid = template_id if isinstance(template_id, int) else None
    counts = _count_cards(user_id, tid)
    claimed = _is_claimed(user_id, tid)
    return counts, claimed


def get_all_progress(user_id):
    templates = get_all_templates()
    results = []
    for t in templates:
        counts, claimed = get_quest_progress(user_id, t["id"])
        tier = t.get("rarity", "F")
        if tier not in COLLECTOR_TIERS:
            continue
        req = COLLECTOR_TIERS[tier]
        base_ok = counts["base"] >= req["base"]
        shiny_ok = counts["shiny"] >= req["shiny"]
        myth_ok = counts["mythical"] >= req["mythical"]
        complete = base_ok and shiny_ok and myth_ok and not claimed
        results.append({
            "template": t,
            "tier": tier,
            "counts": counts,
            "req": req,
            "claimed": claimed,
            "complete": complete,
            "progress": min(1.0, sum([
                min(1.0, counts["base"] / req["base"]),
                min(1.0, counts["shiny"] / req["shiny"]) if req["shiny"] > 0 else 1.0,
                min(1.0, counts["mythical"] / req["mythical"]) if req["mythical"] > 0 else 1.0,
            ]) / (3 if req["mythical"] > 0 else 2))
        })
    results.sort(key=lambda x: ("SABCDEF".index(x["tier"]) if x["tier"] in "SABCDEF" else 99, -x["progress"]))
    return results


async def claim_quest(user_id, template_id, guild):
    template = next((t for t in get_all_templates() if t["id"] == template_id), None)
    if not template:
        return False, "Template not found."

    tier = template.get("rarity", "F")
    if tier not in COLLECTOR_TIERS:
        return False, f"No collector quest for {tier} tier."
    req = COLLECTOR_TIERS[tier]

    if _is_claimed(user_id, template_id):
        return False, "You already claimed this template!"

    counts = _count_cards(user_id, template_id)
    if counts["base"] < req["base"]:
        return False, f"Not enough base cards ({counts['base']}/{req['base']})."
    if counts["shiny"] < req["shiny"]:
        return False, f"Not enough shiny/mythical cards ({counts['shiny']}/{req['shiny']})."
    if counts["mythical"] < req["mythical"]:
        return False, f"Not enough mythical cards ({counts['mythical']}/{req['mythical']})."

    _delete_required_cards(user_id, template_id, req)

    points = req["points"]
    add_points(user_id, points)

    is_first = _get_claim_count(user_id) == 0

    role = discord.utils.get(guild.roles, name=COLLECTOR_ROLE_NAME)
    if not role:
        role = await guild.create_role(name=COLLECTOR_ROLE_NAME, color=0xFFD700, hoist=True,
                                       mentionable=True, reason="Collector series role")

    if is_first:
        member = guild.get_member(user_id)
        if member and role not in member.roles:
            try:
                await member.add_roles(role, reason="First collector claim")
            except:
                pass

    _record_claim(user_id, template_id)

    msg = f"Claimed **{template['name']}** [{tier}]!" + f" +**{points}** points."
    if is_first:
        msg += f" You also earned the **{COLLECTOR_ROLE_NAME}** role!"
    return True, msg
