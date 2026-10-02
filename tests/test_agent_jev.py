import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent_jev import JevBuyer, JevSeller
from model import DoubleAuctionModel


def test_jev_traders_creation():
    model = DoubleAuctionModel(
        n_buyers=5,
        n_sellers=5,
        buyer_cls=JevBuyer,
        seller_cls=JevSeller,
        rng=1,
    )
    buyers = [a for a in model.agents if isinstance(a, JevBuyer)]
    sellers = [a for a in model.agents if isinstance(a, JevSeller)]
    assert len(buyers) == 5
    assert len(sellers) == 5
    assert len(model.agents) == 10


def test_jev_traders_respect_rationality_constraints():
    model = DoubleAuctionModel(
        n_buyers=10,
        n_sellers=10,
        buyer_cls=JevBuyer,
        seller_cls=JevSeller,
        rng=42,
    )
    model.run_for(50)

    for a in model.agents:
        if isinstance(a, JevBuyer) and a.done_trading:
            assert a.wealth() >= -1e-9  # Never transacts at a loss
        if isinstance(a, JevSeller) and a.done_trading:
            assert a.cash >= a.private_value - 1e-9  # Never sells below cost


def test_jev_traders_choice_stochastic_execution():
    from agent_jev import JevTrader

    JevTrader.reset_telemetry()
    model = DoubleAuctionModel(
        n_buyers=5,
        n_sellers=5,
        buyer_cls=JevBuyer,
        seller_cls=JevSeller,
        rng=123,
    )
    model.run_for(15)

    assert len(JevTrader.recent_decisions) > 0
    # Check that decisions contain chosen_tactic and probability distribution
    choice_decisions = [d for d in JevTrader.recent_decisions if "chosen_tactic" in d]
    assert len(choice_decisions) > 0
    for d in choice_decisions:
        assert d["chosen_tactic"] in (
            "spread_crosser",
            "queue_competitor",
            "patient_maker",
            "deep_discount",
            "premium_markup",
        )
        assert "distribution" in d
        assert len(d["distribution"]) >= 3
        # Probabilities sum to ~1.0
        assert 0.99 <= sum(d["distribution"].values()) <= 1.01

