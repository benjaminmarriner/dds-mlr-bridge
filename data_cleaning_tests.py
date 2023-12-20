"""Unit tests for the data_cleaning module."""

from typing import Callable
import pytest
from data_cleaning import *

def assert_correct_output(input_to_expected_output:list[Tuple[Any,Any]],function:Callable) -> None:

    """
    Asserts that, when given the first element of a input_to_expected_output tuple, the input function returns the second for 
    each tuple in the list. The first element in every tuple must itself be an iterable of function parameters.
    """

    for (input,expected_output) in input_to_expected_output:
        assert function(*input) == expected_output

def assert_correct_exception(input_to_expected_exception:list[Tuple[Any,type[Exception]]],function:Callable) -> None:

    """
    Asserts that, when given the first element of a input_to_expected_output tuple, the input function raises the specified exception
    for each tuple in the list. The first element in every tuple must itself be an iterable of function parameters.
    """

    for (input,expected_exception) in input_to_expected_exception:
        with pytest.raises(expected_exception):
            function(*input)

def test_validate_deal() -> None:
    assert_correct_output([
        (("N:AK75.54.987653.A Q.AT983.42.JT753 642.KQJ7.AQJ.962 JT983.62.KT.KQ84",),[ # A valid deal
            ["SA","SK","S7","S5","H5","H4","D9","D8","D7","D6","D5","D3","CA"],
            ["SQ","HA","HT","H9","H8","H3","D4","D2","CJ","CT","C7","C5","C3"],
            ["S6","S4","S2","HK","HQ","HJ","H7","DA","DQ","DJ","C9","C6","C2"],
            ["SJ","ST","S9","S8","S3","H6","H2","DK","DT","CK","CQ","C8","C4"],
        ]),
    ],validate_deal)

    assert_correct_exception([
        (("",),MissingDealError),
        (("N:AK75.54.987653. Q.AT983.42.AJT753 642.KQJ7.AQJ.962 JT983.62.KT.KQ84",),UnbalancedDealError), # One hand with 12 cards, one with 14
        (("N:AK75.54.987653.L Q.AT983.42.JT753 642.KQJ7.AQJ.962 JT983.62.KT.KQ84",),CardError), # Invalid card "L" of clubs for North
        (("N:AK75.542.987653. Q.AT983.42.JT753 642.KQJ7.AQJ.962 JT983.62.KT.KQ84",),CardError), # 2 of hearts held by north and east, nobody has ace of clubs
    ],validate_deal)

def test_get_cleaned_bids() -> None:
    assert_correct_output([
        (("P 1C 2H 3s 4D X xX 7N p P P",),["P","1C","2H","3S","4D","X","R","7N","P","P","P"]), # All valid bids, differing case
        (("1C! =0=6NT =0=7N =0=X XX! P! P P",),["1C","6N","7N","X","R","P","P","P"]), # Valid (or NT) bids with leading =0= or trailing !
        (("PASS PAS S3 DBL REDBL 4NT XXX AP",),["P","P","3S","X","R","4N","X","R","P","P","P"]), # Normalizable bids
        (("1NTPASS P XPASS 2H2NT X XXPASS PASS5S XXX 7NT",),["1N","P","P","X","P","2H","2N","X","R","P","P","5S","X","R","7N"]), # Concatenations
        (("1NT! =6= ?? !! =:= P =9= 34 Pc P ! 1.0 $1 % P",),["1N","P","P","P"]), # Illegal bids
        (("",),[]),
    ],get_cleaned_bids)

def test_validate_auction() -> None:
    assert_correct_output([
        (("P P P 1N X R 2N P P P",),"P P P 1N X R 2N P P P"), # Valid auction
    ],validate_auction)

    assert_correct_exception([
        (("1C 2S 3H P P P 4H 5C P P P",),PassError), # Passes out in the middle of the auction
        (("P P P 6H 7N P P",),PassError), # Does not end in 3 passes
        (("1C 2S 2H P P P",),ContractBidError), # Decreasing contract bid suit
        (("1C 2H 1S P P P",),ContractBidError), # Decreasing contract bid level
        (("4H P P 4H X R P P P",),ContractBidError), # Repeated contract bid
        (("P P X 1C 7N P P P",),DoubleBidError), # Double with no contract
        (("P P P R 1C 7N P P P",),RedoubleBidError), # Redouble with no contract
        (("1C P X P P P",),DoubleBidError), # Double out of position
        (("3N X P R P P P",),RedoubleBidError), # Redouble out of position
        (("7C X P X P P P",),DoubleBidError), # Doubled twice
        (("7C X R X P P P",),DoubleBidError), # Doubled after redouble
        (("7C X R P R P P P",),RedoubleBidError), # Redoubled twice
        (("7C P R P P P",),RedoubleBidError), # Redoubled without double
        (("",),MissingAuctionError),
    ],validate_auction) 

