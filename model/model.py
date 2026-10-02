import heapq
import mesa

from .agents import Buyer, Seller
from .order_book import OrderBook


class DoubleAuctionModel(mesa.Model):
    """Continuous double-auction model with pluggable trader classes."""

    def __init__(
        self,
        n_buyers: int = 25,
        n_sellers: int = 25,
        max_valuation: float = 100.0,
        mean_interarrival: float = 1.0,
        rng: int | None = None,
        buyer_cls: type = Buyer,
        seller_cls: type = Seller,
    ):
        """Create traders, the order book, and the model data collector."""
        super().__init__(rng=rng)

        if not hasattr(self, "time"):
            self.time = 0.0
        if not hasattr(mesa.Model, "schedule_event"):
            self._event_queue = []
            self._event_counter = 0

        self.max_valuation = max_valuation
        self.mean_interarrival = mean_interarrival
        self.order_book = OrderBook()
        self.buyer_cls = buyer_cls
        self.seller_cls = seller_cls

        self.clearing_price: float | None = None
        self.cumulative_volume: int = 0
        self.price_history: list[tuple[float, float]] = []  # (time, price)

        self._volume_since_last_tick: int = 0
        reservation_prices = self.rng.uniform(0, max_valuation, size=n_buyers).tolist()
        buyer_cls.create_agents(
            model=self, n=n_buyers, reservation_price=reservation_prices
        )

        costs = self.rng.uniform(0, max_valuation, size=n_sellers).tolist()
        seller_cls.create_agents(model=self, n=n_sellers, cost=costs)

        self.datacollector = mesa.DataCollector(
            model_reporters={
                "ClearingPrice": lambda m: m.clearing_price,
                "Volume": lambda m: m._volume_since_last_tick,
                "CumulativeVolume": lambda m: m.cumulative_volume,
                "Spread": lambda m: m.order_book.spread(),
                "BestBid": lambda m: (
                    m.order_book.best_bid().price if m.order_book.best_bid() else None
                ),
                "BestAsk": lambda m: (
                    m.order_book.best_ask().price if m.order_book.best_ask() else None
                ),
            },
            agent_reporters={
                "Wealth": lambda a: a.wealth(),
                "Cash": lambda a: a.cash,
                "Inventory": lambda a: a.inventory,
                "PrivateValue": lambda a: a.private_value,
                "Type": lambda a: type(a).__name__,
                "DoneTrading": lambda a: a.done_trading,
            },
        )

    def schedule_event(self, function, *, at: float | None = None, after: float | None = None, **kwargs):
        """Schedule a one-off event (native Mesa 3.5+ or fallback event queue)."""
        if hasattr(mesa.Model, "schedule_event"):
            return super().schedule_event(function, at=at, after=after, **kwargs)
        if (at is None) == (after is None):
            raise ValueError("Specify exactly one of 'at' or 'after'")
        t = at if at is not None else self.time + after
        self._event_counter += 1
        heapq.heappush(self._event_queue, (t, self._event_counter, function))

    def run_for(self, duration: float | int) -> None:
        """Advance simulation time by duration and execute scheduled events."""
        if hasattr(mesa.Model, "run_for"):
            return super().run_for(duration)
        end_time = self.time + duration
        while self._event_queue and self._event_queue[0][0] <= end_time:
            t, _, func = heapq.heappop(self._event_queue)
            self.time = t
            func()
            if self.is_equilibrium_reached:
                break
        self.time = end_time

    @property
    def is_equilibrium_reached(self) -> bool:
        """Return True when no further mutually beneficial trades can ever occur."""
        active_buyers = [
            a for a in self.agents if isinstance(a, self.buyer_cls) and not a.done_trading
        ]
        active_sellers = [
            a for a in self.agents if isinstance(a, self.seller_cls) and not a.done_trading
        ]

        if not active_buyers or not active_sellers:
            return True

        max_active_buyer_val = max(b.private_value for b in active_buyers)
        min_active_seller_cost = min(s.private_value for s in active_sellers)

        return max_active_buyer_val < min_active_seller_cost

    def handle_arrival(self):
        """Settle trades while the book remains crossed after an order arrival."""
        agents_by_id = {a.unique_id: a for a in self.agents}
        while True:
            trade = self.order_book.try_match(self.time)
            if trade is None:
                break

            buyer = agents_by_id[trade.buyer_id]
            seller = agents_by_id[trade.seller_id]
            buyer.settle_purchase(trade.price)
            seller.settle_sale(trade.price)

            self.clearing_price = trade.price
            self.price_history.append((trade.time, trade.price))
            self.cumulative_volume += 1
            self._volume_since_last_tick += 1

        if self.is_equilibrium_reached:
            self.running = False

    def step(self):
        """Collect one tick of data and reset the per-tick volume counter."""
        self.datacollector.collect(self)
        self._volume_since_last_tick = 0
        if self.is_equilibrium_reached:
            self.running = False