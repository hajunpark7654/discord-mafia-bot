GUILD_ID = 1515228078505201684
PRESHOUT_CHANNEL_ID = 1515229943045554186
ADMIN_USER_ID = 926932089062977626

GAME_CATEGORY_NAME = "🎭 Mafia Game"
TOWN_SQUARE_CHANNEL = "town-square"
MAFIA_DEN_CHANNEL = "mafia-den"
DEAD_CHAT_CHANNEL = "beyond-the-veil"
LOBBY_CHANNEL = "mafia-lobby"

PLAYER_ROLE_NAME = "Mafia Player"
DEAD_ROLE_NAME = "Dead Player"

AUTO_MODE_TIMEOUT = 300
HOSTED_MODE_TIMEOUT = 600
DEFENSE_TIMER = 45
PRESHOUT_WAIT_TIME = 120
MIN_PLAYERS = 5
NOMINATIONS_REQUIRED = 2
PRESHOUT_AUTO_CANCEL_IDLE = 300
PRESHOUT_AUTO_CANCEL_JOINED = 120
RANDOM_AUTO_MIN_INTERVAL = 7200
RANDOM_AUTO_MAX_INTERVAL = 18000
RANDOM_AUTO_JOIN_WINDOW = 120
MAFIA_CHAT_OPEN_AT_NIGHT = True

POINTS = {
    "town_win": 10, "town_win_bonus": 15,
    "mafia_win": 15, "mafia_win_bonus": 20,
    "neutral_win": 10, "neutral_win_bonus": 15,
    "jester_win": 15, "jester_win_bonus": 20,
    "bh_win": 15, "bh_win_bonus": 20,
    "participation": 5,
    "premature_end": 3,
}

FACTION_MAFIA = "mafia"
FACTION_TOWN = "town"
FACTION_NEUTRAL = "neutral"

TEAMS = {
    "mafia_killing": {"faction": FACTION_MAFIA, "display": "🔪 Mafia Killing"},
    "mafia_support": {"faction": FACTION_MAFIA, "display": "👥 Mafia Support"},
    "neutral_chaotic": {"faction": FACTION_NEUTRAL, "display": "💥 Chaotic Neutral"},
    "neutral_lawful": {"faction": FACTION_NEUTRAL, "display": "⚖️ Neutral Lawful"},
    "town": {"faction": FACTION_TOWN, "display": "🏘️ Town"},
    "town_support": {"faction": FACTION_TOWN, "display": "🔬 Town Support"},
}

TEAM_DISPLAY_ORDER = ["mafia_killing", "mafia_support", "neutral_chaotic", "neutral_lawful", "town", "town_support"]

ROLE_REGISTRY = {
    "mafia": {"team": "mafia_killing", "faction": FACTION_MAFIA, "killing": True, "points_key": "mafia_win"},
    "ambusher": {"team": "mafia_killing", "faction": FACTION_MAFIA, "killing": True, "points_key": "mafia_win"},
    "framer": {"team": "mafia_support", "faction": FACTION_MAFIA, "killing": False, "points_key": "mafia_win"},
    "consort": {"team": "mafia_support", "faction": FACTION_MAFIA, "killing": False, "points_key": "mafia_win"},
    "janitor": {"team": "mafia_support", "faction": FACTION_MAFIA, "killing": False, "points_key": "mafia_win"},
    "consigliere": {"team": "mafia_support", "faction": FACTION_MAFIA, "killing": False, "points_key": "mafia_win"},
    "town": {"team": "town", "faction": FACTION_TOWN, "killing": False, "points_key": "town_win"},
    "doctor": {"team": "town", "faction": FACTION_TOWN, "killing": False, "special": True, "points_key": "town_win"},
    "sheriff": {"team": "town", "faction": FACTION_TOWN, "killing": False, "special": True, "points_key": "town_win"},
    "lawyer": {"team": "town_support", "faction": FACTION_TOWN, "killing": False, "special": True, "points_key": "town_win"},
    "psychic": {"team": "town_support", "faction": FACTION_TOWN, "killing": False, "special": True, "points_key": "town_win"},
    "lookout": {"team": "town_support", "faction": FACTION_TOWN, "killing": False, "special": True, "points_key": "town_win"},
    "investigator": {"team": "town_support", "faction": FACTION_TOWN, "killing": False, "special": True, "points_key": "town_win"},
    "medium": {"team": "town_support", "faction": FACTION_TOWN, "killing": False, "special": True, "points_key": "town_win"},
    "pirate": {"team": "neutral_chaotic", "faction": FACTION_NEUTRAL, "killing": True, "points_key": "neutral_win"},
    "bounty_hunter": {"team": "neutral_chaotic", "faction": FACTION_NEUTRAL, "killing": True, "points_key": "bh_win"},
    "teleporter": {"team": "neutral_chaotic", "faction": FACTION_NEUTRAL, "killing": False, "points_key": "neutral_win"},
    "jester": {"team": "neutral_lawful", "faction": FACTION_NEUTRAL, "killing": False, "points_key": "jester_win"},
    "veteran": {"team": "neutral_lawful", "faction": FACTION_NEUTRAL, "killing": True, "points_key": "neutral_win"},
    "survivor": {"team": "neutral_lawful", "faction": FACTION_NEUTRAL, "killing": False, "points_key": "survivor_win"},
}

