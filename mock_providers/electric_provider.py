"""Rocky Mountain Power Demo mock payment site."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from mock_providers.shared import BASE_STYLE, confirmation_timestamp, generate_confirmation_number

app = FastAPI(title="Rocky Mountain Power Demo")
PROVIDER_NAME = "Rocky Mountain Power Demo"


def page(title: str, body: str, accent: str = "#005bbb") -> str:
    return f"""
    <html><head><title>{title}</title><style>
    {BASE_STYLE}
    .brand {{ color: {accent}; }}
    .step {{ color: #666; font-size: 0.9rem; }}
    </style></head><body>
    <div class="container">
      <p class="step">Step: {title}</p>
      <h1 class="brand">{PROVIDER_NAME}</h1>
      {body}
    </div></body></html>
    """


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return page(
        "Home",
        '<p>Demo electric utility payment portal.</p><a href="/pay">Pay your bill</a>',
        accent="#005bbb",
    )


@app.get("/pay", response_class=HTMLResponse)
def pay_account() -> str:
    body = """
    <p>Pay your utility bill online.</p>
    <form method="post" action="/pay/amount">
      <label for="account_number">Account number</label>
      <input id="account_number" name="account_number" type="text" required />
      <button id="continue" type="submit">Continue</button>
    </form>
    """
    return page("Account", body)


@app.post("/pay/amount", response_class=HTMLResponse)
def pay_amount(account_number: str = Form(...)) -> str:
    body = f"""
    <p>Account ending in ...{account_number[-4:] if len(account_number) >= 4 else account_number}</p>
    <form method="post" action="/pay/review">
      <input type="hidden" name="account_number" value="{account_number}" />
      <label for="payment_amount">Payment amount</label>
      <input id="payment_amount" name="payment_amount" type="text" required />
      <button id="continue" type="submit">Continue</button>
    </form>
    """
    return page("Amount", body)


@app.post("/pay/review", response_class=HTMLResponse)
def pay_review(account_number: str = Form(...), payment_amount: str = Form(...)) -> str:
    body = f"""
    <p>Review your payment before submitting.</p>
    <ul>
      <li>Provider: {PROVIDER_NAME}</li>
      <li>Account: ****{account_number[-4:] if len(account_number) >= 4 else account_number}</li>
      <li>Amount: ${payment_amount}</li>
    </ul>
    <form method="post" action="/pay/confirm">
      <input type="hidden" name="account_number" value="{account_number}" />
      <input type="hidden" name="payment_amount" value="{payment_amount}" />
      <button id="submit_payment" type="submit">Submit Payment</button>
    </form>
    """
    return page("Review", body)


@app.post("/pay/confirm", response_class=HTMLResponse)
def pay_confirm(account_number: str = Form(...), payment_amount: str = Form(...)) -> str:
    try:
        amount = Decimal(payment_amount)
    except InvalidOperation:
        amount = Decimal("0.00")
    confirmation = generate_confirmation_number()
    body = f"""
    <p class="success">Payment successful!</p>
    <div class="meta">
      <p><strong>Provider:</strong> {PROVIDER_NAME}</p>
      <p><strong>Paid amount:</strong> ${amount:.2f}</p>
      <p><strong>Confirmation number:</strong> <span id="confirmation_number">{confirmation}</span></p>
      <p><strong>Timestamp:</strong> {confirmation_timestamp()}</p>
    </div>
    """
    return page("Confirmation", body, accent="#005bbb")
