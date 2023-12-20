"""
This module is a one-time use designed to read one specific database file containing bridge deals to
validate and clean the data, and return the cleaned data alongside statistics on where
the errors occur. This module uses particular assumptions about the state of the data from this specific database.
As such, this module should not be used for other purposes.

The columns from the database along with the assumptions made about their possible values are:

event: NO RESTRICTIONS
date: one of ["", "?", "#"] or in the form YYYY.%
bidstart: one of ["N","E","S","W","","9","7","4","3"]
dealer: one of ["N","E","S","W",""]
deal: "", or in PBN format, %.%.%.% %.%.%.% %.%.%.% %.%.%.%
vulnerable: one of ["None","NS","EW","All","NZ","All]"]
auction: NO RESTRICTIONS
westname: NO RESTRICTIONS
eastname: NO RESTRICTIONS
southname: NO RESTRICTIONS
eastname: NO RESTRICTIONS
result: integer between 0 and 13 inclusive, and 14
play: NO RESTRICTIONS
lead: one of ["N","E","S","W",""]
declarer: one of ["N","E","S","W","S^",""]
contract: one of ["Pass","pass"] or in the form lsd where l in [1-7], s in ["S","H","D","C","NT"], d in ["","X","XX"]
"""

from collections import Counter
import copy
from functools import cache
import sqlite3
import re
from typing import Any,Tuple
from bs4 import BeautifulSoup

import requests
from exceptions import *
from defs import SUITS,ORDER,ORDERED_CONTRACT_BIDS,RANKS, WbfInfo

def get_clean_boards(db_path:str)->Tuple[list[dict[str,Any]],dict[str,int],dict[str,int],dict[str,int]]:

    """
    Opens the db defined at db_path and validates the boards.
    Returns a tuple, first element is a list of dictionaries that define each board.
    Second element is a dictionary mapping critical error messages that led to a board being skipped, to their frequency.
    Third element is a dictionary mapping reasons the auction was not valid to their frequency.
    Fourth element is a dictionary mapping reasons the play sequence was not valid to their frequency.
    """

    con:sqlite3.Connection = sqlite3.connect(db_path)
    cur:sqlite3.Cursor = con.cursor()

    boards: list[dict[str,Any]] = []
    board_errors:dict[str,int] = {}
    auction_errors:dict[str,int] = {}
    play_errors:dict[str,int] = {}

    wbf_data:tuple[tuple[str,WbfInfo],...] = get_wbf_data()

    for (event,date,northname,eastname,southname,westname,deal,vulnerable,dealer,bidstart,auction,contract,declarer,lead,play,result) in \
    cur.execute("SELECT event,date,northname,eastname,southname,westname,deal,vulnerable,dealer,bidstart,auction,contract,declarer,lead,play,result FROM bridgedeals;"):
        
        board:dict[str,Any] = {}
        auction_error:str = ""
        play_error:str = ""

        try:

            board,auction_error,play_error = clean_board(event,date,northname,eastname,southname,westname,deal,vulnerable,dealer,bidstart,auction,contract,declarer,lead,play,result,wbf_data)
            
            if auction_error not in auction_errors:
                auction_errors[auction_error] = 0
            auction_errors[auction_error]+=1

            if play_error not in play_errors:
                play_errors[play_error] = 0
            play_errors[play_error]+=1

        except BoardError as exc:
            
            exc_str:str = str(exc)
            if exc_str not in board_errors:
                board_errors[exc_str] = 0
            board_errors[exc_str]+=1

            continue

        boards.append(board)
        
    con.close()

    return boards,board_errors,auction_errors,play_errors

def validate_deal(deal:str) -> list[list[str]]:
    """
    Validates the deal, and returns a list of lists containing the cards that each player has, starting with north, going clockwise.
    A deal is valid if every card is valid, every card appears exactly once, and every hand has 13 cards.
    If the deal is invalid, a subclass of BoardError is raised.
    Every non-empty deal is in the form "*:%.%.%.% %.%.%.% %.%.%.% %.%.%.%" where * is one of ["N","S","E","W"].
    example N:AK75.54.987653.A Q.AT983.42.JT753 642.KQJ7.AQJ.962 JT983.62.KT.KQ84 or S:75.K6.KQ9754.T73 Q4.J843.J862.Q92 92.AQ752.AT3.K85 AKJT863.T9..AJ64
    """

    if not deal:
        raise MissingDealError()

    player_offset:int = ORDER.index(deal[0])
    deal = deal[2:] # Remove the "N:" part of the deal.

    deck:list[list[str]]=[RANKS[:] for _ in range(4)]
    player_hands:list[list[str]] = [[] for _ in range(4)]
    hands = deal.split(" ")
    for player_pos,hand in enumerate(hands):
        suits = hand.split(".")
        if sum(len(suit) for suit in suits)!=13:
            raise UnbalancedDealError()
        for suit_pos,suit in enumerate(suits):
            for card in suit:
                try:
                    deck[suit_pos].remove(card)
                except ValueError:
                    raise CardError()
                player_hands[(player_pos+player_offset)%4].append(SUITS[suit_pos]+card)

    return player_hands

