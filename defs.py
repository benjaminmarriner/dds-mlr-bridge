"""Large definitions or those common to multiple modules."""

from collections import namedtuple

ORDER:list[str] = ["N","E","S","W"]
"""N,E,S,W"""

RANKS:list[str] = ["A","K","Q","J","T"]
"""A,K,Q,J,T,9,8,7,6,5,4,3,2"""
for rank in range(9,1,-1):
    RANKS.append(str(rank))

SUITS:list[str] = ["S","H","D","C","N"]
"""S,H,D,C,N"""

ORDERED_CONTRACT_BIDS = [] # All possible normalized contract bids, in order.
"""1C,1D,1H,1S,1N,2C,...,7N"""
for level in range(1,8):
    for trump in ["C","D","H","S","N"]:
        ORDERED_CONTRACT_BIDS.append(str(level)+trump)

WbfInfo = namedtuple("WbfInfo",["mp","pp","wbf_names","wbf_initials"])

class Player():

    def __init__(self,name:str):
        
        self.name = name

        self.auctions_analyzed = 0

        self.defender_missed_current_double = 0
        self.weighted_defender_missed_current_double = 0

        self.defender_erroneously_doubled = 0
        self.weighted_defender_erroneously_doubled = 0

        self.defender_missed_higher_contract = 0 
        self.weighted_defender_missed_higher_contract = 0

        self.declarer_missed_higher_contract = 0
        self.weighted_declarer_missed_higher_contract = 0

        self.declarer_missed_doubling_opponents_last_bid = 0
        self.weighted_declarer_missed_doubling_opponents_last_bid = 0

        self.declarer_missed_opponents_last_redouble = 0
        self.weighted_declarer_missed_opponents_last_redouble = 0

        self.declarer_missed_redoubling_opponents_erroneous_double = 0
        self.weighted_declarer_missed_redoubling_opponents_erroneous_double = 0

        self.declarer_missed_opponents_last_bid = 0
        self.weighted_declarer_missed_opponents_last_bid = 0

        self.declarer_erroneous_redouble = 0
        self.weighted_declarer_erroneous_redouble = 0

        self.passed_higher_contract = 0
        self.weighted_passed_higher_contract = 0


        self.claims = 0
        self.claim_mistakes = 0
        self.weighted_claim_mistakes = 0

        self.leads = 0
        self.lead_mistakes = 0
        self.weighted_lead_mistakes = 0

        self.cards_played_as_declarer = 0
        self.play_mistakes_as_declarer = 0
        self.weighted_play_mistakes_as_declarer = 0

        self.cards_played_as_defender = 0
        self.play_mistakes_as_defender = 0
        self.weighted_play_mistakes_as_defender = 0

    def __str__(self)->str:
        return_str:str = ""
        for attr in [
            "name","claims","claim_mistakes","weighted_claim_mistakes","leads","lead_mistakes","weighted_lead_mistakes",
            "cards_played_as_declarer","play_mistakes_as_declarer","weighted_play_mistakes_as_declarer","cards_played_as_defender",
            "play_mistakes_as_defender","weighted_play_mistakes_as_defender","auctions_analyzed","defender_missed_current_double",
            "weighted_defender_missed_current_double","defender_erroneously_doubled","weighted_defender_erroneously_doubled",
            "defender_missed_higher_contract","weighted_defender_missed_higher_contract","declarer_missed_higher_contract",
            "weighted_declarer_missed_higher_contract","declarer_missed_doubling_opponents_last_bid",
            "weighted_declarer_missed_doubling_opponents_last_bid","declarer_missed_opponents_last_redouble",
            "weighted_declarer_missed_opponents_last_redouble","declarer_missed_redoubling_opponents_erroneous_double",
            "weighted_declarer_missed_redoubling_opponents_erroneous_double","declarer_missed_opponents_last_bid",
            "weighted_declarer_missed_opponents_last_bid","declarer_erroneous_redouble","weighted_declarer_erroneous_redouble",
            "passed_higher_contract","weighted_passed_higher_contract"
            ]:
            return_str+=str(self.__getattribute__(attr))+","

        return return_str[:-1]