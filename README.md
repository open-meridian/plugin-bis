# meridian-bis

The Bank for International Settlements' public statistics for
[Open Meridian](https://open-meridian.com): an Open Meridian plugin that puts
the BIS's
central bank policy rates (its `WS_CBPOL` dataflow) into a
deployment's lake, each economy's policy rate each day, as rates; and its
long series on consumer prices (`WS_LONG_CPI`), each
economy's index level each month, as the BIS's own figures. It reads the
BIS's Data Portal API (SDMX), and holds the `data` role, a data plugin. This
is release 0.1.1. How to set it up and use it is in [docs/](docs/README.md);
how a plugin like it is built is documented at
[open-meridian.dev](https://open-meridian.dev).

It is built on the SDK it pins, `open-meridian==0.37.1`, which declares
contract 30 (each dataset's terms in words and how a gap in it is
recovered; its work one class for its role, registered with `meridian.run`).

## What it records

- **`<instance>:bis_cbpol`:** rates (`meridian.v1.Rate`), each day's policy
  rate a `fixing` in per cent, pushed every six hours from the last month,
  any past day from 1 January 1946 pulled when the lake wants it; UTC's day;
  no calendar. Each economy's rate is about its `interest_rate` record,
  asked of the deployment by the BIS's key for the series as a symbol at
  `bis` (`WS_CBPOL.D.CA`, Canada's).
- **Each rate's convention.** The BIS states "per cent per year" and no day
  count; the lake needs one. The plugin states each rate simple, on its
  currency's money-market day count (actual/360 for the dollar, the euro and
  the Swiss franc; actual/365 for sterling, the Canadian dollar and the yen;
  business/252, compounded, for Brazil), said on the Datasets page as the
  plugin's statement. An economy whose day count it does not hold is read
  and not recorded.
- **`<instance>:bis_long_cpi`:** the BIS's figures
  (`meridian.v1.DerivedSeries`, `published_by` the BIS), each month's
  consumer price level named `level`, based 2010 = 100, valid the whole
  month, pushed every six hours from the last thirteen months, any past
  month pulled when the lake wants it. Each economy's index is about its
  `index` record, `WS_LONG_CPI.M.CA.628` at `bis`.
- **No record minted.** The platform seeds none of these records yet: until
  a deployment holds one, it is reported missing, and its values wait.
- **Exact.** Every value is made a decimal from the text the API wrote; a
  value the BIS marks missing is no value, never a zero.
- **No published time.** The BIS states none for a value, so none is
  recorded rather than a wrong one.
- **Every answer kept** as received, in the storage the deployment grants,
  and named by each row it was first read into.

Its pages, under Manage alone, are the data role's, the same on every data
plugin, and show how it reaches the BIS and what it serves, never a value:
**Connection** (`read_connection`, "No key needed", "Does not stream", and
its Sources) and **Datasets** (`read_datasets`, saying whether a deployment
admin has licensed each dataset, with its Records), each the same through
the deployment's MCP.

## Deploying it

On a deployment, with the `meridian` CLI connected (`meridian connect`):

    meridian plugin upload            # from this directory: builds the image, sends it and its declaration
    meridian plugin launch bis        # a deployment admin approves its one role, data

It needs no key and no account. Then, on the deployment's Data sources
page, a deployment admin licenses `bis:bis_cbpol` and `bis:bis_long_cpi`
and entitles the plugins that read them ([docs/setup.md](docs/setup.md)).
Until the deployment holds each series' record, its values wait.

## Checking it

    make ci-local                                  # lint, tests, plugin check, image, e2e: the pre-push gate
    make preview SHOTS=<dir>                       # each page in a browser with the kit, at 375, 582 and 1280 px

`make e2e` runs it on core's plugin harness beside a reading plugin: the
BIS's API unreachable at first, then sample data reading the committed
answers, every series' record asked of the deployment and, held by none,
reported missing and never minted, both tools answering what the pages
show, the catalogue as declared, and a new container recording nothing.

**The data suite.** `tests/test_suite.py` runs the SDK's suite on the
plugin's own conversion, and it passes: `records-a-derived-series` on the
consumer prices, `a-same-day-revision` on the policy rates, and the cases
every data plugin answers, `reads-its-datasets-licences` among them; every
other case is about what the BIS never states here -- a price, a trade, a
quote, a fixing's volume and percentiles, a curve, a calendar, a published
time -- and is not presented, with why.

## The terms, summarised

Not legal advice; read the BIS's own words before relying on them.

- **Use with the BIS cited.** The BIS allows use of its statistics provided
  the BIS is cited as the source, a translation is marked unofficial, and no
  endorsement is implied; including them in a commercial product must not
  add a charge for them to its users; no other use is permitted
  ([legal](https://data.bis.org/help/legal)). Each dataset says so in words
  (contract 30, ruling 1032: `declared.BIS_TERMS`), shown on Data sources,
  and declares no licence. A deployment's licence on its Data sources page
  is the one enforced; until one is set, the lake keeps the rows and reads
  every use right restrictively. A gap in either dataset is asked again of
  the API (`gap_recovery` `backfill`).
- **No endorsement.** This project is not affiliated with or endorsed by the
  Bank for International Settlements.

## Licence

Apache-2.0 (LICENSE, NOTICE). The BIS's answers under `src/bis/responses/`
are its policy rates and long consumer prices as received on 2026-11-19.
