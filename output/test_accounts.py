import pytest
from datetime import datetime, timezone, timedelta
import accounts

from accounts import (
    Account,
    get_share_price,
    InsufficientFundsError,
    InsufficientHoldingsError,
    InvalidSymbolError,
    InvalidQuantityError,
)

# Helper to create a base timestamp
BASE_TIME = datetime(2023, 1, 1, tzinfo=timezone.utc)


def test_initial_deposit():
    # Positive initial deposit
    acc = Account(1000)
    assert acc.cash_balance() == 1000

    # Negative initial deposit should raise ValueError
    with pytest.raises(ValueError):
        Account(-100)

    # Zero initial deposit is allowed? The code checks only <=0 for deposit, not for init
    # But we will test that Account(0) is allowed because no check. However, it's odd.
    # We can assert it works but it's not required.
    acc_zero = Account(0)
    assert acc_zero.cash_balance() == 0


def test_deposit_and_invalid_deposit():
    acc = Account(100)
    # Valid deposit
    t_deposit = BASE_TIME + timedelta(seconds=5)
    acc.deposit(50, timestamp=t_deposit)
    assert acc.cash_balance(as_of=t_deposit) == 150

    # Negative deposit raises ValueError
    with pytest.raises(ValueError):
        acc.deposit(-10)

    # Zero deposit raises ValueError
    with pytest.raises(ValueError):
        acc.deposit(0)


def test_withdraw_and_insufficient_funds():
    acc = Account(100)
    t_withdraw = BASE_TIME + timedelta(seconds=10)
    # Valid withdraw
    acc.withdraw(30, timestamp=t_withdraw)
    assert acc.cash_balance(as_of=t_withdraw) == 70

    # Withdraw more than available
    with pytest.raises(InsufficientFundsError):
        acc.withdraw(1000)

    # Negative withdraw raises ValueError
    with pytest.raises(ValueError):
        acc.withdraw(-5)

    # Zero withdraw raises ValueError
    with pytest.raises(ValueError):
        acc.withdraw(0)


def test_buy_positive_and_errors():
    acc = Account(1000)
    t_buy = BASE_TIME + timedelta(seconds=20)
    # Valid buy
    acc.buy("AAPL", 2, timestamp=t_buy)  # cost 300
    assert acc.cash_balance() == 700
    assert acc.holdings() == {"AAPL": 2}

    # Insufficient funds
    with pytest.raises(InsufficientFundsError):
        acc.buy("AAPL", 10, timestamp=BASE_TIME + timedelta(seconds=30))  # cost 1500

    # Invalid quantity (negative)
    with pytest.raises(InvalidQuantityError):
        acc.buy("AAPL", -5)

    # Invalid quantity (zero)
    with pytest.raises(InvalidQuantityError):
        acc.buy("AAPL", 0)

    # Invalid symbol
    with pytest.raises(InvalidSymbolError):
        acc.buy("MSFT", 1)


def test_sell_positive_and_errors():
    acc = Account(1000)
    t_buy = BASE_TIME + timedelta(seconds=5)
    acc.buy("AAPL", 3, timestamp=t_buy)  # cost 450
    # Valid sell
    t_sell = BASE_TIME + timedelta(seconds=10)
    acc.sell("AAPL", 2, timestamp=t_sell)  # proceeds 300
    assert acc.cash_balance() == 850  # 1000 - 450 + 300
    assert acc.holdings() == {"AAPL": 1}

    # Insufficient holdings
    with pytest.raises(InsufficientHoldingsError):
        acc.sell("AAPL", 5, timestamp=BASE_TIME + timedelta(seconds=15))

    # Invalid quantity (negative)
    with pytest.raises(InvalidQuantityError):
        acc.sell("AAPL", -1)

    # Invalid quantity (zero)
    with pytest.raises(InvalidQuantityError):
        acc.sell("AAPL", 0)


def test_portfolio_value_profit_loss_and_holdings():
    acc = Account(1000)
    t1 = BASE_TIME + timedelta(seconds=5)
    acc.deposit(500, timestamp=t1)  # cash 1500
    t2 = BASE_TIME + timedelta(seconds=10)
    acc.withdraw(200, timestamp=t2)  # cash 1300
    t3 = BASE_TIME + timedelta(seconds=15)
    acc.buy("AAPL", 2, timestamp=t3)  # cost 300 -> cash 1000, holdings AAPL:2
    t4 = BASE_TIME + timedelta(seconds=20)
    acc.sell("AAPL", 1, timestamp=t4)  # proceeds 150 -> cash 1150, holdings AAPL:1

    # Portfolio value at t4
    pv = acc.portfolio_value(as_of=t4)
    assert pv == 1150 + 1 * 150  # 1300

    # Profit loss
    assert acc.profit_loss(as_of=t4) == pv - 1000  # 300

    # Holdings
    assert acc.holdings(as_of=t4) == {"AAPL": 1}

    # Transaction history length
    txs = acc.transaction_history()
    # 5 transactions: initial, deposit, withdraw, buy, sell
    assert len(txs) == 5

    # Check types of first and last transaction
    assert txs[0].type == "deposit"
    assert txs[-1].type == "sell"
    assert txs[-1].symbol == "AAPL"
    assert txs[-1].quantity == -1
    assert txs[-1].amount == 150.0


