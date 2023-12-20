"""This module leverages Bo Haglund's Double Dummy Solver DLL."""

from ctypes import c_long, pointer
from functools import cache
from dll_wrapper import *
from typing import Any
from defs import Player,SUITS,ORDER,ORDERED_CONTRACT_BIDS
from data_cleaning import find_declarer_from_auction

dds:CDLL = create_dds() # Put the path to the DDS DLL here

def perform_dds_analysis(boards:list[dict[str,Any]])->dict[str,Player]:

    """
    Takes as input a list of boards which are expected to be clean, i.e. returned by get_clean_boards.
    Returns a dictionary mapping the names of players to Player objects which contains the variable values.     
    """

    player_to_object:dict[str,Player] = {}
     
    analyse_play_trace_chunk:list[dict[str,Any]] = []
    deal_PBNs:list[dealPBN] = []
    play_trace_PBNs:list[playTracePBN] = []

    analyse_auction_chunk:list[dict[str,Any]] = []
    dd_table_deal_PBNs:list[ddTableDealPBN] = []

    for board in boards:

        for player in board["names"]:
            if player not in player_to_object:
                player_to_object[player] = Player(player)

        if board["play"] and board["contract"]:  
            # Only analyze the play trace when both the play trace and the contract are known (declarer, lead are always known)

            analyse_play_trace_chunk.append(board) 
            deal_PBNs.append(create_deal_PBN(board))
            play_trace_PBNs.append(create_play_trace_PBN(board))

        if board["auction"] and board["bidstart"]: # Only analyze the auction when auction is known (if auction and bidstart are known, so is contract) 

            analyse_auction_chunk.append(board)
            dd_table_deal_PBNs.append(create_dd_table_deal_PBN(board))

        if len(analyse_play_trace_chunk)==20: # DDS can solve up to 20 play traces at once
            
            analyse_plays(deal_PBNs,play_trace_PBNs,analyse_play_trace_chunk,player_to_object)
            analyse_play_trace_chunk = []
            deal_PBNs = []
            play_trace_PBNs = []

        if len(analyse_auction_chunk)==32: # DDS can solve up to 32 hands at once

            analyse_auctions(dd_table_deal_PBNs,analyse_auction_chunk,player_to_object)
            analyse_auction_chunk = []
            dd_table_deal_PBNs = []

    # Now we analyze the remaining play traces and hands if necessary
            
    if len(analyse_play_trace_chunk)!=0:
        analyse_plays(deal_PBNs,play_trace_PBNs,analyse_play_trace_chunk,player_to_object)

    if len(analyse_auction_chunk)!=0:
        analyse_auctions(dd_table_deal_PBNs,analyse_auction_chunk,player_to_object)

    return player_to_object

def analyse_auctions(dd_table_deal_PBNs:list[ddTableDealPBN],chunk:list[dict[str,Any]],player_to_object:dict[str,Player]):

    """
    Call the CalcAllTablesPBN function from the DDS DLL, use the results to analyze the auction.
    Updates player_to_object with auction mistakes.
    """
    
    dd_table_deals_PBN = ddTableDealsPBN()
    dd_table_deals_PBN.noOfTables = len(chunk)
    dd_table_deals_PBN.deals=tuple(dd_table_deal_PBNs)

    mode:int = -1 # We do not wish to use the par calculations
    LongArray5 = (c_long * 5)
    trump_filter = LongArray5(False,False,False,False,False)
    dd_tables_res = ddTablesRes()
    all_par_results = allParResults()

    dds.CalcAllTablesPBN(pointer(dd_table_deals_PBN),mode,trump_filter,pointer(dd_tables_res),pointer(all_par_results))

    for board_num in range(len(chunk)):
        # dd_tables_res.noOfBoards seems to return the total number of resTable entries and not
        # the number of boards, DDS bug? Using len(chunk) instead as we control this value

        board:dict[str,Any] = chunk[board_num]

        for name in board["names"]:
            player_to_object[name].auctions_analyzed+=1

        if board["contract"]=="P":
            assign_passed_auction_mistakes(board,dd_tables_res.results[board_num].resTable,player_to_object)
        else:
            assign_defender_auction_mistakes(board,dd_tables_res.results[board_num].resTable,player_to_object)
            assign_declarer_auction_mistakes(board,dd_tables_res.results[board_num].resTable,player_to_object)

