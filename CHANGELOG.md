# Changelog

## 0.1.2

SDK 0.37.0: waits for a lost sidecar; its storage is read once registered,
on an instance run as shards or with a standby pod the shard's own folder.

## 0.1.1

Seven more economies' policy rates, each with a cited day count (the
product owner's item 177, 2026-11-19): Iceland, Serbia, Indonesia, Morocco
and China on actual/360, simple; Türkiye on actual/365, simple (the simple
rate, never the compounded one); the Philippines on actual/360, simple, the
basis of its PHIREF benchmark. Each is cited in series.py. China keeps 360
although a June 2026 PBoC draft would move it to 365 (366 in leap years),
until a final rule is issued. Kuwait, Saudi Arabia and North Macedonia stay
not carried: no central-bank or benchmark source states their day count.

## 0.1.0

On open-meridian 0.36.0, contract 30, on core aae501d's harness. The
product owner's items 128 and 140 (2026-11-19): Tier 1. The dataset keys,
the records' symbols and the source `bis` are proposed here, the product
owner's to approve.

- **Central bank policy rates, `bis_cbpol`.** The BIS's `WS_CBPOL`
  dataflow, every economy's policy rate, daily: each day's rate a `fixing`,
  in per cent, as the BIS writes it, against the economy's `interest_rate`
  record, named by the BIS's key as a symbol at `bis`
  (`WS_CBPOL.D.CA`). Its convention is the plugin's statement -- simple,
  on the currency's money-market day count (series.py) -- since the BIS
  states none; an economy whose day count the plugin does not hold (ten
  today, among them China, Indonesia and Türkiye) is read and not recorded.
  Pushed every six hours from the last month; any past day from 1946 pulled
  on a want.
- **Long consumer prices, `bis_long_cpi`.** The BIS's `WS_LONG_CPI`
  dataflow, its index levels based 2010 = 100, monthly: each month's level
  the BIS's figure, a `DerivedSeries` named `level` marked `published_by`
  the BIS (ruling 136), against the economy's `index` record
  (`WS_LONG_CPI.M.CA.628` at `bis`), valid the whole month. Pushed every six
  hours from the last thirteen months; any past month pulled on a want.
- **No record minted.** The platform seeds none of these records yet: each
  is reported missing, and its values wait until the deployment holds it.
- **No published time.** The BIS states none for a value, so none is
  recorded; the feed delay is not reported.
- **Terms in words** (`declared.BIS_TERMS`): the BIS cited, a translation
  marked unofficial, no endorsement implied, no added charge in a commercial
  product, no other use; the API as is.
- **Pages:** the data role's Connection (with Sources) and Datasets (with
  Records), from the SDK's templates.
- **Sample data:** the BIS's answers as received on 2026-11-19.
