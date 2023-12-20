"""Defines all possible issues with a board as different exception classes."""


class ContradictionError(Exception):
    """An error to be thrown if a function discovers that two entries from the input data contradict each other."""

class ExceptionWithDescripton(Exception):

    def __str__(self)->str:
        return self.__doc__ or "An error occured."

class BoardError(ExceptionWithDescripton):
    """Invalid board."""
    
class AuctionError(ExceptionWithDescripton):
    """Invalid auction."""

class PlaySequenceError(ExceptionWithDescripton):
    """Invalid play sequence."""




class MissingDealError(BoardError):
    """Missing deal."""

class UnbalancedDealError(BoardError):
    """Deal had a hand that did not have 13 cards."""

class CardError(BoardError):
    """A player had an invalid card in the deal, or a card appeared twice."""

class MissingNamesError(BoardError):
    """All names are missing."""

class ClaimError(BoardError):
    """The declarer claimed fewer tricks than they had already won, or more tricks than there were remaining."""

class ContractContradictionError(BoardError):
    """Contract differs from the contract deducible from the auction."""

class DeclarerContradictionError(BoardError):
    """Declarer differs from the declarer deducible from the auction."""

class LeadContradictionError(BoardError):
    """Lead differs from the lead deducible from the declarer."""

class PassContradictionError(BoardError):
    """Contract is pass, play sequence is non-empty."""




class MissingAuctionError(AuctionError):
    """Missing auction."""

class PassError(AuctionError):
    """The contract was passed out in the middle of the auction, or the auction did not end with three passes."""

class ContractBidError(AuctionError):
    """Contract bid was made in a non-increasing fashion."""

class DoubleBidError(AuctionError):
    """A double bid was made where the contract was already doubled or redoubled, the bid was made by the side who bid the last contract, or there was no contract bid made yet."""

class RedoubleBidError(AuctionError):
    """A redouble bid was made where the contract was not doubled or already redoubled, the bid was made by the side who did not bid the last contract, or there was no contract bid made yet."""




class MissingPlaySequenceInfoError(PlaySequenceError):
    """Missing play_sequence, lead, or trump."""

class FirstCardIsDashError(PlaySequenceError):
    """First card played to a trick is a dash."""

class CardAfterDashError(PlaySequenceError):
    """A card is played to a trick after a dash."""

class UnbalancedPlaySequenceError(PlaySequenceError):
    """The number of legal plays, augmented with dashes if necessary, is not divisible by 4."""

class MultipleClaimError(PlaySequenceError):
    """Dashes appeared in more than one trick."""

class PlayError(PlaySequenceError):
    """A card is played twice or the player never had it."""

class RenegeError(PlaySequenceError):
    """A player reneged."""


