from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, List, Dict, Literal, Any


class InsufficientFundsError(Exception):
    """Raised when a withdrawal or purchase would result in a negative cash balance."""


class InsufficientHoldingsError(Exception):
    """Raised when attempting to sell more shares than the account owns."""


class InvalidSymbolError(Exception):
    """Raised when an unknown ticker symbol is used."""


class InvalidQuantityError(Exception):
    """Raised when a non‑positive quantity is supplied for a transaction."""


@dataclass(frozen=True)
class Transaction:
    timestamp: datetime
    type: Literal["deposit", "withdraw", "buy", "sell"]
    symbol: Optional[str]
    quantity: float  # positive for buy, negative for sell, None for cash moves
    price_per_share: Optional[float]  # None for cash moves
    total_amount: float  # positive for deposits/buys, negative for withdrawals/sells


def get_share_price(symbol: str) -> float:
    """
    Test implementation that returns fixed prices for supported symbols.
    Raises InvalidSymbolError for unknown symbols.
    """
    prices = {
        "AAPL": 150.0,
        "TSLA": 800.0,
        "GOOGL": 2800.0,
    }
    if symbol not in prices:
        raise InvalidSymbolError(f"Unknown symbol: {symbol}")
    return prices[symbol]


class Account:
    def __init__(self, initial_deposit: float) -> None:
        if initial_deposit <= 0:
            raise ValueError("Initial deposit must be positive")
        self._initial_deposit: float = float(initial_deposit)
        self._transactions: List[Transaction] = []
        now = datetime.utcnow().replace(tzinfo=timezone.utc)
        self._record_transaction(
            timestamp=now,
            type="deposit",
            symbol=None,
            quantity=0.0,
            price_per_share=None,
            total_amount=float(initial_deposit),
        )

    def _record_transaction(
        self,
        timestamp: datetime,
        type: Literal["deposit", "withdraw", "buy", "sell"],
        symbol: Optional[str],
        quantity: float,
        price_per_share: Optional[float],
        total_amount: float,
    ) -> None:
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        self._transactions.append(
            Transaction(
                timestamp=timestamp,
                type=type,
                symbol=symbol,
                quantity=quantity,
                price_per_share=price_per_share,
                total_amount=total_amount,
            )
        )

    def deposit(self, amount: float, timestamp: Optional[datetime] = None) -> None:
        if amount <= 0:
            raise ValueError("Deposit amount must be positive")
        ts = timestamp or datetime.utcnow().replace(tzinfo=timezone.utc)
        self._record_transaction(
            timestamp=ts,
            type="deposit",
            symbol=None,
            quantity=0.0,
            price_per_share=None,
            total_amount=float(amount),
        )

    def withdraw(self, amount: float, timestamp: Optional[datetime] = None) -> None:
        if amount <= 0:
            raise ValueError("Withdrawal amount must be positive")
        cash, _ = self._apply_transactions_up_to(
            self._latest_timestamp() if timestamp is None else timestamp
        )
        if cash < amount:
            raise InsufficientFundsError("Insufficient cash for withdrawal")
        ts = timestamp or datetime.utcnow().replace(tzinfo=timezone.utc)
        self._record_transaction(
            timestamp=ts,
            type="withdraw",
            symbol=None,
            quantity=0.0,
            price_per_share=None,
            total_amount=-float(amount),
        )

    def buy(
        self,
        symbol: str,
        quantity: float,
        timestamp: Optional[datetime] = None,
    ) -> None:
        if quantity <= 0:
            raise InvalidQuantityError("Quantity must be positive for a buy")
        price = get_share_price(symbol)
        cost = price * quantity
        cash, holdings = self._apply_transactions_up_to(
            self._latest_timestamp() if timestamp is None else timestamp
        )
        if cash < cost:
            raise InsufficientFundsError("Insufficient cash to buy shares")
        ts = timestamp or datetime.utcnow().replace(tzinfo=timezone.utc)
        self._record_transaction(
            timestamp=ts,
            type="buy",
            symbol=symbol,
            quantity=float(quantity),
            price_per_share=price,
            total_amount=-float(cost),
        )

    def sell(
        self,
        symbol: str,
        quantity: float,
        timestamp: Optional[datetime] = None,
    ) -> None:
        if quantity <= 0:
            raise InvalidQuantityError("Quantity must be positive for a sell")
        ts = timestamp or datetime.utcnow().replace(tzinfo=timezone.utc)
        cash, holdings = self._apply_transactions_up_to(ts)
        current_qty = holdings.get(symbol, 0.0)
        if current_qty < quantity:
            raise InsufficientHoldingsError(
                f"Attempting to sell {quantity} of {symbol} but only {current_qty} held"
            )
        price = get_share_price(symbol)
        proceeds = price * quantity
        self._record_transaction(
            timestamp=ts,
            type="sell",
            symbol=symbol,
            quantity=-float(quantity),
            price_per_share=price,
            total_amount=float(proceeds),
        )

    def _apply_transactions_up_to(self, up_to: datetime) -> tuple[float, Dict[str, float]]:
        """
        Returns the cash balance and holdings dictionary after applying all transactions
        up to and including the provided timestamp.
        """
        if up_to.tzinfo is None:
            up_to = up_to.replace(tzinfo=timezone.utc)
        cash = 0.0
        holdings: Dict[str, float] = {}
        for tx in sorted(self._transactions, key=lambda t: t.timestamp):
            if tx.timestamp > up_to:
                break
            cash += tx.total_amount
            if tx.type in ("buy", "sell") and tx.symbol:
                holdings[tx.symbol] = holdings.get(tx.symbol, 0.0) + tx.quantity
        return cash, holdings

    def _latest_timestamp(self) -> datetime:
        return max(tx.timestamp for tx in self._transactions)

    def portfolio_value(self, as_of: Optional[datetime] = None) -> float:
        """
        Returns the total value of cash plus market value of all holdings as of `as_of`.
        If `as_of` is `None`, uses the most recent transaction date.
        """
        ts = as_of or self._latest_timestamp()
        cash, holdings = self._apply_transactions_up_to(ts)
        market_value = 0.0
        for symbol, qty in holdings.items():
            if qty == 0:
                continue
            price = get_share_price(symbol)
            market_value += qty * price
        return cash + market_value

    def profit_loss(self, as_of: Optional[datetime] = None) -> float:
        return self.portfolio_value(as_of) - self._initial_deposit

    def holdings(self, as_of: Optional[datetime] = None) -> Dict[str, float]:
        ts = as_of or self._latest_timestamp()
        _, holdings = self._apply_transactions_up_to(ts)
        return {sym: qty for sym, qty in holdings.items() if qty != 0.0}

    def transaction_history(
        self,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
    ) -> List[Transaction]:
        result: List[Transaction] = []
        for tx in self._transactions:
            if since and tx.timestamp < since:
                continue
            if until and tx.timestamp > until:
                continue
            result.append(tx)
        return result

    def cash_balance(self, as_of: Optional[datetime] = None) -> float:
        ts = as_of or self._latest_timestamp()
        cash, _ = self._apply_transactions_up_to(ts)
        return cash

    # Public helper methods for withdrawals and buys that need state before action
    def withdraw(self, amount: float, timestamp: Optional[datetime] = None) -> None:
        if amount <= 0:
            raise ValueError("Withdrawal amount must be positive")
        ts = timestamp or datetime.utcnow().replace(tzinfo=timezone.utc)
        # Determine cash before withdrawal
        cash_before, _ = self._apply_transactions_up_to(ts)
        if cash_before < amount:
            raise InsufficientFundsError("Insufficient cash for withdrawal")
        self._record_transaction(
            timestamp=ts,
            type="withdraw",
            symbol=None,
            quantity=0.0,
            price_per_share=None,
            total_amount=-float(amount),
        )

    def buy(
        self,
        symbol: str,
        quantity: float,
        timestamp: Optional[datetime] = None,
    ) -> None:
        if quantity <= 0:
            raise InvalidQuantityError("Quantity must be positive for a buy")
        ts = timestamp or datetime.utcnow().replace(tzinfo=timezone.utc)
        price = get_share_price(symbol)
        cost = price * quantity
        cash_before, _ = self._apply_transactions_up_to(ts)
        if cash_before < cost:
            raise InsufficientFundsError("Insufficient cash to buy shares")
        self._record_transaction(
            timestamp=ts,
            type="buy",
            symbol=symbol,
            quantity=float(quantity),
            price_per_share=price,
            total_amount=-float(cost),
        )

    def sell(
        self,
        symbol: str,
        quantity: float,
        timestamp: Optional[datetime] = None,
    ) -> None:
        if quantity <= 0:
            raise InvalidQuantityError("Quantity must be positive for a sell")
        ts = timestamp or datetime.utcnow().replace(tzinfo=timezone.utc)
        holdings_before, _ = self._apply_transactions_up_to(ts)
        current_qty = holdings_before.get(symbol, 0.0)
        if current_qty < quantity:
            raise InsufficientHoldingsError(
                f"Attempting to sell {quantity} of {symbol} but only {current_qty} held"
            )
        price = get_share_price(symbol)
        proceeds = price * quantity
        self._record_transaction(
            timestamp=ts,
            type="sell",
            symbol=symbol,
            quantity=-float(quantity),
            price_per_share=price,
            total_amount=float(proceeds),
        )
"""
End of accounts.py
"""