def assign_passed_auction_mistakes(board:dict[str,Any],res_table,player_to_object:dict[str,Player]):

    """
    Given a board that was passed, updates player_to_object with every player's passed mistakes.
    """

    # check all makeable contracts for each side. The highest positive score is the magnitude of the mistake. If no positive score, no mistake.

    for side,vulnerabiltiy in zip([(0,2),(1,3)],["NS_vulnerable","EW_vulnerable"]):
        best_higher_contract_score:int = 0
        for contract in ORDERED_CONTRACT_BIDS:
            for declarer_index in side:
                higher_contract_score = compute_score(contract,res_table[SUITS.index(contract[1])][declarer_index],board[vulnerabiltiy],board["year"])
                if higher_contract_score > best_higher_contract_score:
                    best_higher_contract_score = higher_contract_score

        if best_higher_contract_score:
            for player_index in side:
                player_to_object[board["names"][player_index]].passed_higher_contract+=1
                player_to_object[board["names"][player_index]].weighted_passed_higher_contract+=best_higher_contract_score

def assign_declarer_auction_mistakes(board:dict[str,Any],res_table,player_to_object:dict[str,Player]):

    """Updates player_to_object with the declarer's auction mistakes"""
    
    mistake_candidates:list[tuple[int,list[tuple[str,int]]]] = [] 
    # The first element of each tuple in the list is an integer to sort the tuples by, equal to the magnitude of the mistake.
    # The second element is a list of tuples pairing the string name of the attribute to be incremented, and the quantity to increment
    # it by.

    declarer_index:int = ORDER.index(board["declarer"])
    defender_indexes:list[int] = [(declarer_index+1)%4,(declarer_index+3)%4]
    declaring_side_indexes:list[int] = [declarer_index,(declarer_index+2)%4]

    declarer_vulnerability:str = "NS_vulnerable"
    defender_vulnerability:str = "EW_vulnerable"
    if declarer_index in (1,3):
        declarer_vulnerability = "EW_vulnerable"
        defender_vulnerability = "NS_vulnerable"

    double = ""
    try:
        double = board["contract"][2]
    except IndexError:
        pass

    current_tricks:int = res_table[SUITS.index(board["contract"][1])][declarer_index]
    current_score:int = compute_score(board["contract"],current_tricks,board[declarer_vulnerability],board["year"])

    defenders_last_bid,defenders_redoubled_last_bid = get_defenders_last_bid(board,defender_indexes)

    available_contract_index:int = 0
    if defenders_last_bid:
        available_contract_index = ORDERED_CONTRACT_BIDS.index(defenders_last_bid)+1


    # consider all available contracts
    declarer_candidates:dict[str,set[int]] = determine_declarer_candidates(board["auction"],ORDER.index(board["bidstart"]))
    best_higher_contract_score:int = -7600
    for contract in ORDERED_CONTRACT_BIDS[available_contract_index:]:
        for declarer_candidate in declarer_candidates[contract[1]] & set([declarer_index,(declarer_index+2)%4]):
            will_make:int = res_table[SUITS.index(contract[1])][declarer_candidate]

            # If the declarers could not have made this contract, they assume their opponents will double it
            higher_contract_score:int = compute_score(contract+"X" if will_make<int(contract[0])+6 else contract,will_make,board[declarer_vulnerability],board["year"])
            if higher_contract_score > best_higher_contract_score: # compute_score is from the declarers point of view
                best_higher_contract_score = higher_contract_score

    if best_higher_contract_score > current_score:
        mistake_candidates.append((best_higher_contract_score - current_score,[("declarer_missed_higher_contract",1),("weighted_declarer_missed_higher_contract",best_higher_contract_score - current_score)]))


    auction_cutoff_since_defenders_last_bid:int = 0

    if defenders_last_bid:

        auction_cutoff_since_defenders_last_bid = board["auction"].split(" ").index(defenders_last_bid)+1

        # player who WOULD HAVE been the declarer in the defenders last contract
        declarer_from_defenders_last_bid = ORDER.index(find_declarer_from_auction(" ".join(board["auction"].split(" ")[:board["auction"].split(" ").index(defenders_last_bid)+1]),board["bidstart"]))

        defenders_last_bid_doubled_score = compute_score(defenders_last_bid+"X",res_table[SUITS.index(defenders_last_bid[1])][declarer_from_defenders_last_bid],board[defender_vulnerability],board["year"])
        if defenders_last_bid_doubled_score < -current_score:
            mistake_candidates.append((-current_score-defenders_last_bid_doubled_score,[("declarer_missed_doubling_opponents_last_bid",1),("weighted_declarer_missed_doubling_opponents_last_bid",-current_score-defenders_last_bid_doubled_score)]))

        defenders_last_bid_score = compute_score(defenders_last_bid,res_table[SUITS.index(defenders_last_bid[1])][declarer_from_defenders_last_bid],board[defender_vulnerability],board["year"])
        if defenders_last_bid_score < -current_score:
            mistake_candidates.append((-current_score - defenders_last_bid_score,[("declarer_missed_opponents_last_bid",1),("weighted_declarer_missed_opponents_last_bid",-current_score - defenders_last_bid_score,)]))

        if defenders_redoubled_last_bid:
            defenders_last_bid_redoubled_score:int = compute_score(defenders_last_bid+"R",res_table[SUITS.index(defenders_last_bid[1])][declarer_from_defenders_last_bid],board[defender_vulnerability],board["year"])
            if defenders_last_bid_redoubled_score < -current_score:
                mistake_candidates.append((-current_score - defenders_last_bid_redoubled_score,[("declarer_missed_opponents_last_redouble",1),("weighted_declarer_missed_opponents_last_redouble",-current_score - defenders_last_bid_redoubled_score)])) 


    if double=="R":
        current_contract_doubled_score:int = compute_score(board["contract"][:2]+"X",current_tricks,board[declarer_vulnerability],board["year"])
        if current_contract_doubled_score > current_score:
            mistake_candidates.append((current_contract_doubled_score - current_score,[("declarer_erroneous_redouble",1),("weighted_declarer_erroneous_redouble",current_contract_doubled_score - current_score)]))

    doubled_bids:list[tuple[str,int]] = get_declarers_past_doubled_bids(board,auction_cutoff_since_defenders_last_bid) # Bid, declarer

    highest_past_redouble_score = -7600
    for contract,declarer in doubled_bids:
        past_redouble_score:int = compute_score(contract+"R",res_table[SUITS.index(contract[1])][declarer],board[declarer_vulnerability],board["year"])
        if past_redouble_score > highest_past_redouble_score:
            highest_past_redouble_score = past_redouble_score

    if highest_past_redouble_score > current_score:
        mistake_candidates.append((past_redouble_score - current_score,[("declarer_missed_redoubling_opponents_erroneous_double",1),("weighted_declarer_missed_redoubling_opponents_erroneous_double",past_redouble_score-current_score)]))

    assign_mistakes(board,mistake_candidates,player_to_object,declaring_side_indexes)

