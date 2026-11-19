# Setup

## Launching it

The BIS's statistics need no key and no account: its Data Portal API is
public. Launch the plugin and approve its one role, `data` (a data plugin).
It reads the API at once, and every six hours after.

Its settings, in the dashboard's Settings form:

- **Raw responses window** and **past the window** (the SDK's): how long the
  BIS's answers are kept in the plugin's storage, ten years by default, and
  whether they are then archived, kept or deleted.
- **Sample data**, on a deployment installed for development only: the
  BIS's answers recorded on 19 November 2026, committed with the plugin, in
  place of the API. For trying it offline.

## Its datasets

On the deployment's **Data sources** page (deployment admins), for each of
`<instance>:bis_cbpol` (the policy rates, as rates) and
`<instance>:bis_long_cpi` (the consumer prices, as the BIS's figures):

1. **License it.** Each dataset describes the BIS's terms in words and
   declares no licence: use with the BIS cited as the source, a translation
   marked unofficial, no endorsement implied, and no added charge for them
   in a commercial product. Record that in your licence's note. Until a
   licence is set, the lake keeps the rows and reads every use right
   restrictively.
2. **Entitle** each plugin that reads it, such as your reporting plugin, or
   a signal or pricing plugin reading the policy rates.
3. **Priority**, where another dataset also states the same values -- a
   central bank's own plugin for its policy rate: put the one your
   valuation should read first.

## The records

Each value is about a record your deployment holds, named by the BIS's key
for its series as a symbol at the source `bis`: `bis:WS_CBPOL.D.<economy>`
for a policy rate, `bis:WS_LONG_CPI.M.<economy>.628` for a price index. The
platform does not seed them yet, and the plugin never makes one: the
Datasets page's Records tab shows each as not held, reported missing, and
its values wait until your deployment holds the record.