def test_ensure_non_contradiction() -> None:
    assert_correct_output([
        (("0","0"),"0"), # Both nonempty, the same
        (("",""),""), # Both empty
        (("0",""),"0"), # Value2 empty
        (("","0"),"0"), # Value1 empty
    ],ensure_non_contradiction)

    assert_correct_exception([
        (("0","1"),ContradictionError)
    ],ensure_non_contradiction)

def test_normalized_contract()->None:
    assert_correct_output([
        (("Pass",),"P"),
        (("1NT",),"1N"),
        (("5CXX",),"5CR"),
        (("3D",),"3D"),
        (("3SX",),"3SX"),
        (("7NTXX",),"7NR")
    ],normalize_contract)

def test_find_contract_from_auction()->None:
    assert_correct_output([
        (("P P P 1C P 2S X R P 7N",),"7N"), # Undoubled
        (("P 4N X P P 5H X P P P",),"5HX"), # Doubled
        (("2C 3D P P X R P P P",),"3DR"), # Redoubled
        (("P P P P",),"P") # Passed out
    ],find_contract_from_auction)

def test_find_declarer_from_auction()->None:
    assert_correct_output([
        (("1C 2C 3C 4C 5S 7C P P P","E"),"S"), # Everyone bid the eventual trump suit, first bidder (S) was also last bidder
        (("P P 2D 3C 4H X 5H P P P","N"),"N"), # Only winning side bid the eventual trump suit, first bidder (N) was not last bidder (S)
        (("1C X R P P P","W"),"W"), # Only one bid
        (("P P P P","E"),"")
    ],find_declarer_from_auction)

def test_find_lead_from_declarer()->None:
    assert_correct_output([
        (("N",),"E"),
        (("E",),"S"),
        (("S",),"W"),
        (("W",),"N")
    ],find_lead_from_declarer)

def test_determine_trick_winner()->None:
    assert_correct_output([
        ((["DA","D3","D2","C2"],"C",0),3), # Trump suit played, not as lead
        ((["DA","D3","D2","C2"],"S",2),2), # No trump played, lead is winner
        ((["C2","C5","CA","CK"],"D",0),2), # No trump played, lead isnt winner
        ((["S3","S5","C3","CA"],"S",1),2), # Trump played as lead, lead isnt winner
        ((["SK","SQ","ST","DT"],"S",1),1), # Trump played as lead, lead is winner
        ((["DJ","DK","D2","DQ"],"D",3),0), # All trump played
    ],determine_trick_winner)

def test_reneged()->None:
    assert_correct_output([
        ((["C3","D4","S4","H4"],[["C5","D2","S9","HT"],["D5","S7","HA","D3"],["H2","HK","HQ","HJ"],["S2","DA","DK","DQ"]],0),False), # No reneging, lead suit not played again
        ((["SA","D2","DQ","SJ"],[["H2","DK"],["S4","DT"],["ST","DA"],["C2","C3"]],2),False), # No reneging, led suit played
        ((["SK","DK","S3","CT"],[["DQ","DA"],["D2","D3"],["S2","CA"],["CQ","CJ"]],1),True), # South reneged
        ((["DA","D2"],[["C2","C3"],["DJ","D4"],["S2","S3"],["DQ","DK"]],3),False), # Partial trick, no reneging
        ((["HA","D2","D3"],[["C3","C2"],["HT","D5"],["HJ","D4"],["HK","HQ"]],0),True), # Partial trick, east and south reneged
    ],reneged)

def test_validate_dashes()->None:
    assert_correct_output([
        ((["DK","DA","D2","C3"],),0),
        ((["SK","SA","SJ","-"],),1),
        ((["HT","H2","-","-"],),2),
        ((["C2","-","-","-"],),3),
    ],validate_dashes)

    assert_correct_exception([
        ((["D2","D3","-","D4"],),CardAfterDashError),
        ((["-","-","-","-"],),FirstCardIsDashError),
        ((["-","S3","S4","S5"],),FirstCardIsDashError)
    ],validate_dashes)

