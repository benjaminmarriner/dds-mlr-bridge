"""Unit tests for the dds module."""

from typing import Callable, Tuple
from dds import *

def assert_correct_output(input_to_expected_output:list[Tuple[Any,Any]],function:Callable) -> None:

    """
    Asserts that, when given the first element of a input_to_expected_output tuple, the input function returns the second for 
    each tuple in the list. The first element in every tuple must itself be an iterable of function parameters.
    """

    for (input,expected_output) in input_to_expected_output:
        assert function(*input) == expected_output

def test_compute_undertrick_points()->None:
    assert_correct_output([
        ((1,"",True,1988),-100),
        ((1,"",False,0),-50),
        ((1,"X",True,1988),-200),
        ((3,"X",True,1988),-800),
        ((4,"X",True,1988),-1100),
        ((1,"R",True,1988),-400),
        ((2,"R",True,1988),-1000),
        ((5,"R",True,1988),-2800),
        ((1,"X",False,1988),-100),
        ((2,"X",False,1988),-300),
        ((4,"X",False,1988),-800),
        ((4,"X",False,1987),-700),
        ((1,"R",False,1988),-200),
        ((3,"R",False,1988),-1000),
        ((6,"R",False,1988),-2800),
    ],compute_undertrick_points)

def test_compute_overtrick_points()->None:
    assert_correct_output([
        ((2,"H","",False),60),
        ((2,"D","",False),40),
        ((2,"N","",True),60),
        ((4,"C","R",True),1600),
        ((3,"N","R",False),600),
        ((5,"S","X",False),500),
        ((1,"N","X",True),200)
    ],compute_overtrick_points)

def test_compute_bonus_points()->None:
    assert_correct_output([
        ((3,8,0,"",True),0),
        ((3,10,90,"",False),50),
        ((3,9,100,"",False),300),
        ((4,10,480,"R",True),600),
        ((6,12,120,"",False),800),
        ((6,12,120,"",True),1250),
        ((7,13,210,"",False),1300),
        ((7,13,210,"",True),2000),
        ((7,12,0,"R",True),0)
    ],compute_bonus_points)

def test_compute_contract_points()->None:
    assert_correct_output([
        ((1,"N",""),40),
        ((2,"H",""),60),
        ((3,"C",""),60),
        ((2,"N","X"),140),
        ((4,"S","X"),240),
        ((1,"D","X"),40),
        ((3,"N","R"),400),
        ((1,"H","R"),120),
        ((5,"D","R"),400),
    ],compute_contract_points)

def test_compute_score()->None:
    assert_correct_output([
        (("1H",9,False,0),140),
        (("4SX",8,True,0),-500),
        (("7H",13,False,0),1510),
        (("1N",9,True,0),150),
        (("4HR",10,True,0),1080),
        (("3C",9,True,0),110)
    ],compute_score)

def test_determine_declarer_candidates()->None:
    assert_correct_output([
        (("1S 2H 3C P P P",0),{"S":{0,1,3},"H":{0,1,2},"D":{0,1,2,3},"C":{1,2,3},"N":{0,1,2,3}}),
        (("1S 2N 3S 4N P P P",3),{"S":{0,2,3},"H":{0,1,2,3},"D":{0,1,2,3},"C":{0,1,2,3},"N":{0,1,3}}),
        (("1S 2S 3S 4S P P P",0),{"S":{0,1},"H":{0,1,2,3},"D":{0,1,2,3},"C":{0,1,2,3},"N":{0,1,2,3}}),
    ],determine_declarer_candidates)