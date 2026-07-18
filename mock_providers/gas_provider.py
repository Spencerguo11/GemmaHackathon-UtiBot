"""Dominion Energy Demo mock payment site."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse

from mock_providers.shared import confirmation_timestamp, generate_confirmation_number

app = FastAPI(title="Dominion Energy Demo")
PROVIDER_NAME = "Dominion Energy Demo"
DEMO_USERNAME = "demo"
DEMO_PASSWORD = "demo123"


def page(title: str, body: str) -> str:
    return f"""
    <html><head><title>{title}</title><style>
    body {{ font-family: Arial, sans-serif; background: #102a43; color: white; margin: 0; }}
    .panel {{ max-width: 760px; margin: 48px auto; background: #243b53; padding: 28px; border-radius: 4px; }}
    h1 {{ color: #f0b429; text-transform: uppercase; letter-spacing: 1px; }}
    label {{ display:block; margin-top: 14px; }}
    input, select, button {{ width: 100%; box-sizing: border-box; margin-top: 8px; padding: 10px; }}
    button {{ background: #f0b429; color: #102a43; border: 0; font-weight: bold; }}
    .success {{ color: #3ecf8e; font-size: 1.2rem; }}
    </style></head><body><div class="panel"><h1>{PROVIDER_NAME}</h1>{body}</div></body></html>
    """


@app.get("/pay", response_class=HTMLResponse)
def login_page() -> str:
    body = """
    <p>Mock login required. Demo credentials: demo / demo123</p>
    <form method="post" action="/pay/accounts">
      <label for="username">Username</label>
      <input id="username" name="username" type="text" required />
      <label for="password">Password</label>
      <input id="password" name="password" type="password" required />
      <button id="login" type="submit">Sign In</button>
    </form>
    """
    return page("Login", body)


@app.post("/pay/accounts", response_class=HTMLResponse)
def account_selection(username: str = Form(...), password: str = Form(...)) -> str:
    if username != DEMO_USERNAME or password != DEMO_PASSWORD:
        return page("Login", "<p>Invalid demo credentials.</p><a href='/pay'>Try again</a>")
    body = """
    <p>Select an account to pay.</p>
    <form method="post" action="/pay/amount">
      <label for="account_number">Account</label>
      <select id="account_number" name="account_number">
        <option value="5566778899">Gas Account ****8899</option>
        <option value="1122334455">Gas Account ****4455</option>
      </select>
      <button id="continue" type="submit">Continue</button>
    </form>
    """
    return page("Accounts", body)


@app.post("/pay/amount", response_class=HTMLResponse)
def amount_page(account_number: str = Form(...)) -> str:
    body = f"""
    <form method="post" action="/pay/review">
      <input type="hidden" name="account_number" value="{account_number}" />
      <label for="payment_amount">Payment amount</label>
      <input id="payment_amount" name="payment_amount" type="text" required />
      <button id="continue" type="submit">Continue</button>
    </form>
    """
    return page("Amount", body)


@app.post("/pay/review", response_class=HTMLResponse)
def review_page(account_number: str = Form(...), payment_amount: str = Form(...)) -> str:
    body = f"""
    <p>Review payment for account ****{account_number[-4:]}.</p>
    <form method="post" action="/pay/confirm">
      <input type="hidden" name="account_number" value="{account_number}" />
      <input type="hidden" name="payment_amount" value="{payment_amount}" />
      <button id="submit_payment" type="submit">Submit Payment</button>
    </form>
    """
    return page("Review", body)


@app.post("/pay/confirm", response_class=HTMLResponse)
def confirm_page(account_number: str = Form(...), payment_amount: str = Form(...)) -> str:
    try:
        amount = Decimal(payment_amount)
    except InvalidOperation:
        amount = Decimal("0.00")
    confirmation = generate_confirmation_number()
    body = f"""
    <p class="success">Payment successful!</p>
    <p><strong>Provider:</strong> {PROVIDER_NAME}</p>
    <p><strong>Paid amount:</strong> ${amount:.2f}</p>
    <p><strong>Confirmation number:</strong> <span id="confirmation_number">{confirmation}</span></p>
    <p><strong>Timestamp:</strong> {confirmation_timestamp()}</p>
    """
    return page("Confirmation", body)