def get_cleaned_bids(auction:str) -> list[str]:

    """
    Clean the auction. Return a list of valid bids.
    Below is a case-insensitive set of all bids made in the database.

    {'', '=0=2H', '1D!', '4H!', '1NT', 'PASS5S', '5S', 'PC', '1NT2S', 'XXX', '7NT', 'XPASS', '2NT!', '1C3D', '2D2H', '2H', '2N', '1.0', '1NT!',
    '=0=', '=;=', '4C!', '3S!', '=0=2D', '4S!', '=0=3H', '3NT!', '2NT3S', 'X3C', '22T', '2D!', '4C', '1DX', '7H', '=6=', '2NT', 'XX', '$1',
    '=3=', '1C2D', '?', '=<=', '6H', '===', 'XX2C', '=2=', '??', 'X2H', '=:=', '2CPASS', '=0=2S', '5H', '6S', '3D!', '3CPASS', '34', '1SPASS',
    '=0=1S', '=0=1NT', 'X2S', '1H!', '6NT', '1N', '3S', '*', '4H', '1C1H', '4D!', '1SX', '=0=', 'S3', 'X', '2S', '4S', '1DPASS', '=4=', '6C',
    '1D1S', '5C', '7D', '1S', '=0=3S', 'X!', '12T', '%', '5S!', '=>=', '==', '=5=', '=7=', '4NT', '3NT', '5D!', 'DBL', '6D', '=?=', '1C1D',
    '1C!', '2D', '2C!', '5D', '3H', '3C!', '1D1NT', '2H2NT', 'P!', '1C', '7S', '1CPASS', 'PAS', '5H!', '=0=2C', '1D', '1S!', '2C', '2NTPASS',
    'XX2S', '2SPASS', '5C!', '4HPASS', '7C', '=0=1H', '!!', 'X3H', '2HPASS', '2H!', '4NT!', '=8=', '1NTPASS', '1NTX', '3C', '1NT2C', '=1=', 
    '2.0', '3H!', 'AP', '2DPASS', '=9=', '2S!', '3D', 'PBN', '3SPASS', '=0=3D', 'XXPASS', 'REDBL', '!', 'P', '1H', 'PASS', '=0=1D', '1D1H', 
    'XX!', '=0=4D', '3DPASS', '5NT', '4D'}
    
    We split the bids into 5 categories:
        1. valid (see VALID_BIDS below),
        2. valid or NT bid with a trailing "!" or a leading "=0=",
        3. recognizable and can be normalized to a valid bid (see NORMALIZE_BID below),
        4. A concatenation of two legal bids, or a NT bid
        5. An illegal bid. Most likely an alert or other extraneous information.

    Bids in categories 1 through 4 are normalized and added to the return list. Category 5 bids are ignored and removed from 
    the (still potentially legal) auction.
    
    Below is a set of all bids that are ignored (category 5)

    {"=8=","!!","=9=","==","1.0","22T","PC","12T","=4=","PBN","=1=","=3=","=:=","34","===",
    "%","2.0","=<=","=5=","=2=","=>=","!","??","=6=","?","=7=","=;=","*","=?=",""}

    Some ignored bids that could be actual bids are "12T" (1NT), "22T" (2NT), "PC" (P), and "34" (?).
    All other ignored bids are likely extraneous information, or signify an alert.
    """

    NORMALIZE_BID:dict[str,str] = {"PASS":"P","AP":"P P P","DBL":"X","REDBL":"R","XX":"R","PAS":"P","S3":"3S","XXX":"X R"}
    # There is no auction that is only "AP", so "AP" never has to be interpreted as "P P P P".

    VALID_BIDS:set[str] = set(["P","R","X"]).union(ORDERED_CONTRACT_BIDS)

    cleaned_bids:list[str] = []

    for bid in auction.split(" "):
        bid = bid.upper() # Ensure the matching is case-insensitive.

        # Convert category 2 bids to category 1 (or category 4 for NT).
        bid = bid.rstrip("!")
        bid = bid.lstrip("=0=")

        # Add category 1 bids to return list.
        if bid in VALID_BIDS:
            cleaned_bids.append(bid)
            continue

        try:
            # Add category 3 bids to return list.
            normalized_bid:str = NORMALIZE_BID[bid]
            cleaned_bids+=normalized_bid.split(" ") 
            # normalized_bid may be a space-seperated sequence of multiple valid bids.
            # If it is a single valid bid, then .split(" ") just returns a singleton list of that bid.
            continue
        except KeyError:
            # The bid is not recognized as one that can be normalized, continue with other methods.
            pass

        # Now, the bid is either a concatenation of legal bids or a NT bid (category 4), or an illegal bid (category 5).

        cleaned_bids += map(lambda bid: NORMALIZE_BID.get(bid,bid),re.findall("|".join(["XX","PASS"]+list(VALID_BIDS-set("P"))),bid))
        # Searches the bid string for valid bids, to identify the concatenations of legal bids and recognize NT bids as N.
        # In addition to VALID_BIDS, search for "XX" and "PASS" as these are the only normalizable non-valid bids that appear in a concatenation.
        # The normalizable non-valid bids must be normalized after being extracted, and are mapped through NORMALIZE_BID.
        # We do not search for "P", as all conatenations that intend to indicate a pass use "PASS". We do not wish to identify illegal bids such as "PBN" as "P".
        # We ensure "XX" appears before "X" in the regex matching list so that "XX" in a concatenation is matched as "XX" and not "X".
        # Note that the special case of a bid concatenation, "XXX" is handled by NORMALIZE_BID.
        # Note also that the order of the list returned by re.findall must be maintained as the bids were intended to appear in that order.
        # If the bid was not handled by the above (cleaned_bids was not appended to), the bid is ignored.

    return cleaned_bids

