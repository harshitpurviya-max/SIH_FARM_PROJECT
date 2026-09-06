# Kisan Setu Demo Data Sources

## Real-source-derived identity

The seeded procurement-center names and locations are based on public e-NAM market listing identity for Madhya Pradesh markets, including Guna, Aron, Kumbhraj, Biaora, Kurawar, Narsinghgarh, Pachore, Vidisha, Ganj Basoda, Sironj, Khandwa, Harsud, Barwani, Anjad, and Sendhwa.

Source: [e-NAM](https://www.enam.gov.in/web/market-wise-data)

The source is used only for market identity and location naming. The project does not claim that the demo operational values are live government values.

## Synthetic demo data

The following values in `backend/seed_data.py` are synthetic and deterministic for SIH presentation reliability:

- Booking capacity and slot tonnage
- Operating hours
- Queue size and token order
- Demo farmer and officer accounts
- Quality inspections and moisture values
- Weighments
- Payment amounts, references, and states
- Required-document descriptions for the selected demo centers

No live market-price API is used. Payment amounts are synthetic demo values configured by `demo_price_per_tonne`.

## Why this split exists

A live external source could fail during a presentation and would not provide authoritative queue or transaction state. Kisan Setu therefore keeps backend procurement state as the source of truth while using clearly labeled synthetic records to make the demonstration repeatable.