ROLE_EMOJIS = {
    "mafia": "🔪", "ambusher": "🌲",
    "framer": "🖼️", "consort": "🔒", "janitor": "🧹", "consigliere": "🔍",
    "town": "🏘️", "doctor": "💉", "sheriff": "🔎",
    "lawyer": "⚖️", "psychic": "🔮", "lookout": "👁️", "investigator": "🔬", "medium": "👻",
    "pirate": "🏴‍☠️", "bounty_hunter": "🎯", "teleporter": "🌀",
    "jester": "🤡", "veteran": "🎖️", "survivor": "🛡️",
}

ROLE_DESCRIPTIONS = {
    "mafia": "Kill one person each night, or choose not to.",
    "ambusher": "Lurk at a player's location; kill anyone who visits them.",
    "framer": "Frame a person each night to seem suspicious.",
    "consort": "Role-block a non-mafia player each night.",
    "janitor": "Clean a Mafia kill once — victim's role hidden (only you see it).",
    "consigliere": "Investigate a player each night and learn their exact role.",
    "town": "No special ability. Discuss and vote.",
    "doctor": "Protect one player each night (self-heal once).",
    "sheriff": "Investigate one player each night for alignment.",
    "lawyer": "Your vote counts as two. Only you know.",
    "psychic": "Occasionally see 3 players, at least one evil.",
    "lookout": "See who visited a player at night.",
    "investigator": "Investigate a player and get 3 possible roles they could be.",
    "medium": "Occasionally access dead chat at night.",
    "pirate": "Duel a player each night (RPS). Win 2 duels to win.",
    "bounty_hunter": "Kill your target (told their role). Survive to win.",
    "teleporter": "Swap two players each night, redirecting actions.",
    "jester": "Get voted out during the day to win.",
    "veteran": "2 alerts — kills all visitors, immune at night.",
    "survivor": "Has one bulletproof vest. Survive to win.",
}

POINTS = {
    "town_win": 10, "town_win_bonus": 15,
    "mafia_win": 15, "mafia_win_bonus": 20,
    "neutral_win": 10, "neutral_win_bonus": 15,
    "jester_win": 15, "jester_win_bonus": 20,
    "bh_win": 15, "bh_win_bonus": 20,
    "survivor_win": 15, "survivor_win_bonus": 20,
    "participation": 5,
    "premature_end": 3,
}

ROLE_DISTRIBUTION = {
    5:  {"mafia_killing": 1, "mafia_support": 0, "neutral": 0, "doctor": 1, "sheriff": 0, "town": 3, "town_support": 0},
    6:  {"mafia_killing": 1, "mafia_support": 0, "neutral": 1, "doctor": 1, "sheriff": 1, "town": 2, "town_support": 0},
    7:  {"mafia_killing": 1, "mafia_support": 0, "neutral": 2, "doctor": 1, "sheriff": 1, "town": 2, "town_support": 0},
    8:  {"mafia_killing": 1, "mafia_support": 1, "neutral": 1, "doctor": 1, "sheriff": 1, "town": 2, "town_support": 1},
    9:  {"mafia_killing": 1, "mafia_support": 1, "neutral": 1, "doctor": 1, "sheriff": 1, "town": 3, "town_support": 1},
    10: {"mafia_killing": 1, "mafia_support": 1, "neutral": 2, "doctor": 1, "sheriff": 1, "town": 3, "town_support": 1},
}

MAFIA_KILLING_POOL = ["mafia", "ambusher"]
MAFIA_KILLING_WEIGHTS = [100, 10]

MAFIA_SUPPORT_POOL = ["framer", "consort", "consigliere", "janitor"]
MAFIA_SUPPORT_WEIGHTS = [25, 25, 25, 15]

NEUTRAL_CHAOTIC_POOL = ["pirate", "bounty_hunter", "teleporter"]
NEUTRAL_LAWFUL_POOL = ["jester", "veteran", "survivor"]

TOWN_SUPPORT_POOL = ["lawyer", "psychic", "lookout", "investigator", "medium"]
TOWN_SUPPORT_WEIGHTS = [30, 25, 20, 15, 10]

NIGHT_DEATH_MESSAGES = [
    "{name}'s remains were found scattered in the field.",
    "{name} was found armless, hanging from a tree.",
    "{name} was found with multiple deep stab wounds to the chest.",
    "{name}'s head was discovered in the fridge.",
    "{name} appears to have fallen down the stairs and died.",
    "{name} was found with a single gunshot wound to the back of the head.",
]

VOTE_OUT_MESSAGES = [
    "{name} was hung at the town-square.",
    "{name} was decapitated by the guillotine.",
    "{name}'s limbs were torn from their torso.",
]

GAME_OPTIONS = {
    "Mafia": {"min_players": 5, "max_players": 20},
}
