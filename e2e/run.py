"""`make e2e`: the plugin on the plugin harness of the runtime it pins
(contract 30), beside `reader`, a reporting plugin (e2e/reader.py), and the
harness's admin. Run from the repository's root by the Makefile, which
builds the image and writes the harness's plugins first; standard library
only.

1. The API unreachable: the plugin's hosts file sends the BIS's API nowhere,
   so its first check fails, and Connection says so -- "Not answering", the
   data role's word -- and records nothing.
2. Sample data on (a developer's setting, accepted on the harness): the
   plugin reads the committed answers -- the policy rates to 17 November
   2026, the consumer prices to September 2026 -- and asks the deployment
   for each series' record by the BIS's key as a symbol at `bis`. The
   platform seeds none yet, so each of the 91 series carried is reported
   missing, never minted, and its values wait: the lake holds the 91 misses
   and no row (e2e/expected.lake's `miss|bis|91`).
3. Parity: through the deployment's MCP, `read_connection` and
   `read_datasets` answer what the pages show, under the data role's names
   -- each source's latest period, each series with why it has no record --
   and core's `dashboard__list_datasets` lists `bis:bis_cbpol` and
   `bis:bis_long_cpi` as the catalogue declares them: push and pull, UTC's
   day, no calendar, a day and about a month.
4. Licensed and entitled at the Data sources page: the reader is entitled.
5. `store lake` is e2e/expected.lake.
6. A new container: it reads the answers again and records nothing; a new
   process asks for each record once more and reports each missing again
   (`miss|bis|182`), and reads its licences on start.
"""

import json
import os
import subprocess
import sys
import time

PROJECT = "bis-e2e"
LOG = ".e2e/runner.log"
COMPONENTS = ".e2e/components.log"
COMPOSE = ["docker", "compose", "-p", PROJECT, "-f", ".e2e/harness/compose.yaml",
           "-f", ".e2e/harness/plugins.yaml", "-f", "e2e/plugin.yaml"]
CBPOL = "bis:bis_cbpol"
CPI = "bis:bis_long_cpi"
#: The series carried that the committed answers' current ranges hold a
#: value for: each reported missing once a process.
MISSES = 98


class Failed(Exception):
    pass


def log(text):
    with open(LOG, "a", encoding="utf-8") as kept:
        kept.write(text + "\n")


def compose(*args, check=True, timeout=600):
    done = subprocess.run(COMPOSE + list(args), capture_output=True, text=True,
                          timeout=timeout)
    log(f"$ compose {' '.join(args)[:300]}\n{done.stdout[-4000:]}{done.stderr[-2000:]}")
    if check and done.returncode != 0:
        raise Failed(f"compose {' '.join(args)[:200]}: {(done.stdout + done.stderr).strip()[-600:]}")
    return done


def runner(*args, check=True):
    done = compose("run", "--rm", "-T", "runner", *args, check=check)
    return done.stdout if check else done


def must(condition, why):
    if not condition:
        raise Failed(why)


def until(seconds, attempt, what):
    deadline = time.monotonic() + seconds
    last = None
    while True:
        try:
            answer = attempt()
        except Failed as failed:
            answer, last = None, failed
        if answer:
            return answer
        if time.monotonic() > deadline:
            raise Failed(f"{what}, in {seconds} seconds" + (f": {last}" if last else ""))
        time.sleep(2)


def page(instance, level, path):
    said = runner("page", "--instance", instance, "--level", level, path)
    status, _, body = said.partition("\n")
    must(status.strip() == "200", f"{instance} {path} answered {said[-600:]}")
    return body


def call(tool, arguments=None):
    done = runner("mcp", "call", tool, json.dumps(arguments or {}), check=False)
    try:
        answer = json.loads(done.stdout)
    except ValueError:
        raise Failed(f"{tool}: no answer: {(done.stdout + done.stderr)[-400:]}")
    must(answer.get("outcome") in ("read", "unchanged"), f"{tool} answered {done.stdout[-700:]}")
    return answer["data"]


def store_lake():
    return compose("run", "--rm", "-T", "store", "lake").stdout


def sorted_lines(lines):
    return "\n".join(sorted(lines.strip().splitlines())) + "\n"