def validate_auction(auction:str) -> str:

    """
    Ensure the auction is valid. 
    Returns the cleaned auction as a string.
    Raises an AuctionError if an error occurs.
    """

    if not auction:
        raise MissingAuctionError()

    # First, we clean the auction.
    cleaned_bids = get_cleaned_bids(auction)
    cleaned_auction = " ".join(cleaned_bids) # Convert the list back into a space-seperated string.

    if cleaned_auction.find("P P P",1) != len(cleaned_auction)-5: 
        # Three passes must appear exactly once at the end of the auction, with the exception of three passes to start the auction.
        raise PassError()
    
    # Seperate the bids into contract bids, and a list of lists of bids between each contract bid.
    contract_bids:list[str] = []
    non_contract_bids:list[list[str]] = [[]] 
    number_of_contract_bids:int = 0 
    for bid in cleaned_bids:
        if bid not in ORDERED_CONTRACT_BIDS:
            non_contract_bids[number_of_contract_bids].append(bid)
        else:
            contract_bids.append(bid)
            non_contract_bids.append([])
            number_of_contract_bids+=1

    # Ensure that every contract bid is increasing
    current_bid_index:int = -1
    for bid in contract_bids:
        if ORDERED_CONTRACT_BIDS.index(bid) <= current_bid_index:
            raise ContractBidError()
        current_bid_index = ORDERED_CONTRACT_BIDS.index(bid)

    # Ensure the consistency of the double/redouble bids.
    for contract_bid_made,bid_sequence in enumerate(non_contract_bids):
        doubled=False
        redoubled=False
        for pos,bid in enumerate(bid_sequence):
            if bid=="X": # Double bid has been made
                if doubled or redoubled or pos%2 or not contract_bid_made: # The side allowed to make double bids appear at even indexes.
                    raise DoubleBidError()
                doubled = True
            elif bid=="R": # Redouble bid has been made
                if not doubled or redoubled or not pos%2 or not contract_bid_made: #The side allowed to make redouble bids appear at odd indexes.
                    raise RedoubleBidError()
                redoubled = True
    return cleaned_auction

def ensure_non_contradiction(value1:str,value2:str) -> str:

    """
    Ensures value1 and value2 do not contradict each other.
    If they are the same, return that value.
    If they are not the same and both non-empty, raise a ContradictionError.
    If one is empty, return the other.
    """

    if value2:
        if value1 and value1!=value2:
            raise ContradictionError()
        return value2
    else:
        return value1
    
