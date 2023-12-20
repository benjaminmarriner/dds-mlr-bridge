"""ctypes definitions for use with the DDS DLL."""

from ctypes import CDLL,c_int,Structure,POINTER,c_char

MAXNOOFBOARDS:int = 200
MAXNOOFTABLES:int = 32 # We always use 5 strains

class dealPBN(Structure):
    _fields_ = [("trump",c_int),("first",c_int),("currentTrickSuit",c_int * 3),("currentTrickRank",c_int*3),("remainCards",c_char * 80)]

class boardsPBN(Structure):
    _fields_= [("noOfBoards",c_int),("dealPBN",dealPBN * MAXNOOFBOARDS),
               ("target",c_int * MAXNOOFBOARDS),("solutions",c_int*MAXNOOFBOARDS),
               ("mode",c_int * MAXNOOFBOARDS)]
    
class playTracePBN(Structure):
    _fields_=[("number",c_int),("cards",c_char*106)]

class playTracesPBN(Structure):
    _fields_ = [("noOfBoards",c_int),("plays",playTracePBN * (MAXNOOFBOARDS // 10))]
    
class solvedPlay(Structure):
    _fields_=[("number",c_int),("tricks",c_int*53)]

class solvedPlays(Structure):
    _fields_ = [("noOfBoards",c_int),("solved",solvedPlay*MAXNOOFBOARDS)]

class ddTableDealPBN(Structure):
    _fields_ = [("cards",c_char*80)]

class ddTableDealsPBN(Structure):
    _fields_ = [("noOfTables",c_int),("deals",ddTableDealPBN*MAXNOOFTABLES)]

class ddTableResults(Structure):
    _fields_ = [("resTable",(c_int*4)*5)]

class ddTablesRes(Structure):
    _fields_ = [("noOfBoards",c_int),("results",ddTableResults*MAXNOOFTABLES)]

class parResults(Structure):
    _fields_ = [("parScore",(c_char*2)*16),("parContractsString",(c_char*2)*128)]

class allParResults(Structure):
    _fields_ = [("parResults",parResults*MAXNOOFTABLES)]

def create_dds(dll_path:str) -> CDLL:

    dds: CDLL = CDLL(dll_path)

    dds.AnalyseAllPlaysPBN.argtypes=[POINTER(boardsPBN),POINTER(playTracesPBN),POINTER(solvedPlays),c_int]
    dds.AnalyseAllPlaysPBN.restype=c_int

    dds.CalcAllTablesPBN.argtypes=[POINTER(ddTableDealsPBN),c_int,c_int*5,POINTER(ddTablesRes),POINTER(allParResults)]
    dds.CalcAllTablesPBN.restype=c_int

    return dds