# Troubleshooting

## Connection

| What you see | What it means | What to do |
|---|---|---|
| **Not answering** | No check has reached the BIS's API: no network, a proxy, or the API down | Check the deployment's outbound access to stats.bis.org; the plugin tries again within six hours |
| **Answering**, with a warning | An earlier check worked; the last did not | Nothing, usually: the next check runs within six hours. The detail says what failed |

## Values and records

| What you see | What it means | What to do |
|---|---|---|
| **N records not held** | Your deployment holds no record for a series: the platform does not seed the BIS's yet | Nothing the plugin can do: it never makes a record. Its values are recorded once your deployment holds the record |
| A record **not carried** | A policy rate whose money-market day count the plugin does not hold | Its rates are read and not recorded; a later version may carry it |
| A value the plugin could not read | The API stated a value that is not a number, or in another unit | It is not recorded; the Datasets page lists it |

## Wants and licences

| What you see | What it means | What to do |
|---|---|---|
| A day declined, *source silent* | A weekend, a closed day, a month not published yet, or a period not come | Wait for the BIS's next update |
| A day declined, *beyond history* | A policy rate asked for before 1946 | Nothing: the BIS publishes none |
| A subject declined, *not covered* | A record this plugin does not record, or not yet held | Check the Records tab |
| Datasets: **Not licensed yet** | No deployment admin has licensed the dataset | Ask a deployment admin to license it on Data sources; the page says so within a minute |
