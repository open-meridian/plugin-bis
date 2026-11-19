# Overview

The Bank for International Settlements (BIS) publishes two series this
plugin puts into your deployment's lake:

- **Central bank policy rates** (`<instance>:bis_cbpol`): each economy's
  policy rate, daily, as the BIS compiles it from each central bank -- the
  Bank of Canada's target for the overnight rate, the Bank of England's Bank
  Rate, the Federal Reserve's target midpoint, the euro area's deposit
  facility rate and some thirty more. Each day's rate is recorded as a
  **fixing**, in per cent.
- **Long series on consumer prices** (`<instance>:bis_long_cpi`): each
  economy's consumer price index, monthly, based 2010 = 100. Each month's
  level is recorded as **the BIS's figure** (a derived series marked as the
  BIS's), valid for the whole month.

It reads the BIS's public Data Portal API: no key, no account. It checks
for new values every six hours, and reads any past day or month the lake
asks for.

## What it records

- **Each value as the BIS writes it,** made an exact decimal from its text.
  A value the BIS marks missing -- a weekend, a closed day, a month not yet
  published -- is no value, never a zero.
- **Against your deployment's records.** Each policy rate is about one
  reference rate record and each price index about one index record, asked
  of your deployment by the BIS's key for the series (for example
  `WS_CBPOL.D.CA` for Canada's policy rate). The plugin never makes a
  record: one your deployment does not hold is reported missing, and its
  values wait until it does.
- **Each policy rate's convention.** The BIS states a policy rate in per
  cent per year and no day count. The lake needs one, so the plugin states
  each rate simple, on its currency's money-market day count -- actual/360
  for the US dollar, the euro and the Swiss franc, actual/365 for sterling,
  the Canadian dollar and the yen, business/252 for Brazil. An economy whose
  day count the plugin does not hold is read and not recorded; the Datasets
  page says which.
- **No published time.** The BIS states none for a value, so none is
  recorded rather than a wrong one.
- **Every answer kept** as received, in the storage your deployment grants.

## What it never does

It records no price, no trade and no forecast, and shows no value on its
pages: those are the reading plugins'. It holds no account and uses no key.
