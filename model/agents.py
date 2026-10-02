import mesa


class Trader(mesa.Agent):
    """Base class for single-unit zero-intelligence traders."""

    recent_decisions: list[dict] = []
    agent_profiles: dict = {}

    def __init__(self, model, private_value: float):
        """Initialize a trader and schedule its first market arrival."""
        super().__init__(model)
        self.private_value = private_value  # reservation price (buyer) or cost (seller)
        self.cash = 0.0
        self.inventory = 0
        self.done_trading = False  # True once this agent's single unit has traded
        self.side: str = ""
        first_delay = self.model.rng.exponential(self.model.mean_interarrival)
        self.model.schedule_event(self.act, after=first_delay)

    @classmethod
    def reset_telemetry(cls):
        """Reset the ZI-C decision log and agent profile store."""
        cls.recent_decisions.clear()
        cls.agent_profiles.clear()

    @classmethod
    def record_decision(cls, decision: dict):
        """Record a trader's decision in the inspectable telemetry buffer."""
        cls.recent_decisions.append(decision)
        if len(cls.recent_decisions) > 60:
            cls.recent_decisions.pop(0)
        cls.agent_profiles[decision["agent_id"]] = decision

    def wealth(self) -> float:
        """Return marked wealth using the trader's private value for inventory."""
        return self.cash + self.inventory * self.private_value

    def _schedule_next_arrival(self):
        """Schedule another market arrival unless the trader has completed its trade."""
        if self.done_trading:
            return
        delay = self.model.rng.exponential(self.model.mean_interarrival)
        self.model.schedule_event(self.act, after=delay)

    def act(self):
        """Submit or update an order when the trader arrives at the market."""
        raise NotImplementedError


class Buyer(Trader):
    """Zero-intelligence buyer with one unit of demand."""

    def __init__(self, model, reservation_price: float):
        """Create a buyer with a maximum willingness to pay."""
        super().__init__(model, private_value=reservation_price)
        self.side = "bid"

    def act(self):
        """Cancel any stale bid, submit a new random bid, and try to trade."""
        if self.done_trading:
            return

        self.model.order_book.cancel_agent_order(self.unique_id, "bid")
        bid_price = self.model.rng.uniform(0, self.private_value)
        self.model.order_book.submit_bid(self.unique_id, bid_price, self.model.time)

        bb = self.model.order_book.best_bid()
        ba = self.model.order_book.best_ask()
        spread = self.model.order_book.spread()
        alpha = (bid_price / self.private_value) if self.private_value > 0 else 0.5
        score = alpha * 4.0
        pct = alpha * 100.0

        if alpha >= 0.8:
            tactic = f"Aggressive Bid ({pct:.0f}% of Val)"
        elif alpha >= 0.6:
            tactic = f"High Quote ({pct:.0f}% of Val)"
        elif alpha >= 0.4:
            tactic = f"Mid-Range Draw ({pct:.0f}% of Val)"
        elif alpha >= 0.2:
            tactic = f"Patient Draw ({pct:.0f}% of Val)"
        else:
            tactic = f"Deep Margin ({pct:.0f}% of Val)"

        decision = {
            "agent_id": self.unique_id,
            "role": "Buyer",
            "time": round(self.model.time, 2),
            "val": round(self.private_value, 2),
            "best_bid": round(bb.price, 2) if bb else None,
            "best_ask": round(ba.price, 2) if ba else None,
            "spread": round(spread, 2) if spread is not None else None,
            "decision_type": "zi_heuristic",
            "score": round(score, 2),
            "alpha": round(alpha, 2),
            "tactic": tactic,
            "submitted_price": round(bid_price, 2),
            "margin": round(self.private_value - bid_price, 2),
            "tokens": 0,
            "reasoning": f"Canonical Gode & Sunder (1993) uniform draw U[0, ${self.private_value:.2f}] subject to no-loss budget constraint (P <= V).",
            "is_live": False,
            "system_one": {
                "theory": "Gode & Sunder (1993) Zero-Intelligence Constrained",
                "budget_constraint": f"Bid <= Valuation (${self.private_value:.2f})",
                "draw_range": f"[0.00, {self.private_value:.2f}]",
                "actual_draw": f"${bid_price:.2f}",
                "shading_pct": f"{pct:.1f}% of Valuation",
                "surplus_retained": f"${self.private_value - bid_price:.2f}",
            },
        }
        Trader.record_decision(decision)

        self.model.handle_arrival()
        self._schedule_next_arrival()

    def settle_purchase(self, price: float):
        """Record a completed purchase and stop future trading."""
        self.cash -= price
        self.inventory += 1
        self.done_trading = True