def test_transaction_history_filtering():
    acc = Account(500)
    t1 = BASE_TIME + timedelta(seconds=5)
    t2 = BASE_TIME + timedelta(seconds=10)
    t3 = BASE_TIME + timedelta(seconds=15)
    t4 = BASE_TIME + timedelta(seconds=20)
    acc.deposit(200, timestamp=t1)     # cash 700
    acc.withdraw(100, timestamp=t2)    # cash 600
    acc.buy("AAPL", 1, timestamp=t3)   # cost 150 -> cash 450
    acc.sell("AAPL", 1, timestamp=t4)  # proceeds 150 -> cash 600

    # Since t2 (withdraw) until t3 (buy) inclusive
    history_mid = acc.transaction_history(since=t2, until=t3)
    assert len(history_mid) == 2
    assert history_mid[0].type == "withdraw"
    assert history_mid[1].type == "buy"

    # All history
    all_history = acc.transaction_history()
    assert len(all_history) == 5  # initial + deposit + withdraw + buy + sell

    # Since None, until t2 should exclude later
    early_history = acc.transaction_history(until=t2)
    assert len(early_history) == 3  # initial, deposit, withdraw


def test_cash_balance_and_holdings_as_of():
    acc = Account(800)
    t1 = BASE_TIME + timedelta(seconds=5)
    acc.deposit(200, timestamp=t1)  # 1000
    t2 = BASE_TIME + timedelta(seconds=10)
    acc.withdraw(300, timestamp=t2)  # 700
    t3 = BASE_TIME + timedelta(seconds=15)
    acc.buy("AAPL", 2, timestamp=t3)  # cost 300 -> 400, holdings AAPL:2

    # Cash balance as of t2 (before buy)
    assert acc.cash_balance(as_of=t2) == 700
    # Cash balance as of t3 (after buy)
    assert acc.cash_balance(as_of=t3) == 400

    # Holdings as of t2 (no shares)
    assert acc.holdings(as_of=t2) == {}
    # Holdings as of t3 (after buy)
    assert acc.holdings(as_of=t3) == {"AAPL": 2}

    # Portfolio value as of t3
    assert acc.portfolio_value(as_of=t3) == 400 + 2 * 150  # 700

    # Portfolio value as of t2
    assert acc.portfolio_value(as_of=t2) == 700


def test_get_share_price_valid_and_invalid():
    assert get_share_price("AAPL") == 150
    assert get_share_price("MSFT") == 250
    assert get_share_price("GOOG") == 2800

    with pytest.raises(InvalidSymbolError):
        get_share_price("UNKNOWN")


def test_multiple_transactions_and_history_order():
    acc = Account(1000)
    times = [BASE_TIME + timedelta(seconds=i) for i in range(5)]
    acc.deposit(100, timestamp=times[0])
    acc.withdraw(50, timestamp=times[1])
    acc.buy("AAPL", 1, timestamp=times[2])
    acc.sell("AAPL", 1, timestamp=times[3])
    acc.deposit(200, timestamp=times[4])

    history = acc.transaction_history()
    assert len(history) == 6  # initial + 5 more
    # Ensure timestamps in chronological order
    for i in range(len(history) - 1):
        assert history[i].timestamp <= history[i + 1].timestamp

    # Check that the last transaction is the final deposit
    assert history[-1].type == "deposit"
    assert history[-1].amount == 200.0


@pytest.mark.parametrize(
    "initial_amount,action,expected_balance,expected_error",
    [
        (100, ("deposit", 50), 150, None),
        (100, ("withdraw", 200), 0, InsufficientFundsError),
        (0, ("deposit", 0), 0, ValueError),
        (0, ("withdraw", 0), 0, ValueError),
    ],
)
def test_parameterized_transactions(initial_amount, action, expected_balance, expected_error):
    acc = Account(initial_amount)
    action_type, amount = action
    t_time = BASE_TIME + timedelta(seconds=10)

    if action_type == "deposit":
        if expected_error:
            with pytest.raises(expected_error):
                acc.deposit(amount, timestamp=t_time)
        else:
            acc.deposit(amount, timestamp=t_time)
            assert acc.cash_balance(as_of=t_time) == expected_balance
    elif action_type == "withdraw":
        if expected_error:
            with pytest.raises(expected_error):
                acc.withdraw(amount, timestamp=t_time)
        else:
            acc.withdraw(amount, timestamp=t_time)
            assert acc.cash_balance(as_of=t_time) == expected_balance
    else:
        pytest.fail("Unknown action type in parameterized test")