def get_declarers_past_doubled_bids(board:dict[str,Any],auction_cutoff:int)->list[tuple[str,int]]:

    """
    Return a list of tuples of previous declarer bid that was doubled that occured after the defenders last bid,
    and the integer representation of the player who would have been the declarer had that bid become the contract.
    """

    doubled_bids:list[tuple[str,int]] = []
    current_bid_doubled:bool = False
    for bid in reversed(board["auction"].split(" ")[auction_cutoff:]):
        if bid=="X":
            current_bid_doubled = True
        if bid in ORDERED_CONTRACT_BIDS and current_bid_doubled:
            doubled_bids.append((bid,ORDER.index(find_declarer_from_auction(" ".join(board["auction"].split(" ")[:board["auction"].split(" ").index(bid)+1]),board["bidstart"]))))
            current_bid_doubled = False

    return doubled_bids

def get_defenders_last_bid(board:dict[str,Any],defender_indexes:list[int])->tuple[str,bool]:

    """
    Given a board and a list of indexes of the defenders positions, returns a tuple of the defenders last contract bid, 
    and whether or not their last contract bid was redoubled by them.
    """

    defenders_last_bid:str = ""
    defenders_redoubled_last_bid:bool = False
    bidder_index = (ORDER.index(board["bidstart"]) + len(board["auction"].split(" "))-1) %4 # last bidder
    for bid in reversed(board["auction"].split(" ")):
        if bid == "R":
            defenders_redoubled_last_bid = True
        if bid in ORDERED_CONTRACT_BIDS and bidder_index not in defender_indexes:
            defenders_redoubled_last_bid = False
        if bid in ORDERED_CONTRACT_BIDS and bidder_index in defender_indexes:
            defenders_last_bid = bid
            break
        bidder_index = (bidder_index-1)%4

    return defenders_last_bid,defenders_redoubled_last_bid