def run():
    started = time.time()
    compose("--profile", "runner", "down", "-v", "--remove-orphans", check=False)
    compose("up", "-d")
    runner("ready")
    runner("ready", "--instance", "reader")

    # 1. The API unreachable.
    page_said = runner("page", "--level", "admin", "/", "--until", "Not answering",
                       "--seconds", "90")
    must("URLError" in page_said or "Error" in page_said,
         f"step 1, Connection names why the API was not reached: {page_said[-500:]}")
    lake = store_lake()
    must("row|" not in lake, f"step 1, nothing recorded with the API unreachable: {lake}")

    # 2. Sample data: every series read, its record asked for and missed.
    runner("settings", "sample_data=true")
    runner("page", "--level", "admin", "/datasets?tab=records", "--until",
           'data-code="WS_CBPOL.D.CA"', "--seconds", "120")
    runner("page", "--level", "admin", "/?tab=sources", "--until", "Tue 17 Nov 2026",
           "--seconds", "60")
    until(90, lambda: f"miss|bis|{MISSES}" in store_lake(),
          f"step 2, the {MISSES} series' records were not reported missing")

    # 3. Parity through the deployment's MCP, and core's view of the catalogue.
    runner("grant", "--level", "admin")
    runner("mcp", "connect", "--covers", "deployment_admin", "--covers", "bis:admin")
    tools = runner("mcp", "list").split()
    read_connection = next((t for t in tools if t.endswith("read_connection")), "")
    read_datasets = next((t for t in tools if t.endswith("read_datasets")), "")
    must(read_connection and read_datasets, f"step 3, the plugin's two tools are listed: {tools}")
    connection = call(read_connection)
    rates, prices = connection["sources"]
    must(connection["mode"] == "Sample data" and connection["credentials"] == []
         and connection["sessions"] is None
         and rates["dataset"] == CBPOL and rates["last_release"] == "2026-11-17"
         and prices["dataset"] == CPI and prices["last_release"] == "2026-09-01",
         f"step 3, read_connection: {connection}")
    datasets = call(read_datasets)
    records = {r["code"]: r for r in datasets["records"]}
    missed = [r for r in records.values() if r["miss"] == "not held: reported missing"]
    must(len(missed) == MISSES and not any(r["instrument_id"] for r in records.values())
         and records["WS_CBPOL.D.TR"]["miss"] == "not carried"
         and records["WS_CBPOL.D.CA"]["source"] == "Bank of Canada",
         f"step 3, read_datasets names each series and why it has no record: {datasets['records'][:3]}")
    shown = page("bis", "admin", "/datasets?tab=records")
    must(all(f'data-code="{code}"' in shown for code in records),
         "step 3, Datasets shows what read_datasets answers")
    listed = {d["dataset"]: d for d in call("dashboard__list_datasets")["datasets"]}
    for dataset, cadence, kind in ((CBPOL, 86400, "meridian.v1.Rate"),
                                   (CPI, 30 * 86400, "meridian.v1.DerivedSeries")):
        entry = listed.get(dataset, {}).get("catalogue_entry", {})
        must(entry.get("modes") == ["push", "pull"] and entry.get("day_time_zone") == "UTC"
             and entry.get("cadence") == cadence and not entry.get("calendar_id")
             and entry.get("data_types") == [kind],
             f"step 3, core lists {dataset} as declared: {listed.get(dataset)}")

    # 4. Licensed and entitled.
    for dataset, what in ((CBPOL, "the policy rates"), (CPI, "the long consumer prices")):
        runner("licence", dataset, "kept=true", "retention_days=0", "derived_use=true",
               "display=true", "personal_use=false",
               f"note=The BIS's {what}: use citing the BIS, no added charge.")
        runner("entitle", "--instance", "reader", dataset, f"note=The e2e's reader may read {what}.")
    runner("grant", "--instance", "reader", "--level", "read")

    # 5. The lake.
    got = sorted_lines(store_lake())
    with open(".e2e/lake", "w", encoding="utf-8") as kept:
        kept.write(got)
    with open("e2e/expected.lake", encoding="utf-8") as held:
        expected = held.read()
    if got != expected:
        diff = subprocess.run(["diff", "-u", "e2e/expected.lake", ".e2e/lake"], capture_output=True, text=True)
        raise Failed(f"step 5, the lake is not e2e/expected.lake:\n{diff.stdout[-3000:]}")

    # 6. A new container records nothing, and reports each record missing again.
    compose("up", "-d", "--no-deps", "--force-recreate", "bis")
    runner("ready")
    until(120, lambda: "Tue 17 Nov 2026" in page("bis", "admin", "/?tab=sources"),
          "step 6, the new container did not read the answers again")
    until(90, lambda: f"miss|bis|{2 * MISSES}" in store_lake(),
          "step 6, the new container did not ask for each record again")
    time.sleep(5)
    again = sorted_lines(store_lake())
    must(again == got.replace(f"miss|bis|{MISSES}\n", f"miss|bis|{2 * MISSES}\n"),
         "step 6, the new container recorded something:\n"
         + subprocess.run(["diff", "-u", "-", ".e2e/lake"], input=again, capture_output=True, text=True).stdout[-2000:])
    until(90, lambda: all(s["licensed"] for s in call(read_datasets)["served"]),
          "step 6, the new container never read its datasets' licences")

    print(f"e2e OK in {int(time.time() - started)}s on the plugin harness: the BIS's API unreachable "
          f"said on Connection, nothing recorded; sample data's policy rates to 17 November 2026 and "
          f"consumer prices to September 2026 read, each of the {MISSES} series carried asked of "
          f"the deployment by its key at bis and, held by no record, reported missing and never "
          f"minted; read_connection and read_datasets answering what the pages show, and core "
          f"listing {CBPOL} and {CPI} as declared; licensed and entitled; `store lake` as "
          f"e2e/expected.lake; and a new container recording nothing, its records asked again and "
          f"its licences read on start")


def main():
    os.makedirs(".e2e", exist_ok=True)
    open(LOG, "w").close()
    try:
        run()
    except (Failed, subprocess.TimeoutExpired, KeyError, ValueError, IndexError, TypeError) as failed:
        with open(COMPONENTS, "a", encoding="utf-8") as kept:
            kept.write(compose("logs", "--no-color", check=False).stdout)
        # The lake as it stood, for the artifact.
        if os.path.exists(".e2e/lake"):
            with open(".e2e/lake", encoding="utf-8") as held, open(".e2e/lake.log", "w", encoding="utf-8") as kept:
                kept.write(held.read())
        compose("--profile", "runner", "down", "-v", "--remove-orphans", check=False)
        print(f"e2e FAILED: {failed}; the runner's log is in {LOG}, the components' in {COMPONENTS}",
              file=sys.stderr)
        return 1
    compose("--profile", "runner", "down", "-v", "--remove-orphans", check=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
