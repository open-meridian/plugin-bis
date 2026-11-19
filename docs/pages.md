# Pages

Both pages are the data role's, the same on every data plugin, under
**Manage**, for the plugin's admins. Neither shows a rate or a level. Each is
also a read tool on the deployment's MCP, answering what the page shows,
under the same names on every data plugin.

## Connection (`read_connection`)

How the plugin reaches the BIS, and how the last check went:

- the head's status: answering, checking, not answering, or records not
  held;
- **Key:** the mode (Live or Sample data), "No key needed", what the BIS
  serves, and where it reads from;
- **Limits and use:** the limits it keeps (the BIS states none; one request
  at a time, at most one every two seconds, a check every six hours), the
  requests made, the last check and error, and how many answers are kept;
- **Stream:** it does not stream;
- **Sources**, a tab of its own: one line per source -- the policy rates and
  the consumer prices -- with its state, the latest period published and its
  calls; its details say where it reads and how far its history reaches.

## Datasets (`read_datasets`)

What the plugin serves the lake:

- **Served**: its two datasets as declared, whether a deployment admin has
  licensed each, what it recorded and declined; the wants it answered and
  the ones it keeps current; the subjects it reads;
- **Records**, a tab of its own: each series the BIS publishes -- its key,
  its name and central bank, what it is recorded as, its convention, and
  your deployment's record for it or why there is none -- searched and paged
  to fit one screen, under the attribution the BIS's terms ask for.