def assign_defender_auction_mistakes(board:dict[str,Any],res_table,player_to_object:dict[str,Player]):

    """
    Updates player_to_object with the defender's auction mistakes.
    """

    mistake_candidates:list[tuple[int,list[tuple[str,int]]]] = [] 
    # The first element of each tuple in the list is an integer to sort the tuples by, equal to the magnitude of the mistake.
    # The second element is a list of tuples pairing the string name of the attribute to be incremented, and the quantity to increment
    # it by.

    declarer_index:int = ORDER.index(board["declarer"])
    defender_indexes:list[int] = [(declarer_index+1)%4,(declarer_index+3)%4]

    declarer_vulnerability:str = "NS_vulnerable"
    defender_vulnerability:str = "EW_vulnerable"
    if declarer_index in (1,3):
        declarer_vulnerability = "EW_vulnerable"
        defender_vulnerability = "NS_vulnerable"
    
    current_tricks:int = res_table[SUITS.index(board["contract"][1])][declarer_index]
    current_score:int = compute_score(board["contract"],current_tricks,board[declarer_vulnerability],board["year"])

    double = ""
    try:
        double = board["contract"][2]
    except IndexError:
        pass

    if not double: # They didnt double, should they have?
        doubled_score = compute_score(board["contract"]+"X",current_tricks,board[declarer_vulnerability],board["year"])
        if doubled_score < current_score: # both scores are from the declarers point of view, defenders want it low
            mistake_candidates.append((current_score - doubled_score,[("defender_missed_current_double",1),("weighted_defender_missed_current_double",current_score - doubled_score)]))

    if double: # They doubled, should they have?
        undoubled_score = compute_score(board["contract"][:2],current_tricks,board[declarer_vulnerability],board["year"])
        if undoubled_score < current_score:
            mistake_candidates.append((current_score - undoubled_score,[("defender_erroneously_doubled",1),("weighted_defender_erroneously_doubled",current_score - undoubled_score)]))

    # consider all available contracts
    declarer_candidates:dict[str,set[int]] = determine_declarer_candidates(board["auction"],ORDER.index(board["bidstart"]))
    best_higher_contract_score:int = -7600 # lowest possible score
    for contract in ORDERED_CONTRACT_BIDS[ORDERED_CONTRACT_BIDS.index(board["contract"][:2])+1:]:
        for declarer_candidate in declarer_candidates[contract[1]] & set(defender_indexes): # Those who can be declarers and are defenders
            will_make:int = res_table[SUITS.index(contract[1])][declarer_candidate]

            # If the defenders would not have made this new contract, they assume the opponents will double it
            higher_contract_score:int = compute_score(contract+"X" if will_make<int(contract[0])+6 else contract,will_make,board[defender_vulnerability],board["year"])
            if higher_contract_score > best_higher_contract_score:
                best_higher_contract_score = higher_contract_score

    if best_higher_contract_score > -current_score: # current_score was calculated from the original declarers point of view.
        mistake_candidates.append((best_higher_contract_score - (-current_score),[("defender_missed_higher_contract",1),("weighted_defender_missed_higher_contract",best_higher_contract_score - (-current_score))]))

    assign_mistakes(board,mistake_candidates,player_to_object,defender_indexes)

