from discord import Member


class Player:
    def __init__(self, member: Member = None, is_dummy=False, dummy_id=0):
        self.user_id = dummy_id if is_dummy else member.id
        self.member = member
        self.name = f"Dummy {dummy_id}" if is_dummy else member.display_name
        self.mention = f"<@{dummy_id}>" if is_dummy else member.mention
        self.is_dummy = is_dummy
        self.role = None
        self.alive = True
        self.original_roles = []
        self.night_action = None
        self.night_target = None
        self.day_vote = None
        self.trial_vote = None
        self.nomination_target = None
        self.protected = False
        self.roleblocked = False
        self.framed = False
        self.visited_by = []
        self.alerts_used = 0
        self.duel_wins = 0
        self.self_heal_used = False
        self.janitor_used = False
        self.bh_killed = False
        self.bh_target_role = None
        self.bh_exposed = False
        self.survivor_vest = True
        self.medium_used = False
        self.points_earned = 0

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "name": self.name,
            "role": self.role,
            "alive": self.alive,
        }
