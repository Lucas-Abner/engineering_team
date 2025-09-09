from __future__ import annotations

import gradio as gr
import pandas as pd
from datetime import datetime
from accounts import Account, InsufficientFundsError, InsufficientHoldingsError, InvalidSymbolError, InvalidQuantityError

# Global account state (None until created)
account: Account | None = None

# --------------------------------------------------------------------
# Helper functions that perform actions on the account
# --------------------------------------------------------------------
def create_account(initial_deposit: float):
    global account
    try:
        account = Account(initial_deposit)
        return f"✅ Account created with an initial deposit of ${initial_deposit:,.2f}"
    except Exception as e:
        return f"❌ Error creating account: {e}"

def deposit(amount: float):
    global account
    if account is None:
        return "❌ No account exists. Please create an account first."
    try:
        account.deposit(amount)
        return f"✅ Deposited ${amount:,.2f}. New cash balance: ${account.cash_balance():,.2f}"
    except Exception as e:
        return f"❌ Error depositing: {e}"

def withdraw(amount: float):
    global account
    if account is None:
        return "❌ No account exists. Please create an account first."
    try:
        account.withdraw(amount)
        return f"✅ Withdrew ${amount:,.2f}. New cash balance: ${account.cash_balance():,.2f}"
    except InsufficientFundsError:
        return f"❌ Insufficient cash for withdrawal of ${amount:,.2f}."
    except Exception as e:
        return f"❌ Error withdrawing: {e}"

def buy(symbol: str, quantity: float):
    global account
    if account is None:
        return "❌ No account exists. Please create an account first."
    try:
        account.buy(symbol, quantity)
        holdings = account.holdings()
        holdings_str = ", ".join([f"{k}: {v:.2f}" for k, v in holdings.items()]) or "None"
        return (
            f"✅ Bought {quantity} shares of {symbol} at ${account._initial_deposit:,.2f}. "
            f"New cash balance: ${account.cash_balance():,.2f}. "
            f"Holdings: {holdings_str}"
        )
    except (InsufficientFundsError, InvalidSymbolError, InvalidQuantityError) as e:
        return f"❌ Error buying: {e}"
    except Exception as e:
        return f"❌ Unexpected error: {e}"

def sell(symbol: str, quantity: float):
    global account
    if account is None:
        return "❌ No account exists. Please create an account first."
    try:
        account.sell(symbol, quantity)
        holdings = account.holdings()
        holdings_str = ", ".join([f"{k}: {v:.2f}" for k, v in holdings.items()]) or "None"
        return (
            f"✅ Sold {quantity} shares of {symbol}. "
            f"New cash balance: ${account.cash_balance():,.2f}. "
            f"Holdings: {holdings_str}"
        )
    except (InsufficientHoldingsError, InvalidQuantityError, InvalidSymbolError) as e:
        return f"❌ Error selling: {e}"
    except Exception as e:
        return f"❌ Unexpected error: {e}"

def view_portfolio():
    global account
    if account is None:
        return "❌ No account exists. Please create an account first.", "", "", ""
    cash = account.cash_balance()
    holdings_dict = account.holdings()
    portfolio_val = account.portfolio_value()
    pnl = account.profit_loss()
    holdings_df = pd.DataFrame(
        [
            {"Symbol": sym, "Quantity": qty, "Market Value": qty * account._latest_timestamp() and account._latest_timestamp() or datetime.utcnow()}
            for sym, qty in holdings_dict.items()
        ]
    )
    holdings_str = "\n".join([f"{sym}: {qty:.2f}" for sym, qty in holdings_dict.items()]) or "None"
    return (
        f"${cash:,.2f}",
        holdings_str,
        f"${portfolio_val:,.2f}",
        f"${pnl:,.2f}"
    )