def assign_mistakes(board:dict[str,Any],mistake_candidates,player_to_object:dict[str,Player],players:list[int]):

    """
    Assigns the mistakes to the players defined by players in board to player_to_object, given mistake_candidates.
    """

    mistake_magnitude:int = 0
    try:
        mistake_magnitude = max(mistake_candidates,key=lambda mistake_candidate: mistake_candidate[0])[0]
        # Finds the magnitude of the largest mistake that was made.
    except ValueError:
        pass

    mistakes:list[list[tuple[str,int]]] = [mistake_candidate[1] for mistake_candidate in mistake_candidates if mistake_candidate[0]==mistake_magnitude]
    # Finds all mistakes that have magnitude equal to the largest magnitude.

    for player_pos in players:
        for attributes_to_update in mistakes:
            for attribute_to_update in attributes_to_update:
                setattr(player_to_object[board["names"][player_pos]],attribute_to_update[0],getattr(player_to_object[board["names"][player_pos]],attribute_to_update[0])+(attribute_to_update[1]/len(mistakes)))
                # If more than one mistake had magnitude equal to the largest magnitude, each attribute is incremented by the original value
                # divided by the number of simultaneous mistakes.

@cache
def determine_declarer_candidates(auction:str,bidstart_index:int)->dict[str,set[int]]:

    """
    Returns a dictionary mapping the string representation of each suit to a set of the integer representations of the players 
    who may still be a declarer in the given suit, given the auction and integer representation of bidstart.
    A player may still be a declarer for a suit if their partner was not the first of their partnership to bid that suit.
    """

    suit_to_declarer_candidates:dict[str,set[int]] = {"S":{0,1,2,3},"H":{0,1,2,3},"C":{0,1,2,3},"D":{0,1,2,3},"N":{0,1,2,3}}

    bidder_index = bidstart_index
    for bid in auction.split(" "):
        if bid in ORDERED_CONTRACT_BIDS and bidder_index in suit_to_declarer_candidates[bid[1]] and (bidder_index+2)%4 in suit_to_declarer_candidates[bid[1]]:
            suit_to_declarer_candidates[bid[1]].remove((bidder_index+2)%4)
        bidder_index = (bidder_index+1)%4

    return suit_to_declarer_candidates

def create_dd_table_deal_PBN(board:dict[str,Any])->ddTableDealPBN:

    dd_table_deal_PBN = ddTableDealPBN()
    dd_table_deal_PBN.cards = board["deal"].encode("utf-8")

    return dd_table_deal_PBN