def normalize_contract(contract:str)->str:

    """
    Normalize the contract string.
    From the database, the contract.upper() is "PASS" or lsd where
    l in [1,2,3,4,5,6,7]
    s = ['NT','S','H','D','C']
    d = ['XX','X'].
    'NT' is normalized to 'N', 'XX' is normalized to 'R', 'Pass' is normalized to 'P'.
    """

    if contract.upper() == "PASS":
        return "P"
    
    if contract[-2:] == "XX":
        contract = contract[:-2] + "R"

    if contract[1:3] == "NT":
        contract = contract[:2]+contract[3:]

    return contract

def find_contract_from_auction(auction:str) -> str:
    """
    Read the auction string backwards, and find the last contract bid, and whether it was (re)doubled.
    Expects a clean auction. i.e. one that has been returned by validate_auction.
    Returns the contract deducible from the auction in the normalized way. i.e. the way that normalize_contract would return it.
    """

    if not auction:
        return ""

    contract, double = "",""
    for bid in reversed(auction.split(" ")):
        if bid=="R":
            double = "R"
        elif bid=="X":
            if double!="R":
                double = "X"
        elif bid!="P":
            contract = bid
            break
    if contract=="":
        return "P"
    return contract+double

def find_declarer_from_auction(auction:str,bidstart:str) -> str:
    """
    Finds the declarer from a clean auction using a proper bidstart.
    To do this, we must know who won the auction. Finding the contract does not require knowing who won. 
    Finding who won, also reveals the contract. So, this function needs to find who won, and then find the declarer.
    It therefore does not need the contract to be passed in.
    """

    if not auction or not bidstart:
        return ""
    
    # The declarer is the player from the winning partnership to have first bid the eventual trump suit.

    suit_to_first_player_to_bid = {"N":[-1,-1],"S":[-1,-1],"H":[-1,-1],"D":[-1,-1],"C":[-1,-1]} 
    # Value is first player from each side to have bid that trump suit, ordered ["NS","EW"]
    winning_bidder = -1
    winning_trump = ""
    current_bidder = ORDER.index(bidstart)
    for bid in auction.split(" "): # bid[1] is trump suit
        if bid in ORDERED_CONTRACT_BIDS:
            if suit_to_first_player_to_bid[bid[1]][current_bidder%2]==-1: # current_bidder%2 returns the bidder partnership, 0: "NS", 1: "EW".
                suit_to_first_player_to_bid[bid[1]][current_bidder%2] = current_bidder
            winning_bidder = current_bidder
            winning_trump = bid[1]
        current_bidder = (current_bidder+1)%4

    if not winning_trump:
        return ""
    
    return ORDER[suit_to_first_player_to_bid[winning_trump][winning_bidder%2]] # winning_bidder%2 returns the index of the winning side

def find_lead_from_declarer(declarer:str) ->str:

    """
    Given the declarer, return the lead. 
    The lead is to the left of the declarer.
    """

    if not declarer:
        return ""
    
    if declarer=="P":
        return "P"
    
    return ORDER[(ORDER.index(declarer)+1)%4]

def determine_trick_winner(trick:list[str],trump:str,lead:int) -> int:

    """
    Given a trick consisting of valid cards ordered in the way it was played,
    a valid trump suit, and a valid integer representation of player who lead this trick,
    return the integer representation of the player who won the trick.
    The player who won the trick is the player who played the highest rank trump suit, or,
    if no trump suit was ever played, the player who played the highest led suit.
    """

    RANK_TO_VALUE:dict[str,int] = {"T":10,"J":11,"Q":12,"K":13,"A":14}
    for i in range(2,10):
        RANK_TO_VALUE[str(i)] = i

    highest_trump:int = -1
    highest_led:int = -1
    winning_player:int = -1
    led_suit:str = trick[0][0]
    for pos,card in enumerate(trick):
        if card[0] == trump and RANK_TO_VALUE[card[1]] > highest_trump:
            highest_trump = RANK_TO_VALUE[card[1]]
            winning_player = (lead+pos)%4
        elif card[0] == led_suit and highest_trump==-1 and RANK_TO_VALUE[card[1]] > highest_led:
            highest_led = RANK_TO_VALUE[card[1]]
            winning_player = (lead+pos)%4
    return winning_player

def reneged(trick:list[str],hands:list[list[str]],lead:int) -> bool:

    """
    Reneging in bridge is having a card of the led suit, and not playing a card of the led suit.
    Returns True if any player reneged, False otherwise.

    hands is the holdings of each player AFTER the given trick was played, ordered in the typical way.
    trick may be full trick or a partial trick.
    lead is a valid integer representation.
    """

    led_suit:str = ""
    for pos,card in enumerate(trick):
        if pos==0:
            led_suit = trick[0][0]
        else:
            if card[0]!=led_suit and led_suit in set(card[0] for card in hands[(lead+pos)%4]):
                return True
    return False