def transaction_history():
    global account
    if account is None:
        return pd.DataFrame(columns=["Timestamp", "Type", "Symbol", "Quantity", "Price per Share", "Total Amount"])
    tx_list = account.transaction_history()
    data = {
        "Timestamp": [tx.timestamp.strftime("%Y-%m-%d %H:%M:%S") for tx in tx_list],
        "Type": [tx.type for tx in tx_list],
        "Symbol": [tx.symbol or "" for tx in tx_list],
        "Quantity": [tx.quantity for tx in tx_list],
        "Price per Share": [tx.price_per_share for tx in tx_list],
        "Total Amount": [tx.total_amount for tx in tx_list],
    }
    return pd.DataFrame(data)

# --------------------------------------------------------------------
# Gradio UI definition
# --------------------------------------------------------------------
with gr.Blocks() as demo:
    gr.HTML("<h1>Trading Simulator Dashboard</h1>")

    with gr.Tab("Create Account"):
        init_deposit = gr.Number(label="Initial Deposit ($)", precision=2)
        create_btn = gr.Button("Create Account")
        create_msg = gr.Textbox(label="Status", interactive=False)

        create_btn.click(
            fn=create_account,
            inputs=[init_deposit],
            outputs=[create_msg]
        )

    with gr.Tab("Deposit"):
        deposit_amount = gr.Number(label="Deposit Amount ($)", precision=2)
        deposit_btn = gr.Button("Deposit")
        deposit_msg = gr.Textbox(label="Status", interactive=False)

        deposit_btn.click(
            fn=deposit,
            inputs=[deposit_amount],
            outputs=[deposit_msg]
        )

    with gr.Tab("Withdraw"):
        withdraw_amount = gr.Number(label="Withdrawal Amount ($)", precision=2)
        withdraw_btn = gr.Button("Withdraw")
        withdraw_msg = gr.Textbox(label="Status", interactive=False)

        withdraw_btn.click(
            fn=withdraw,
            inputs=[withdraw_amount],
            outputs=[withdraw_msg]
        )

    with gr.Tab("Buy Shares"):
        buy_symbol = gr.Dropdown(choices=["AAPL", "TSLA", "GOOGL"], label="Stock Symbol")
        buy_qty = gr.Number(label="Quantity", precision=2)
        buy_btn = gr.Button("Buy")
        buy_msg = gr.Textbox(label="Status", interactive=False)

        buy_btn.click(
            fn=buy,
            inputs=[buy_symbol, buy_qty],
            outputs=[buy_msg]
        )

    with gr.Tab("Sell Shares"):
        sell_symbol = gr.Dropdown(choices=["AAPL", "TSLA", "GOOGL"], label="Stock Symbol")
        sell_qty = gr.Number(label="Quantity", precision=2)
        sell_btn = gr.Button("Sell")
        sell_msg = gr.Textbox(label="Status", interactive=False)

        sell_btn.click(
            fn=sell,
            inputs=[sell_symbol, sell_qty],
            outputs=[sell_msg]
        )

    with gr.Tab("Portfolio Overview"):
        view_btn = gr.Button("View Portfolio")
        cash_output = gr.Textbox(label="Cash Balance ($)", interactive=False)
        holdings_output = gr.Textbox(label="Holdings", interactive=False)
        portfolio_val_output = gr.Textbox(label="Portfolio Value ($)", interactive=False)
        pnl_output = gr.Textbox(label="Profit/Loss ($)", interactive=False)

        view_btn.click(
            fn=view_portfolio,
            inputs=[],
            outputs=[cash_output, holdings_output, portfolio_val_output, pnl_output]
        )

    with gr.Tab("Transaction History"):
        history_btn = gr.Button("Show History")
        history_output = gr.Dataframe(headers=["Timestamp", "Type", "Symbol", "Quantity", "Price per Share", "Total Amount"], datatype="string", interactive=False)

        history_btn.click(
            fn=transaction_history,
            inputs=[],
            outputs=[history_output]
        )

# --------------------------------------------------------------------
# Launch the app
# --------------------------------------------------------------------
demo.queue()
if __name__ == "__main__":
    demo.launch()