def test_validate_play()->None:

    hands:list[list[str]] = [
        ["S4","S2","H7","DK","DT","D9","D8","D5","D4","D3","CQ","C8","C6"],
        ["SA","SK","SQ","S9","S5","HK","HQ","HT","H6","D2","CK","CT","C7"],
        ["SJ","ST","S8","S7","S6","S3","H9","H5","H3","DQ","DJ","D6","CA"],
        ["HA","HJ","H8","H4","H2","DA","D7","CJ","C9","C5","C4","C3","C2"]
    ]

    assert_correct_output([
        (("H7 H6 H3 % H8 C6 CT CA C2 C8 PBN HT H5 H2 CQ CK S3 C3 !","N",hands,"C"), # Valid, some illegal plays
        ("H7H6H3H8C2C6CTCAH5H2C8HTCQCKS3C3",[0,1,2,3,3,0,1,2,2,3,0,1,0,1,2,3],4,2)),
        (("H7 H6 H3 H8 C6 CT CA C2 C8 HT H5 H2 CQ -- - --","N",hands,"C"), # Last trick is claimed midway through, mix of -- and -
        ("H7H6H3H8C2C6CTCAH5H2C8HTCQ",[0,1,2,3,3,0,1,2,2,3,0,1,0],3,1)),
        (("H3 HTHQ H2","S",[["HQ"],["H2"],["H3"],["HT"]],"H"), # HTHQ, south lead
        ("H3HTHQH2",[2,3,0,1],1,0)),
    ],validate_play)

    assert_correct_exception([
        (("H7 H6 H3 H8 C6 CT CA C2 C8 HT H5 H2 CQ CK S3","N",hands,"C"),UnbalancedPlaySequenceError), # Plays not divisible by 4
        (("H7 H6 H3 H8 C6 CT CA C2 C8 HT H5 H2 CQ CK S3 HJ","N",hands,"C"),RenegeError), # Last play is a renege, west has a club but plays a heart
        (("H7 H6 H3 H8 C6 CT CA C2 C8 HT H5 H2 CQ CK S3 C7","N",hands,"C"),PlayError), # West plays east's C7 
        (("H7 H6 H3 H8 C6 CT CA C2 C8 HT H5 H2 CQ CK S3 C2","N",hands,"C"),PlayError), # West plays their C2 again
        (("H7 H6 H3 H8 C6 CT CA C2 C8 HT H5 H2 CQ - S3 -","N",hands,"C"),CardAfterDashError), # Card follows dash in last trick
        (("H7 H6 H3 H8 C6 CT CA C2 C8 HT H5 H2 - CK S3 C3","N",hands,"C"),FirstCardIsDashError), # First play to last trick is a dash
        (("H7 - - - C6 CT CA C2 C8 HT H5 H2 CQ CK S3 C2","N",hands,"C"),MultipleClaimError) # Claim appears during first trick, but play continues
    ],validate_play)

def test_compute_claim()->None:
    assert_correct_output([
        ((10,6,5),10) # Valid
    ],compute_claim)
    
    assert_correct_exception([
        ((8,10,9),ClaimError), # Result is fewer than the number of tricks declarer won from play,
        ((12,12,10),ClaimError) # Result is greater than the sum of the number of tricks remaining and the number of tricks declarer won from play.
    ],compute_claim)

def test_compute_year()->None:
    assert_correct_output([
        (("2016","2010.??.??"),2010), # Year is non-empty
        (("2000 Bridge Game","#"),2000), # Read year from event
        (("Bridge 2017","?"),0), # Read year from event, outside range high
        (("Bridge1954",""),0), # Read year from event, outside range low
        (("Bridge1982Champs","2032.??.??"),1982) # Date invalid, read from event
    ],compute_year)

def test_normalize_name()->None:
    
    wbf_info = ( 
        ("John Smith",WbfInfo(0,0,("JOHN","SMITH"),())), ("John (Smith) Doyle",WbfInfo(0,0,("JOHN","SMITH","DOYLE"),())),
        ("Liam A. R. Smith",WbfInfo(0,0,("LIAM","SMITH"),("A","R"))), ("Liam 'Ashton' R. Smith",WbfInfo(0,0,("LIAM","ASHTON","SMITH"),("R"))),
        ("Jeff K. M. Q. Doyle",WbfInfo(0,0,("JEFF","DOYLE"),("K","M","Q"))), ("Jeff K. L. Doyle",WbfInfo(0,0,("JEFF","DOYLE"),("K","L"))),   
    )
    
    assert_correct_output([
        (("John Smith",wbf_info),"John Smith,0,0"),
        (("John Smith Doyle",wbf_info),"John (Smith) Doyle,0,0"),
        (("Liam A. R. Smith",wbf_info),",-1,-1"), # Two candidates are equally as likely
        (("Liam Ashton R. Smith",wbf_info),"Liam 'Ashton' R. Smith,0,0"),
        (("Jeff K. Doyle",wbf_info),"Jeff K. L. Doyle,0,0")
    ],normalize_name)