def validate_dashes(ordered_trick:list[str]) -> int:

    """
    Returns the number of dashes in the ordered_trick.
    Assumes ordered_trick contains valid cards and is ordered in the way it was played.
    Also validates the dashes, ensuring the first card played to a trick is not a dash,
    that once a dash appears in a trick no card should follow it.
    Raises a subclass of PlaySequenceError if the dashes are invalid.
    """

    num_dashes:int = 0
    for pos,card in enumerate(ordered_trick):
        if card=="-":
            if pos==0:
                raise FirstCardIsDashError()
            num_dashes+=1
        else:
            if num_dashes:
                raise CardAfterDashError()
    
    return num_dashes

def validate_play(play_sequence:str,lead:str,hands:list[list[str]],trump:str) -> Tuple[str,list[int],int,int]:

    """
    Validates the play sequence and computes the number of tricks played and the number of tricks won by the declarers side.
    Returns a tuple of cleaned play_sequence, ordered player sequence, number of tricks played, number of tricks won by declarer.
    The cleaned play sequence will be a string of the cards played in the order that they were played with no spaces in between.
    The ordered player sequence is a list of the integer representations of the player who played the card in that position in the
    play sequence.
    Raises a subclass of PlaySequenceError if the play sequence is invalid.

    lead, hands, and trump are assumed to be valid. 
    play_sequence should be a space-separated string of cards, where each trick is listed in order,
    and within each trick, the original lead player's card is listed first,
    followed by the cards played by the other players, in clockwise order.
    That is, if someone other than the original lead won the previous trick, a given trick
    is listed in an order that is not the same as the order the cards actually played.
    
    A set of all of the cards played in any play sequence in the database is below

    {'', 'D9', 'ST', 'S2', 'D6', 'H8', 'H6', 'CJ', 'S5', 'C4', 'H2', 'D7', 'CK', 'SJ', 'PBN', 'DA', 'D8', '--', '^R', '%', 'HJ', 'H5',
    'C6', 'C9', 'D2', 'H9', 'SQ', 'D3', 'C2', '2.0', 'S8', 'C3', 'CQ', 'S3', 'CT', 'S4', 'SK', 'D5', 'D4', 'H7', '1.0', 'S6', 'HK',
    'DK', 'C8', 'S9', 'C7', 'C5', 'SA', 'HQ', 'HTHQ', 'H3', 'H4', 'DJ', '-', 'DQ', '!', 'S*', 'HA', 'HT', 'S7', 'DT', '?', 'CA'}

    Dashes in the play sequence are expected, and represent the scenario where a claim is made mid-trick. 
    The dashes fill out the trick so that it always contains 4 entries. "--" is sometimes also used, and should be read as "-".
    Only one bid, "HTHQ", is invalid but recognizable, and will be considered as "HT HQ".
    All other invalid plays will be assumed to be extraneous information, and will be ignored.
    """

    if not play_sequence or not lead or not trump:
        raise MissingPlaySequenceInfoError()
    
    hands = copy.deepcopy(hands) # Prevent the function from being destructive to the input variable

    # Normalize the recognizable bids.
    RECOGNIZABLE_BIDS:dict[str,str] = {"HTHQ":"HT HQ","--":"-"}
    for (bid,replacement) in RECOGNIZABLE_BIDS.items():
        play_sequence = play_sequence.replace(bid,replacement)

    plays:list[str] = play_sequence.split(" ")

    # Construct the list of valid plays
    valid_plays:list[str] = ["-"]
    for hand in hands:
        valid_plays+=hand

    # Remove any invalid plays from the play list
    for play in plays:
        if play not in valid_plays:
            plays.remove(play)

    if len(plays)%4!=0: # We expect the number of cards played, augmented with dashes if necessary, to be divisible by 4.
        raise UnbalancedPlaySequenceError()

    ordered_play_sequence:str = ""
    play_order_sequence:list[int] = [] # list of the integer representations of the player who played the card in that position in the play sequence.
    tricks_played:int = 0
    tricks_won_by_declarer:int = 0

    lead_player:int = ORDER.index(lead)
    declarer:int = (lead_player - 1)%4
    trick_leader: int = lead_player
    trick:list[str] = []
    ordered_trick:list[str] = []
    num_dashes:int = 0

    for pos,card in enumerate(plays):

        if num_dashes: # Dashes appeared in a previous trick. This is not permitted.
            raise MultipleClaimError()

        if card != "-": # Dashes are the only valid entry that is not a card.
            try:
                hands[(lead_player+pos)%4].remove(card) # trick_leader is updated every 4 cards
            except ValueError:
                raise PlayError()
        trick.append(card)

        if pos%4==3:
            ordered_trick = []
            for trick_pos in range(trick_leader-lead_player,(trick_leader-lead_player)+4):
                if trick[trick_pos%4] != "-": # We don't want dashes in the cleaned play sequence string
                    ordered_play_sequence+=trick[trick_pos%4] # trick is ordered starting from the original lead to each trick
                    play_order_sequence.append((lead_player + trick_pos)%4)
                ordered_trick.append(trick[trick_pos%4])

            num_dashes = validate_dashes(ordered_trick)
            
            if reneged(ordered_trick[:4-num_dashes],hands,trick_leader): # Send ordered_trick with dashes removed.
                raise RenegeError()
            
            if not num_dashes: # A trick winner is only determined for full tricks.
                trick_leader = determine_trick_winner(ordered_trick,trump,trick_leader) 
                if trick_leader in [declarer, (declarer+2)%4]:
                    tricks_won_by_declarer+=1
                tricks_played+=1
                
            trick = []

    return ordered_play_sequence,play_order_sequence,tricks_played,tricks_won_by_declarer

