import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from web_app import AuctionServer
from agent_jev import JevTrader, JevBuyer, JevSeller


def test_max_steps_safeguard():
    server = AuctionServer()
    server.reset(trader_type="zi", max_steps=5)
    assert server.max_steps == 5
    assert server.steps_taken == 0

    # Step 5 times
    for _ in range(5):
        state = server.step(dt=1.0)

    assert server.steps_taken == 5
    assert state["steps_taken"] == 5
    assert state["is_max_steps_reached"] is True

    # Step further: must NOT execute further ticks
    state_after = server.step(dt=1.0)
    assert server.steps_taken == 5
    assert state_after["steps_taken"] == 5


def test_immediate_stop_flag():
    server = AuctionServer()
    server.reset(trader_type="jev", max_steps=50)

    # Calling stop sets both flags
    res = server.stop()
    assert res["status"] == "stopped"
    assert server.stop_requested is True
    assert JevTrader.stop_requested is True

    # When stop_requested is True, query_jev_score immediately returns fallback
    buyer = server.model.agents[0]
    if isinstance(buyer, JevTrader):
        initial_calls = JevTrader.total_ai_calls
        score = buyer.query_jev_score({"val": 50.0, "ask": 45.0}, "question", ["c1"])
        # Should not increment total_ai_calls or token spend
        assert JevTrader.total_ai_calls == initial_calls
        assert score == 3.2


def test_reset_clears_stop_and_updates_max_steps():
    server = AuctionServer()
    server.stop()
    assert server.stop_requested is True
    assert JevTrader.stop_requested is True

    server.reset(max_steps=20)
    assert server.stop_requested is False
    assert server.max_steps == 20
    assert server.steps_taken == 0