def analyse_plays(deal_PBNs,play_trace_PBNs,chunk:list[dict[str,Any]],player_to_object:dict[str,Player]):

    """
    Calls the AnalyseAllPlaysPBN DDS function and computes the scores of the double dummy values before and after each card played.
    Computes mistakes and updates player_to_object.
    """

    solved_plays = solvedPlays()
    boards_PBN = boardsPBN() 
    boards_PBN.noOfBoards = len(chunk)
    boards_PBN.target = tuple([-1 for _ in range(len(chunk))])
    boards_PBN.solutions = tuple([1 for _ in range(len(chunk))])
    boards_PBN.mode = tuple([0 for _ in range(len(chunk))])
    boards_PBN.dealPBN = tuple(deal_PBNs)

    play_traces_PBN = playTracesPBN()
    play_traces_PBN.noOfBoards = len(chunk)
    play_traces_PBN.plays = tuple(play_trace_PBNs)

    dds.AnalyseAllPlaysPBN(pointer(boards_PBN),pointer(play_traces_PBN),pointer(solved_plays),1)

    for board_num in range(solved_plays.noOfBoards):

        previous_dds_value:int = -1
        player_index:int = -1

        board:dict[str,Any] = chunk[board_num]
        declarer_index:int = ORDER.index(board["declarer"])
        declarer_pos:list[int] = [declarer_index,(declarer_index+2)%4] # Identifies the declarer's and dummy's position
        declarer:Player = player_to_object[board["names"][declarer_index]]

        declarer_vulnerability:str = "NS_vulnerable"
        if declarer_index in (1,3):
            declarer_vulnerability = "EW_vulnerable"

        for pos in range(solved_plays.solved[board_num].number):

            dds_value = solved_plays.solved[board_num].tricks[pos]

            if not pos: # First dds_value is the number of tricks before any cards are played.
                previous_dds_value = dds_value
                continue

            player_index = board["play_order"][pos-1]

            previous_declarer_score:int = -1
            new_declarer_score:int = previous_declarer_score
            if dds_value!=previous_dds_value:
                previous_declarer_score = compute_score(board["contract"],previous_dds_value,board[declarer_vulnerability],board["year"])
                new_declarer_score = compute_score(board["contract"],dds_value,board[declarer_vulnerability],board["year"])

            if player_index in declarer_pos: 
                # declarer is responsible for mistakes from dummy's position.
                declarer.cards_played_as_declarer+=1

                if dds_value<previous_dds_value:
                    declarer.play_mistakes_as_declarer+=1
                    declarer.weighted_play_mistakes_as_declarer+= previous_declarer_score - new_declarer_score

            if player_index not in declarer_pos: # Defender

                player:Player = player_to_object[board["names"][player_index]]

                if pos==1: # lead
                    player.leads+=1

                    if dds_value>previous_dds_value:
                        player.lead_mistakes+=1
                        player.weighted_lead_mistakes+= new_declarer_score - previous_declarer_score

                else:
                    player.cards_played_as_defender+=1

                    if dds_value>previous_dds_value:
                        player.play_mistakes_as_defender+=1
                        player.weighted_play_mistakes_as_defender+= new_declarer_score - previous_declarer_score

            previous_dds_value = dds_value

        if board["claim"]!=-1: # There was a claim

            if dds_value!=board["claim"]:
                previous_declarer_score = compute_score(board["contract"],dds_value,board[declarer_vulnerability],board["year"])
                new_declarer_score = compute_score(board["contract"],board["claim"],board[declarer_vulnerability],board["year"])

            for player_name in board["names"]:
                player_to_object[player_name].claims+=1

            if dds_value<board["claim"]: # claim favoured declarers
                for player_pos in [(declarer_index+1)%4,(declarer_index+3)%4]: # Identifies defender's positions
                    player_to_object[board["names"][player_pos]].claim_mistakes+=1
                    player_to_object[board["names"][player_pos]].weighted_claim_mistakes+= new_declarer_score - previous_declarer_score

            if dds_value>board["claim"]: # claim favoured defenders
                # TODO: Should the dummy be penalized for a claim mistake?
                declarer.claim_mistakes+=1
                declarer.weighted_claim_mistakes+= previous_declarer_score - new_declarer_score