def compute_claim(result:str|int,number_of_tricks_played:int,number_of_declarer_tricks:int)->int:

    """
    Returns the result as claim.
    Expects number_of_tricks_played and number_of_declarer_tricks to be valid, i.e. >= 0.
    If result is not valid with respect to number_of_declarer_tricks and number_of_tricks_played 
    (as in, there is a contradicton), raise a subclass of BoardError.
    If result is not valid, -1 is returned.
    """

    try:
        result = int(result)
    except ValueError:
        return -1

    if result<0 or result>13:
        return -1

    if result < number_of_declarer_tricks or result-number_of_declarer_tricks > 13 - number_of_tricks_played:
        raise ClaimError()
    return result

def compute_year(event:str,date:str) -> int:

    """
    Computes the year the board was played in. If there is not enough information, 0 is retuned.
    event is the name of the event the board was played in. This often includes the year.
    date is the date the board was played in, if provided. 
    All date strings, if not one of "", "#", "?", are formatted as yyyy.mm.dd .
    It is known that no board from the database is after 2016, and no board is from before 1955.
    Some years in the database are clearly incorrect, appearing in the future.
    """

    START_YEAR: int = 1955
    END_YEAR: int = 2016

    for match in [re.match(r"^(\d{4})\.",date),re.match(r".*([1-2][0,9][0-2,5-9][0-9])",event)]: # Check date first
        # Expects date strings to be in the form "YYYY." followed by anything.
        # Looks for 4 digit numbers in the event name that looks like a valid year.
        if match:
            year = int(match.group(1))
            if year>=START_YEAR and year<=END_YEAR:
                return year
    return 0

def get_wbf_data() -> tuple[tuple[str,WbfInfo],...]:

    """
    Webscrapes the WBF ranking website and returns a tuple of tuples where the first element is the
    first and last name of the player from the rankings and the second element is a WbfInfo namedTuple
    with their information.
    The functionality of this function is dependent on the format of the wbf rankings webpage,
    and is not very robust to changes.
    """

    WBF_URL:str = "http://www.wbfmasterpoints.com/AllTimerankingOpen.asp"
    MAX_OFFSET:int = 10240
    RECORDS_PER_PAGE:int = 20

    name_to_wbf_name_components:dict[str,WbfInfo] = {}

    for offset in range(0,MAX_OFFSET,RECORDS_PER_PAGE):
        r = requests.get(WBF_URL+"?offset="+str(offset))
        soup = BeautifulSoup(r.content,'html5lib')
        rows = soup.findChildren("tr",{"class":["MainRows","deceased"]})
        for row in rows:
            entries = row.find_all('td') # Rank, code, first name, last name, country, masterpoints, placing points
            wbf_full_name:str = entries[2].text.strip()+" "+entries[3].text.strip()
            wbf_names:list[str] = []
            wbf_initials:list[str] = []
            mp:float = float(entries[5].text.strip())
            pp:float = float(entries[6].text.strip())

            for name_component in wbf_full_name.split(" "):
                if len(name_component)==2 and name_component[1]==".": # Initial
                    wbf_initials.append(name_component[0].upper())
                elif (name_component.startswith("(") and name_component.endswith(")")) or (name_component.startswith("'") and name_component.endswith("'")):
                    # Nickname
                    wbf_names.append(name_component[1:-1].upper())
                else:
                    wbf_names.append(name_component.upper()) # Regular names
            
            name_to_wbf_name_components[wbf_full_name] = WbfInfo(mp,pp,tuple(wbf_names),tuple(wbf_initials))

    return tuple(name_to_wbf_name_components.items())