def test_clean_board()->None:

    wbf_info = (("NORTH",WbfInfo(1,1,("NORTH",),())),("EAST",WbfInfo(2,2,("EAST",),())),("SOUTH",WbfInfo(3,3,("SOUTH",),())),("WEST",WbfInfo(4,4,("WEST",),())))
    
    assert_correct_output([
        (("2000 Bridge","2000.??.??","North","East","South","West","N:AK75.54.987653.A Q.AT983.42.JT753 642.KQJ7.AQJ.962 JT983.62.KT.KQ84",
        "All","N","N","1D 1H X P P 2C 2D 3C 3D P P P","3D","N","E","SQ S2 S3 SK - - - S5",9,wbf_info),(
        {"names":["NORTH,1,1","EAST,2,2","SOUTH,3,3","WEST,4,4"],
        "deal":"N:AK75.54.987653.A Q.AT983.42.JT753 642.KQJ7.AQJ.962 JT983.62.KT.KQ84","auction":"1D 1H X P P 2C 2D 3C 3D P P P",
        "declarer":"N","play":"SQS2S3SKS5","play_order":[1,2,3,0,0],"contract":"3D","bidstart":"N","EW_vulnerable":True,"NS_vulnerable":True,"lead":"E","claim":9,"year":2000},"","")),
    ],clean_board)

    assert_correct_exception([
        (("2000 Bridge","2000.??.??","","","","","N:AK75.54.987653.A Q.AT983.42.JT753 642.KQJ7.AQJ.962 JT983.62.KT.KQ84",
        "All","N","N","1D 1H X P P 2C 2D 3C 3D P P P","3D","N","E","SQ S2 S3 SK - - - S5",9,wbf_info),MissingNamesError),
        
        (("2000 Bridge","2000.??.??","North","East","South","West","N:AK75.54.987653.A Q.AT983.42.JT753 642.KQJ7.AQJ.962 JT983.62.KT.KQ84",
        "All","N","N","1D 1H X P P 2C 2D 3C 3D P P P","4D","N","E","SQ S2 S3 SK - - - S5",9,wbf_info),ContractContradictionError),

        (("2000 Bridge","2000.??.??","North","East","South","West","N:AK75.54.987653.A Q.AT983.42.JT753 642.KQJ7.AQJ.962 JT983.62.KT.KQ84",
        "All","N","N","1D 1H X P P 2C 2D 3C 3D P P P","3D","N","S","SQ S2 S3 SK - - - S5",9,wbf_info),LeadContradictionError),

        (("2000 Bridge","2000.??.??","North","East","South","West","N:AK75.54.987653.A Q.AT983.42.JT753 642.KQJ7.AQJ.962 JT983.62.KT.KQ84",
        "All","N","N","1D 1H X P P 2C 2D 3C 3D P P P","3D","E","S","SQ S2 S3 SK - - - S5",9,wbf_info),DeclarerContradictionError),

        (("2000 Bridge","2000.??.??","North","East","South","West","N:AK7.54.987653.A Q.AT983.42.JT753 642.KQJ7.AQJ.962 JT983.62.KT.KQ84",
        "All","N","N","1D 1H X P P 2C 2D 3C 3D P P P","3D","N","E","SQ S2 S3 SK - - - S5",9,wbf_info),UnbalancedDealError),

        (("2000 Bridge","2000.??.??","North","East","South","West","N:AK75.54.987653.A Q.AT983.42.JT753 642.KQJ7.AQJ.962 JT983.62.KT.KQ84",
        "All","N","N","P P P P","P","P","P","SQ S2 S3 SK - - - S5",9,wbf_info),PassContradictionError),

        (("2000 Bridge","2000.??.??","North","East","South","West","N:AK75.54.987653.A Q.AT983.42.JT753 642.KQJ7.AQJ.962 JT983.62.KT.KQ84",
        "All","N","N","1D 1H X P P 2C 2D 3C 3D P P P","3D","N","E","SQ S2 S3 SK - - - S5",0,wbf_info),ClaimError),

    ],clean_board)