class Seller(Trader):
    """Zero-intelligence seller endowed with one unit to sell."""

    def __init__(self, model, cost: float):
        """Create a seller with a minimum acceptable sale price."""
        super().__init__(model, private_value=cost)
        self.side = "ask"
        self.inventory = (
            1  # sellers start endowed with the one unit they intend to sell
        )

    def act(self):
        """Cancel any stale ask, submit a new random ask, and try to trade."""
        if self.done_trading:
            return

        self.model.order_book.cancel_agent_order(self.unique_id, "ask")
        ask_price = self.model.rng.uniform(self.private_value, self.model.max_valuation)
        self.model.order_book.submit_ask(self.unique_id, ask_price, self.model.time)

        bb = self.model.order_book.best_bid()
        ba = self.model.order_book.best_ask()
        spread = self.model.order_book.spread()
        val_range = self.model.max_valuation - self.private_value
        alpha = (self.model.max_valuation - ask_price) / val_range if val_range > 0 else 0.5
        score = alpha * 4.0
        markup_pct = ((ask_price - self.private_value) / val_range * 100.0) if val_range > 0 else 50.0

        if alpha >= 0.8:
            tactic = f"Aggressive Ask (+{markup_pct:.0f}% Markup)"
        elif alpha >= 0.6:
            tactic = f"Low Ask (+{markup_pct:.0f}% Markup)"
        elif alpha >= 0.4:
            tactic = f"Mid-Range Ask (+{markup_pct:.0f}% Markup)"
        elif alpha >= 0.2:
            tactic = f"High Ask (+{markup_pct:.0f}% Markup)"
        else:
            tactic = f"Max Markup (+{markup_pct:.0f}% Markup)"

        decision = {
            "agent_id": self.unique_id,
            "role": "Seller",
            "time": round(self.model.time, 2),
            "val": round(self.private_value, 2),
            "best_bid": round(bb.price, 2) if bb else None,
            "best_ask": round(ba.price, 2) if ba else None,
            "spread": round(spread, 2) if spread is not None else None,
            "decision_type": "zi_heuristic",
            "score": round(score, 2),
            "alpha": round(alpha, 2),
            "tactic": tactic,
            "submitted_price": round(ask_price, 2),
            "margin": round(ask_price - self.private_value, 2),
            "tokens": 0,
            "reasoning": f"Canonical Gode & Sunder (1993) uniform draw U[${self.private_value:.2f}, ${self.model.max_valuation:.2f}] subject to no-loss budget constraint (P >= C).",
            "is_live": False,
            "system_one": {
                "theory": "Gode & Sunder (1993) Zero-Intelligence Constrained",
                "budget_constraint": f"Ask >= Cost (${self.private_value:.2f})",
                "draw_range": f"[{self.private_value:.2f}, {self.model.max_valuation:.2f}]",
                "actual_draw": f"${ask_price:.2f}",
                "markup_pct": f"{markup_pct:.1f}% above Cost",
                "surplus_retained": f"${ask_price - self.private_value:.2f}",
            },
        }
        Trader.record_decision(decision)

        self.model.handle_arrival()
        self._schedule_next_arrival()

    def settle_sale(self, price: float):
        """Record a completed sale and stop future trading."""
        self.cash += price
        self.inventory -= 1
        self.done_trading = True