@cache
def normalize_name(name:str,wbf_data:tuple[tuple[str,WbfInfo],...])->str:

    """
    Given a name, match it to the best name from wbf_data with their ranking info appended, like so: "name,mp,pp"
    To do so, we create a tuple (number of matching names, number of matching initials, negative number of unmatched names, negative number of unmatched initials)
    An initial can match another initial, or the first letter of an unmatched name.
    The best matching wbf name is the one with the largest lexicographically sorted tuple.
    Any match must have at least one matched name, otherwise there will be no match.
    If there is a tie, there is no match.
    If there is no match, ",-1,-1" is returned.
    """

    name_to_wbf_name_components:dict[str,WbfInfo] = dict(wbf_data)

    candidates:dict[str,tuple[int,int,int,int]] = {} # name -> (matched names,matched initials,unmatched names,unmatched initials)
    initials = []
    names = []
    for component in name.split(" "):
        if len(component)==2 and component[1]==".":
            initials.append(component[0].upper())
        else:
            names.append(component.upper())

    for (wbf_name,wbf_info) in name_to_wbf_name_components.items():
        name_with_points:str = wbf_name+","+str(wbf_info.mp)+","+str(wbf_info.pp)
        matched_names = (Counter(wbf_info.wbf_names)&Counter(names))
        matched_initials = (Counter(wbf_info.wbf_initials)&Counter(initials))
        number_of_matched_names: int = len(list(matched_names.elements()))
        number_of_matched_initials: int = len(list(matched_initials.elements()))

        available_initials = list((Counter(initials) - matched_initials).elements())
        for name in (Counter(wbf_info.wbf_names) - matched_names).elements():
            for initial in available_initials:
                if name.startswith(initial):
                    number_of_matched_initials += 1
                    matched_names[name]+=1
                    matched_initials[initial]+=1
                    available_initials.remove(initial)
                    break
        
        number_of_unmatched_names:int = -len(list((Counter(wbf_info.wbf_names) - matched_names).elements()))
        number_of_unmatched_initials:int = -len(list((Counter(wbf_info.wbf_initials) - matched_initials).elements()))
        # We take the negative of the number of unmatched elements as fewer indicates a better match, and we go on to take the max.

        candidates[name_with_points] = (number_of_matched_names,number_of_matched_initials,number_of_unmatched_names,number_of_unmatched_initials)

    no_match:str = ",-1,-1"

    best_match = max(candidates.values()) # The tuples will get sorted lexicographically
    if best_match[0] == 0:
        return no_match # Must match at least one name
    matching_names = [name for name in candidates.keys() if candidates[name]==best_match]
    if len(matching_names) != 1: # If there is still a tie, don't return a match
        return no_match
    return matching_names[0]

def get_vulnerable_players(vulnerable:str)->set[str]:

    """
    Normalizes vulnerable and returns a list of vulnerable players.
    """
    
    RECOGNIZABLE_VULNERABILITY:dict[str,str] = {"NZ":"NS","All]":"All"}
    for (vulnerable,replacement) in RECOGNIZABLE_VULNERABILITY.items():
        vulnerable = vulnerable.replace(vulnerable,replacement)

    vulnerable_players:set[str] = set()

    if vulnerable == "NS":
        vulnerable_players = set(["N","S"])
    elif vulnerable == "EW":
        vulnerable_players = set(["E","W"])
    elif vulnerable == "All":
        vulnerable_players = set(["N","E","S","W"])

    return vulnerable_players

