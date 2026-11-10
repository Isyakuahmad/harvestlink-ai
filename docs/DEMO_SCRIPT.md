# HarvestLink AI — repeatable competition demo

This walkthrough uses **fictional sample accounts and sample produce data**. It is for demonstration only; it is not evidence of live farmer supply, buyer demand, prices, logistics capacity or a completed real-world delivery.

## 1. Start the application

Follow [DEPLOYMENT.md](DEPLOYMENT.md), or run the API locally using the repository's development instructions. Apply migrations with:

```bash
alembic upgrade head
uvicorn app.main:app --reload
```

Open `http://localhost:8000/dashboard`. API reference: `http://localhost:8000/docs`.

## 2. Create the demo administrator

Set `ADMIN_EMAILS=admin@example.com` before starting the API. Use the API docs to call `POST /api/v1/auth/register` with:

- Email: `admin@example.com`
- Name: `Demo Administrator`
- Password: `DemoOnly-ChangeThis-123!`

Sign in to `/dashboard` as this administrator. Keep this password for local demo use only; replace it for any shared environment.

## 3. Register the marketplace participants

Use the dashboard registration form to create:

| Role | Sample email | Sample organisation / details |
|---|---|---|
| Farmer | `farmer@example.com` | Amina Demo Farm |
| Buyer | `buyer@example.com` | Northstar Foods (buyer type: wholesaler in the dashboard demo) |
| Logistics provider | `carrier@example.com` | Demo Haulage; service areas Nasarawa and Abuja; mode truck |

Use the same demo-only password for each account. Sign in as administrator and approve the pending user verification cases. These are fictional demo identities; do not treat their approval as a real KYC check.

## 4. Create supply and demand

Sign in as the farmer and submit this sample produce offer:

- Crop: white sesame
- Quantity: 3,000 kg
- Quality: clean, dry, machine-sorted sample lot
- Location: Lafia, Nasarawa State
- Availability: choose a future date
- Asking price: optional; leave blank if not using a verified market quote

Sign in as administrator and approve the farmer's produce listing.

Sign in as the buyer and create this requirement:

- Crop: white sesame
- Minimum quantity: 1 tonne
- Maximum quantity: 5 tonnes
- Unit: tonne
- Destination/location: Nasarawa State
- Quality: clean, dry sesame

The buyer workspace should show the eligible, approved farmer listing with its match score and reasons.

## 5. Complete buyer–farmer negotiation

1. Buyer selects **Express interest** on the match.
2. Farmer opens **Buyer interests** and selects **Accept**.
3. Buyer proposes terms, for example 2 tonnes at NGN 1,500,000 per tonne, delivered to an Abuja warehouse on a mutually agreed future date.
4. Farmer reviews the proposal and selects **Confirm terms**.
5. Both parties can now view the transaction and its event history. An unrelated account should not be able to view it.

The price and delivery details above are illustrative negotiation inputs, not a market quotation or recommended sesame price.

## 6. Request and confirm transport

1. Buyer or farmer selects **Request transport quotes** on the confirmed transaction.
2. Sign in as the verified logistics provider and open **Logistics quotation requests**.
3. Provider submits an illustrative quote, e.g. NGN 250,000 with a two-day estimated transit time.
4. Buyer and farmer each approve the quote from their transaction view.
5. Provider selects **Confirm booking** only after both approvals are recorded.

The request closes after one provider confirms. Other quotations cannot create a second booking against the same request.

## 7. Record outcome

A buyer or farmer can record a delivery report with a short evidence note, or report an issue. A delivery report is a participant-submitted statement; it is not independent proof of delivery. For a live pilot, attach independently checkable delivery evidence and verify the physical outcome outside this demo.

## Expected demonstration

The demo should show a traceable journey:

**approved farmer supply → buyer match → buyer interest → farmer response → proposed terms → farmer confirmation → logistics quote → both-party approval → provider booking confirmation → delivery report or issue record.**

All displayed sample values and accounts are fictional. No payment, escrow, real carrier dispatch, live WhatsApp messaging or export clearance is performed by this MVP.
