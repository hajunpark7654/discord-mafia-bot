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

ROLE_REGISTRY = {
    "mafia": {"team": "mafia", "killing": True, "points_key": "mafia_win"},
    "framer": {"team": "mafia", "killing": False, "points_key": "mafia_win"},
    "consort": {"team": "mafia", "killing": False, "points_key": "mafia_win"},
    "janitor": {"team": "mafia", "killing": False, "points_key": "mafia_win"},
    "town": {"team": "town", "killing": False, "points_key": "town_win"},
    "doctor": {"team": "town", "killing": False, "special": True, "points_key": "town_win"},
    "sheriff": {"team": "town", "killing": False, "special": True, "points_key": "town_win"},
    "lawyer": {"team": "town", "killing": False, "special": True, "points_key": "town_win"},
    "psychic": {"team": "town", "killing": False, "special": True, "points_key": "town_win"},
    "lookout": {"team": "town", "killing": False, "special": True, "points_key": "town_win"},
    "pirate": {"team": "neutral", "killing": True, "points_key": "neutral_win"},
    "jester": {"team": "neutral", "killing": False, "points_key": "jester_win"},
    "teleporter": {"team": "neutral", "killing": False, "points_key": "neutral_win"},
    "veteran": {"team": "neutral", "killing": True, "points_key": "neutral_win"},
    "bounty_hunter": {"team": "neutral", "killing": True, "points_key": "bh_win"},
}

ROLE_EMOJIS = {
    "mafia": "🔪", "framer": "🖼️", "consort": "🔒", "janitor": "🧹",
    "town": "🏘️", "doctor": "💉", "sheriff": "🔎", "lawyer": "⚖️",
    "psychic": "🔮", "lookout": "👁️",
    "pirate": "🏴‍☠️", "jester": "🤡", "teleporter": "🌀", "veteran": "🎖️",
    "bounty_hunter": "🎯",
}

ROLE_DESCRIPTIONS = {
    "mafia": "Kill one person each night.",
    "framer": "Frame a person each night to seem suspicious.",
    "consort": "Role-block a non-mafia player each night.",
    "janitor": "Clean a Mafia kill once — role stays hidden.",
    "town": "No special ability. Discuss and vote.",
    "doctor": "Protect one player each night (self-heal once).",
    "sheriff": "Investigate one player each night for alignment.",
    "lawyer": "Your vote counts as two. Only you know.",
    "psychic": "Occasionally see 3 players, at least one evil.",
    "lookout": "See who visited a player at night.",
    "pirate": "Duel a player each night (RPS). Win 2 duels to win.",
    "jester": "Get voted out during the day to win.",
    "teleporter": "Swap two players each night, redirecting actions.",
    "veteran": "2 alerts — kills all visitors, immune at night.",
    "bounty_hunter": "Kill your target (told their role). Survive to win.",
}

ROLE_DISTRIBUTION = {
    5:  {"mafia": 1, "mafia_support": 0, "neutral": 0, "doctor": 1, "sheriff": 0, "town": 3, "special_town": 0},
    6:  {"mafia": 1, "mafia_support": 0, "neutral": 1, "doctor": 1, "sheriff": 1, "town": 2, "special_town": 0},
    7:  {"mafia": 1, "mafia_support": 0, "neutral": 2, "doctor": 1, "sheriff": 1, "town": 2, "special_town": 0},
    8:  {"mafia": 1, "mafia_support": 1, "neutral": 1, "doctor": 1, "sheriff": 1, "town": 2, "special_town": 1},
    9:  {"mafia": 1, "mafia_support": 1, "neutral": 1, "doctor": 1, "sheriff": 1, "town": 3, "special_town": 1},
    10: {"mafia": 1, "mafia_support": 1, "neutral": 2, "doctor": 1, "sheriff": 1, "town": 3, "special_town": 1},
}

MAFIA_SUPPORT_POOL = ["framer", "consort", "janitor"]
SPECIAL_TOWN_POOL = ["lawyer", "psychic", "lookout"]
NEUTRAL_POOL = ["pirate", "jester", "teleporter", "veteran", "bounty_hunter"]

GAME_OPTIONS = {
    "Mafia": {"min_players": 5, "max_players": 20},
}