def clean_board(event:str,date:str,northname:str,eastname:str,southname:str,westname:str,deal:str,vulnerable:str,dealer:str,bidstart:str,auction:str,contract:str,declarer:str,lead:str,play:str,result:str|int,wbf_data:tuple[tuple[str,WbfInfo],...]) -> Tuple[dict[str,Any],str,str]:
    
    """
    Cleans the board and returns a dictionary defining all aspects of it.
    Return is tuple, where the second and third elements are a string defining the problem with the auction or play, respectively,
    or "" if there was no error.
    All input values are assumed to only take on the possible values they take on in the database.
    If the board is invalid, a BoardError is raised.

    The keys of a valid board dictionary are:

    names: A list of the names of the players in the board, ordered north,east,south,west. Will match a wbf_data name, appended with ,<mp>,<pp>
    deal : The deal in PBN format as it was from the database
    bidstart : one of ["N","E","S","W",""], the player who started the bidding (not always and not necessarily the dealer)
    auction : A space-seperated string of valid bids, "" if invalid.
    contract : one of ["","P"] or lsd where l in [1-7], s in ["N","S","H","D","C"], d in ["","X","R"]
    declarer : one of ["N","E","S","W","P"], "P" if the contract was passed
    lead : one of ["N","E","S","W","P"], "P" if the contract was passed
    play : A space-seperated string of valid cards whose length is divisble by 4, potentially augmented with dashes, "" if invalid.
    play_order : list of the integer representations of the player who played the card in that position in the play sequence, [] if invalid.
    claim: -1 if no claim was made, otherwise equal to the number of tricks the declarer's side takes in total.
    NS_vulnerable : True if NS is vulnerable, False otherwise.
    EW_vulnerable : True if EW is vulnerable, False otherwise.
    year : 0 if undeterminable, otherwise the year the board was played in

    where no pieces of information contradict each other.
    """

    board: dict[str,Any] = {}

    if not northname and not eastname and not southname and not westname:
        raise MissingNamesError()

    board["names"] = []
    for name in [northname,eastname,southname,westname]:
        board["names"].append(normalize_name(name,wbf_data))

    player_hands:list[list[str]] = validate_deal(deal) # player_hands is used by validate_play, its computed here as validate_deal naturally almost did all of the mandatory work
    board["deal"] = deal

    if bidstart not in ORDER:
        bidstart = ""

    board["bidstart"] = bidstart or dealer # If they differ, choose bidstart. If only one is non-empty, return that one.
    # When they conflict, we trust bidstart. This is because having the dealer not be the one to start the biding does not change the game in any real way (unlike the first person in the auction winning pair to have bid the contract suit not being the declarer.).

    board["auction"] = ""
    # It is always the case, in our data, that if neither dealer or bidstart is listed, the auction is also not listed.
    # It would be possible, given the declarer, or information to deduce the declarer, 
    # to find the person who started the bidding from the auction. 
    # But, as that implementation would get no use here, it is left out, and the auction is set to empty if the bidstart is empty.

    auction_error:str = ""
    if board["bidstart"]:
        try:
            board["auction"] = validate_auction(auction)
        except AuctionError as exc:
            auction_error = str(exc)

    try:
        board["contract"] = ensure_non_contradiction(normalize_contract(contract), find_contract_from_auction(board["auction"]))
    except ContradictionError:
        raise ContractContradictionError()
    
    if declarer not in ORDER:
        declarer = ""

    try:
        board["declarer"] = ensure_non_contradiction(declarer, find_declarer_from_auction(board["auction"],board["bidstart"]) or "P")
    except ContradictionError:
        raise DeclarerContradictionError()
    try:
        board["lead"] = ensure_non_contradiction(lead,find_lead_from_declarer(board["declarer"]))
    except ContradictionError:
        raise LeadContradictionError()

    number_of_declarer_tricks:int = -1
    number_of_tricks_played:int = -1
    play_error:str = ""
    board["play"] = ""
    board["play_order"] = []
    if board["contract"]!="P":
        try:
            board["play"],board["play_order"],number_of_tricks_played,number_of_declarer_tricks = validate_play(play,lead,player_hands,board["contract"][1])
        except PlaySequenceError as exc:
            play_error = str(exc)
    elif play:
        raise PassContradictionError()

    if not play_error and len(board["play"])!=104 and board["contract"]!="P":
        board["claim"] = compute_claim(result,number_of_tricks_played,number_of_declarer_tricks)
        # Claim is recorded as the total number of tricks won by the declarer, for incomplete, but not empty, play seqeunces.
    else:
        board["claim"] = -1

    RECOGNIZABLE_VULNERABILITY:dict[str,str] = {"All]":"All","NZ":"NS"}

    vulnerability:str = RECOGNIZABLE_VULNERABILITY.get(vulnerable,vulnerable)

    board["NS_vulnerable"] = False
    board["EW_vulnerable"] = False

    if vulnerability=="NS" or vulnerability=="All":
        board["NS_vulnerable"] = True
    if vulnerability=="EW" or vulnerability=="All":
        board["EW_vulnerable"] = True
    
    board["year"] = compute_year(event,date)

    return board,auction_error,play_error