def create_deal_PBN(board:dict[str,Any]):

    deal_PBN = dealPBN()
    deal_PBN.trump = SUITS.index(board["contract"][1])
    deal_PBN.first = ORDER.index(board["lead"])
    deal_PBN.currentTrickSuit = tuple([0 for _ in range(3)])
    deal_PBN.currentTrickRank = tuple([0 for _ in range(3)])
    deal_PBN.remainCards = board["deal"].encode("utf-8")

    return deal_PBN

def create_play_trace_PBN(board:dict[str,Any]):

    play_trace_PBN = playTracePBN()
    play_trace_PBN.number = len(board["play"])//2
    play_trace_PBN.cards = board["play"].encode("utf-8")

    return play_trace_PBN

def compute_undertrick_points(undertricks:int,double:str,declarer_vulnerable:bool,year:int)->int:

    multiplier:int = 1
    if double=="R":
        multiplier = 2
    
    if not declarer_vulnerable:
        if not double:
            return (-50) * undertricks

        if year and year <= 1987: # The undertrick point rules were different prior to and in 1987
            return (-100*multiplier) - ( (200*multiplier) * (undertricks - 1))
        else:
            return (-100*multiplier) - ( (200*multiplier) * (min(2,int(undertricks//1.5))) ) - ( (300*multiplier) * (max(undertricks-3,0)) )
            
    else: # declarer is vulnerable
        if not double:
            return (-100) * undertricks

        return (-200*multiplier) - ( (300*multiplier) * (undertricks-1) )
    
def compute_contract_points(level:int,trump:str,double:str)->int:
    
    multiplier = 1
    if double=="X":
        multiplier = 2
    if double=="R":
        multiplier = 4
    
    if trump in ["C","D"]:
        return (20*level)*multiplier
    elif trump in ["S","H"]:
        return (30*level)*multiplier
    else: # No trump
        return ((30*level)*multiplier) + (10*multiplier)
    
def compute_bonus_points(level,will_make,contract_points,double,declarer_vulnerable)->int:
    
    bonus:int = 0

    multiplier:float = 1
    if declarer_vulnerable:
        multiplier = 1.5
    
    if contract_points and contract_points < 100: 
        bonus += 50 # partial game bonus

    if contract_points >= 100: # game bonus
        if not declarer_vulnerable:
            bonus+=300
        else:
            bonus+=500

    if level == 6 and will_make>=12:
        bonus += int(500*multiplier) # slam bonus
    if level == 7 and will_make==13:
        bonus += int(1000*multiplier) # grand slam bonus
    
    # for insult if made
    if contract_points and double=="X":
        bonus+=50
    if contract_points and double=="R":
        bonus+=100
    
    return bonus

def compute_overtrick_points(overtricks:int,trump:str,double:str,declarer_vulnerable:bool)->int:

    if not double:
        if trump in ["C","D"]:
            return overtricks*20
        if trump in ["S","H","N"]:
            return overtricks*30
        
    multiplier = 1
    if declarer_vulnerable:
        multiplier = 2
    if double=="R":
        multiplier*=2
    
    return overtricks*100*multiplier

def compute_score(contract:str,will_make:int,declarer_vulnerable:bool,year:int) -> int:
    """
    Computes the score that will be earned by the declarer should they make will_make tricks in the given contract and declarer_vulnerable.
    Excpects a valid contract.
    """

    level:int = int(contract[0])
    trump:str = contract[1]
    double:str = ""
    try:
        double = contract[2]
    except IndexError:
        pass

    if will_make < level+6: # contract defeated

        return compute_undertrick_points((level+6) - will_make, double, declarer_vulnerable,year)
                
    score:int = compute_contract_points(level,trump,double)

    score += compute_bonus_points(level,will_make,score,double,declarer_vulnerable)

    score += compute_overtrick_points(will_make - (level+6),trump,double,declarer_vulnerable)
    
    return score