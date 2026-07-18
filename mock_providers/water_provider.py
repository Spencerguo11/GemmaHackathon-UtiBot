"""City Water Demo mock payment site."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse

from mock_providers.shared import confirmation_timestamp, generate_confirmation_number

app = FastAPI(title="City Water Demo")
PROVIDER_NAME = "City Water Demo"


def page(title: str, body: str) -> str:
    return f"""
    <html><head><title>{title}</title><style>
    body {{ font-family: 'Trebuchet MS', sans-serif; background: linear-gradient(180deg,#dff6ff,#ffffff); margin:0; }}
    .card {{ max-width: 680px; margin: 40px auto; background: white; border: 2px solid #0096c7; border-radius: 16px; padding: 24px; }}
    h1 {{ color: #0096c7; }}
    label {{ display:block; margin-top: 12px; color:#023047; }}
    input, button {{ margin-top: 8px; padding: 10px; width: 100%; box-sizing: border-box; }}
    button {{ background: #0096c7; color: white; border: 0; border-radius: 999px; }}
    .success {{ color: #2a9d8f; font-size: 1.2rem; }}
    </style></head><body><div class="card"><h1>{PROVIDER_NAME}</h1>{body}</div></body></html>
    """


@app.get("/pay", response_class=HTMLResponse)
def account_page() -> str:
    body = """
    <form method="post" action="/pay/amount">
      <label for="account_number">Account number</label>
      <input id="account_number" name="account_number" type="text" required />
      <label for="billing_zip">Billing ZIP code</label>
      <input id="billing_zip" name="billing_zip" type="text" required />
      <button id="continue" type="submit">Continue</button>
    </form>
    """
    return page("Account", body)


@app.post("/pay/amount", response_class=HTMLResponse)
def amount_page(account_number: str = Form(...), billing_zip: str = Form(...)) -> str:
    body = f"""
    <form method="post" action="/pay/review">
      <input type="hidden" name="account_number" value="{account_number}" />
      <input type="hidden" name="billing_zip" value="{billing_zip}" />
      <label for="payment_amount">Payment amount</label>
      <input id="payment_amount" name="payment_amount" type="text" required />
      <button id="continue" type="submit">Continue</button>
    </form>
    """
    return page("Amount", body)


@app.post("/pay/review", response_class=HTMLResponse)
def review_page(
    account_number: str = Form(...),
    billing_zip: str = Form(...),
    payment_amount: str = Form(...),
) -> str:
    body = f"""
    <p>Review water bill payment for ZIP {billing_zip}.</p>
    <form method="post" action="/pay/confirm">
      <input type="hidden" name="account_number" value="{account_number}" />
      <input type="hidden" name="billing_zip" value="{billing_zip}" />
      <input type="hidden" name="payment_amount" value="{payment_amount}" />
      <button id="submit_payment" type="submit">Submit Payment</button>
    </form>
    """
    return page("Review", body)


@app.post("/pay/confirm", response_class=HTMLResponse)
def confirm_page(
    account_number: str = Form(...),
    billing_zip: str = Form(...),
    payment_amount: str = Form(...),
) -> str:
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
