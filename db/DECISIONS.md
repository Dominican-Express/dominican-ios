# Architecture decision records

Each section is one decision: the context, what we chose, what we rejected and
why, the evidence, and what it costs. Numbers come from measurements recorded
in [README.es.md](README.es.md) (Spanish) and [DATASET.md](DATASET.md); where there
is no measurement we write "not measured". SurrealDB concepts used here are
explained in [FUNDAMENTALS.md](FUNDAMENTALS.md); the critical assessment is in
[REFLECTION.md](REFLECTION.md).

| # | Decision |
|---|---|
| 1 | SurrealDB instead of MongoDB, Cassandra, Neo4j, ArangoDB or PostgreSQL |
| 2 | No Java backend: the API lives inside the database |
| 3 | The balance is derived from an append-only ledger |
| 4 | `transfer` duplicates the ledger as a graph edge |
| 5 | Authorization is a graph traversal |
| 6 | PIN step-up through an endpoint, not a function or an event |
| 7 | Two-speed fraud engine |
| 8 | A mule ring is defined by forwarding, not by any cycle |
| 9 | Idempotent sweeps |
| 10 | Proportional response and no tipping-off |
| 11 | Nothing is deleted, it is ended; audit by events |
| 12 | The time machine is an investigation tool, not the evidence store |
| 13 | Tests run on SurrealKV, not in memory |
| 14 | Testing by attacking it (red-team suites) |
| 15 | Calibration on IBM data, two tiers |
| 16 | Lossless prefilter before the graph search |
| 17 | Official SDK for the demo client, standard library for tests |
| 18 | Surrealist instead of a custom dashboard |
| 19 | The cluster runs on TiKV through TiUP, natively, and is not the demo node |
| 20 | HAProxy in front of the SurrealDB nodes, health-checking the node and not the storage |

## 1. SurrealDB instead of the alternatives

**Context.** A bank needs money that never goes out of balance (multi-record
transactions), relationships (a graph, for fraud) and sensitive data
(permissions per record and per field). The course requires a NoSQL database.

**Decision.** SurrealDB 3.2.4, a multi-model database (documents + graph).

**Alternatives considered** (checked against official documentation, October 2026):

| Engine | Why not |
|---|---|
| MongoDB | Multi-document ACID since 4.0, so atomicity does not separate it from SurrealDB. No real graph: `$graphLookup` has a 100 MB limit that ignores `allowDiskUse`. Permissions per collection; per field only through views. Snapshot reads reach only about 5 minutes back by default (`minSnapshotHistoryWindowInSeconds = 300`). |
| Cassandra | Lightweight transactions only within one partition. Multi-partition transactions (Accord, 6.0) are alpha and disabled by default. No graph. Permissions per keyspace and table; column masking since 5.0. |
| Neo4j | A leading graph database, but property-level permissions are Enterprise only. No query into the past. |
| ArangoDB | The serious alternative (documents + graph). Rejected for its permissions: only per database and collection. Full ACID only on a single server. No query into the past. |
| PostgreSQL | Not NoSQL, which the course requires. Its documentation says it "does not currently support system time"; graph queries are recursive CTEs; row-level security is not a graph traversal. |

The licence is **not** an argument: SurrealDB and ArangoDB are both BSL 1.1.

Time travel weighed in: SurrealDB was the only one of the five engines
compared with queries into the past inside the language (`SELECT ... VERSION`).

**Evidence.** Feature comparison from documentation. Performance against these
engines: **not measured**. We do not claim SurrealDB is faster than any of
them; a measured comparison against a recursive CTE in PostgreSQL is still
pending (README.es.md, "Pendiente").

**Consequences and costs.** A young engine: we hit a time-travel bug that
produced false evidence (#7601), lost live deliveries with two subscribers,
functions listed in the docs that do not exist in 3.2.4, and many 3.x renames
(README.es.md traps table). Distributed live queries are Enterprise; versioning is
beta. See [REFLECTION.md](REFLECTION.md).

## 2. No Java backend: the API lives inside the database

**Context.** The original group plan was app, then Java, then database. Java
was a whole layer to maintain, deploy and secure.

**Decision.** The apps talk to SurrealDB directly. **Reads** are ordinary
queries filtered by the database's permissions. **Privileged writes** (moving
money, Bizum, contacts, PIN, cards, unlinking devices) go through endpoints
defined in SurrealQL with `DEFINE API` (`07_api.surql`, `08_cards.surql`,
`10_controls.surql`).

**Alternatives considered.** Keep Java as a thin layer (rejected: duplicates
authentication and permissions that SurrealDB 3 already provides). Put
everything, reads included, behind endpoints (rejected: an endpoint body runs
**without** permission checks, so protecting the CVV or other people's
accounts would depend on every endpoint repeating the check correctly; left in
permissions, the database applies them always).

**Evidence.** `payments_test.py`: 35 checks (32 without `--race`), verifying
the real effect as root, not just the response. `payments_redteam.py`: 11/11
breaks detected. Payment orders are also the idempotency key: in 10 rounds of
10 copies of the **same** order, it is paid once and all ten copies get 201.

**Consequences and costs.** Clients can run free **read** queries; permissions
limit what they see, not what it costs (CPU). In production we would close
this with `--deny-arbitrary-query record` and move reads to endpoints too. A
malformed JSON body gives 500 instead of 400, because SurrealQL has no
try/catch. A write conflict arrives as HTTP 400, so the client must retry by
recognising the text.

## 3. The balance is derived from an append-only ledger

**Context.** A bank must be able to explain every cent.

**Decision.** The truth is `entry`, a double-entry ledger: each movement is two
entries summing to zero, written in one transaction, every field `READONLY`.
An entry is never corrected, only compensated. The invariant lives only in
`fn::transfer`; no client writes entries. `account.balance` is a materialised
value, and `fn::reconcile()` must always return nothing.

**Alternatives considered.** A plain mutable balance (rejected: no history, no
audit). A pure ledger without a materialised balance (rejected after
measuring, see evidence).

**Evidence.** Under snapshot isolation a pure ledger allows overdrafts,
because concurrent transfers insert different records and never conflict. The
`UPDATE account SET balance` creates the write-write conflict that serialises
them. With 10 concurrent full-balance transfers: `fn::transfer` 0/20 rounds
with overdraft, `fn::transfer_unsafe` 13/20 (README.es.md). The schema comment
records another run: 0/30 against 7/30, and on 2026-11-11 two runs gave 11/20
and 12/20, and on 2026-11-13 six runs gave 16, 12, 11, 15, 12 and 12 of 20. The unsafe count varies from run to run; the safe one has always
been 0.

The test itself once lied. It counted any final balance other than 0 as an
overdraft, so on a database where the attack had frozen the account no
transfer went through, the balance stayed at 100, and the safe version showed
"20/20 rounds ended in an overdraft". It now tells apart overdraft (below 0),
correct (0, exactly one transfer) and none (100, reported as a setup error),
and `demo.sh race` uses its own fresh database.

**Consequences and costs.** The balance is written twice (ledger and account),
and every payment rewrites the account record, which is what makes versioning
grow the disk (decision 12). The unsafe function is kept on purpose as the
failing case of the test.

## 4. `transfer` duplicates the ledger as a graph edge

**Context.** Fraud detection needs graph traversals; accounting needs the
ledger.

**Decision.** `fn::transfer` writes the entries **and** `RELATE
$from->transfer->$to` in the same transaction. The ledger is the accounting
truth; the edge is the graph projection the detectors traverse.

**Alternatives considered.** Traverse the ledger with `WHERE` queries
(rejected: slower and not a graph); an external graph database fed by ETL
(rejected: two systems that can diverge).

**Evidence.** Same transaction, so they cannot diverge; reconciliation stays
empty. Speed gain of edges over ledger queries: **not measured**.

**Consequences and costs.** The fact is stored twice. This is the multi-model
argument in one line: two models of the same fact in one database, without
ETL.

## 5. Authorization is a graph traversal

**Context.** Who may see an account is a relationship: owner or joint owner.

**Decision.** Permissions are traversals, for example
`PERMISSIONS FOR select WHERE id IN $auth.customer->owns->account`. The card
has three conditions on one row: visible if the account is yours; PAN and CVV
only for the person who carries it (`holder`); and only with a PIN check less
than 90 seconds old.

**Alternatives considered.** Permission tables joined at query time; checks in
a backend (rejected with decision 2).

**Evidence.** `access_test.py`: 18 checks acting as Ana and Luis, including
attacks. `access_redteam.py`: 9/9. The `holder` condition fixed a real flaw of
the first version: a verified joint owner would have seen the other owner's
PAN.

**Consequences and costs.** Permissions only show when testing as a record
user; root bypasses all of them. The engine warns that the permission on
`customer.bizum_account` has "opaque dependencies"; still to review.

## 6. PIN step-up through an endpoint

**Context.** Opening the 90-second window means writing
`app_user.verified_until`, and a user must not be able to write it (or they
would set it to the year 3000).

**Decision.** `POST /verify-pin` as a `DEFINE API`. After 3 consecutive
failures it locks verification for 15 minutes, rejecting even the correct PIN.
The PIN travels in the request and is never stored.

**Alternatives considered.**
1. `DEFINE FUNCTION`: runs with the caller's permissions, so its `UPDATE` did
   nothing, and it **still returned `true`**.
2. `DEFINE EVENT`: writes with privilege, but rejecting means throwing, and the
   throw also undoes the failure counter. A 4-digit PIN allowed all 10,000
   attempts.
3. `DEFINE API`: rejects by **returning** 401, so the failure is kept. Chosen.

**Evidence.** `cards_test.py`: 41 checks (PIN limit, cards, notifications);
`cards_redteam.py`: 12/12.

**Consequences and costs.** The password login has no attempt limit yet; only
the PIN does (README.es.md, "Pendiente").

## 7. Two-speed fraud engine

**Context.** `DEFINE EVENT` runs inside the payment's transaction; if it
throws, the payment is undone, and its cost is added to every write.

**Decision.** **In-line** (events, `04_events.surql`): only bounded,
index-backed detectors: velocity, impossible travel, low balance. **Sweeps**
(`05_detectors.surql`): graph traversals and window aggregations outside the
payment path: mule rings, shared device, structuring. Both write to
`fraud_alert`, the one table the dashboard's `LIVE SELECT` listens to.

**Alternatives considered.** Everything in events (rejected: a graph search
per payment, and a bug would block payments). `ASYNC` events (exist, but with
a delay; default interval 5 s).

**Evidence.** At 3,000 customers: impossible travel and charge bursts in-line,
30/30 found each, 0 false positives; sweeps: rings 1.31 s (249/249), shared
device 0.06 s (30/30), structuring 0.33 s (30/30), all with 0 false positives.
Single payments with all events: 692/s at 1,000 customers. The fraud was
planted by us following the detectors' rules, so this proves the
implementation is correct and scales, not that it would catch a real
launderer.

**Consequences and costs.** Synchronous events add cost to every write, a
trade-off accepted on purpose.

## 8. A mule ring is defined by forwarding, not by any cycle

**Context.** The first detector looked for any cycle of 2 to 5 hops.

**Decision.** Redefine the problem before optimising it: a ring is the **same
money forwarded**: each hop leaves soon after the previous one arrived (under
48 h), for a slightly smaller amount (85 to 100 %), through 3 or more accounts,
back to the origin. Implemented as a recursive function (`fn::ring_from`)
because a `LET` inside a `FOR` does not reassign the outer variable.

**Alternatives considered.** Make the naive cycle search faster (rejected: two
friends paying each other back already form a cycle, and each repeated
transfer multiplies the paths).

**Evidence.** On the same bank of 100 customers: naive version 53 to 54 s
(53 s in the schema comment, 54 s in the README.es.md) and 75 innocent accounts
flagged; new version 0.03 s and 0 false positives. The naive one is kept as
`fn::detect_rings_naive` to repeat the comparison.

**Consequences and costs.** Thresholds were illustrative until decision 15
calibrated them, and independent data showed the strict rule was nearly
blind.

## 9. Idempotent sweeps

**Context.** Sweeps are re-run; with `CREATE`, each pass duplicated the alerts
(22, then 44, then 66 in the 300-customer bank). `bench.py` did not see it
because it deletes alerts before measuring.

**Decision.** Each alert's ID states what was seen, for example
`['mule_ring', account, members]`, `['shared_device', device, holders]`,
`['structuring', account, day]`, and it is written with `INSERT IGNORE`.

**Alternatives considered.** Check-then-create (racy and more code);
deleting old alerts (loses history).

**Evidence.** `detect_test.py`: repeating the sweep does not duplicate alerts;
`detect_redteam.py`: 9/9.

**Consequences and costs.** A structuring burst that crosses midnight can alert
on two consecutive days (declared assumption).

## 10. Proportional response and no tipping-off

**Context.** Detecting is not enough; the bank must act, and false positives
hurt real people.

**Decision.** An event on `fraud_alert` responds in proportion:

| Alert | Response |
|---|---|
| `mule_ring` (strict) | freeze the account and block its cards |
| `impossible_travel` | block that card |
| `possible_ring`, `shared_device`, `structuring`, `velocity` | "under review" |
| `low_balance` | nothing |

Freezing blocks **outgoing** money; incoming money still arrives. The API
answers `423 account_frozen` **without saying why**: telling a suspect of
money laundering that they are being investigated is prohibited (art. 24 of
Spanish Ley 10/2010). A second check inside `fn::transfer` and `fn::debit_at`
covers direct calls. Releasing is `fn::release_account(account, note)`,
fraud team only, and audited; cards do not unblock themselves.

**Alternatives considered.** Freeze on every alert (rejected: four people
punished for sharing a family tablet). Tell the customer the reason (rejected:
illegal).

**Evidence.** `controls_test.py`: 31 checks; `controls_redteam.py`: 23/23.

**Consequences and costs.** Decisions depend on detector precision, which is
why the uncertain tier goes to an analyst (decision 15).

## 11. Nothing is deleted, it is ended; audit by events

**Context.** After an alert, mules try to erase their trail: unlink the shared
phone, empty the account.

**Decision.** Clients cannot delete anything (permissions), just as they
cannot touch a ledger entry. Unlinking a device goes through
`POST /devices/unlink`, which sets `ended_at` and keeps the edge; the
shared-device detector still counts it. Every change to edges, devices, cards,
accounts and customers writes an `audit_log` row with before, after, when and
**who** (`actor`, `via`), written by events, so there is no path around it.
The PAN, CVV and NIF never enter it (analysts read it). Balance changes are not
audited: they are already in the immutable ledger and in `payment_order`.

**Alternatives considered.** Soft-delete flags set by the client (bypassable);
auditing in application code (bypassable).

**Evidence.** Demo `coverup.py`: Marta deletes the phone by SQL (no permission,
it stays), withdraws money (423), unlinks the phone (marked, not deleted, and
audited). Same suites as decision 10.

**Consequences and costs.** Root can still delete rows, including from
`audit_log`, and `REMOVE TABLE` cannot be prevented. A real bank copies the
audit trail out of the database to WORM storage with legal retention; that
copy is not built.

## 12. The time machine is an investigation tool, not the evidence store

**Context.** An investigator needs the bank as it was when the alert fired.

**Decision.** Two clocks. **Bank time**: the immutable ledger gives any past
balance (`fn::balance_at`) with no expiry. **System time**: SurrealKV
versioning (30-day retention) for what can change or be deleted;
`fn::investigate(alert)` rebuilds accounts, owners, balances and devices at the
alert instant and lists what changed. It is **not** the evidence store; the
audit log (decision 11) is.

**Why not evidence:** 30 days against 5 years (EU directive 2015/849) and 10
years (Spanish law) of legal retention; it lives on the server being
investigated; it does not record **who**; SurrealKV is beta; and bug #7601
returned records deleted before the requested date, which in an investigation
is false evidence.

**Evidence.** Disk: 26 MB without versioning, 42 MB with it (+62 %); load time
55 s against 53 s (one run each, noise). The two clocks agree account by
account. `time_travel_test.py`: 20 checks; `time_travel_redteam.py`: 10/10.
Workaround for #7601: traversals give candidates, each confirmed by reading it
by ID (`fn::owners_at`, `fn::users_at`).

**Consequences and costs.** Whether SurrealKV really purges versions older than
the retention is unconfirmed (documented for RocksDB only). Not available on
TiKV.

## 13. Tests run on SurrealKV, not in memory

**Context.** Bug #7601 exists only in SurrealKV. In memory, traversals answer
correctly, so the confirmation traps had nothing to catch: the time-travel red
team dropped to 6/10 without any code change.

**Decision.** `demo.sh server` starts SurrealKV in a temporary folder, and the
time-travel test warns if the engine does not reproduce the bug.

**Alternatives considered.** Memory for speed (rejected: we were testing a
different engine from the one we run).

**Evidence.** 6/10 on memory, 10/10 on SurrealKV. With versioning on, the
other suites also pass, including the payment race, and the live listener gets
the 6 attack alerts.

**Consequences and costs.** Slower test setup: not measured.

## 14. Testing by attacking it

**Context.** A test you have never seen fail guards nothing.

**Decision.** Every protection has a red-team case: `demo/redteam.py` applies
the **real** schema with one exact text replaced (for example
`PERMISSIONS NONE` turned into `PERMISSIONS FULL`) and requires the guarding
test to fail. If the text to break disappears from the file, the case counts
as broken. Attacks are verified by their **effect as root**: a user without
read permission sees `[]` whether the row exists or not.

**Alternatives considered.** Hand-written redefinitions of the broken code
(rejected: they went stale; the impossible-travel one rewrote an event that had
already changed).

**Evidence.** 74/74 breaks detected: access 9/9, payments 11/11, cards 12/12,
detect 9/9, time travel 10/10, controls 23/23. The red teams found tests that
passed with the bug in place (a user who could not read the PIN request table
saw it empty either way) and tests that crashed instead of failing.

**Consequences and costs.** Each suite runs once per break; total time not
measured.

## 15. Calibration on IBM data, two tiers

**Context.** Our own generator can only confirm what we designed. We needed
independent data with a known answer: IBM's synthetic AML dataset
(CDLA-Sharing-1.0), details in [DATASET.md](DATASET.md).

**Decision.** Calibrate with a method fixed in advance (grid of amount bounds
and time gaps, best recall with precision at least 95 %, ties to the
strictest), on HI-Small, then apply it untouched to LI-Small. Two tiers:
strict ring (0.85 to 1.00, 48 h) gives `mule_ring` and **freezes**; a ring only
the wide rule sees (0.90 to 1.20, 72 h) gives `possible_ring` and goes to
**review**.

**Evidence.**

| | strict | wide |
|---|---|---|
| HI-Small (calibration) | 6/54 cycles, precision 100 % | 33/54, 98.6 % |
| LI-Small (held out) | 1/12, 100 % | 8/12, 86.9 % |

Our assumption that a mule keeps a commission was wrong on this data: after
currency conversion the amount moves about 9 % and grows half the time. 19 of
the 54 cycles are out of reach of any forwarding rule (14 have only 2
accounts, 2 break the permissive rule, 3 are not in time order).

**Consequences and costs.** Freezing on the wide rule would freeze about 1
innocent in 8, hence review. Synthetic data: real precision would be lower. We
do not recalibrate on LI-Small.

## 16. Lossless prefilter before the graph search

**Context.** One day of IBM data (200,000 transfers) kept the CPU at 100 % for
minutes on a fanless laptop.

**Decision.** `demo/aml_prefilter.py` removes, in a linear pass repeated until
nothing changes, every transfer that **cannot** be part of a ring under the
most permissive rule: it must have a previous **or** a next hop under the rule,
and its accounts must be in the same strongly connected component of at least
3 accounts. Only the survivors are loaded.

**Evidence.** HI-Small: 4,487,133 to 381 transfers (256 accounts); 323 of the
381 are laundering (85 %, against 0.1 % in the set). LI-Small: 6,119,572 to
158. Lossless checked by a Python re-implementation of `fn::ring_from` on the
first 500,000 and 1,500,000 rows; changing *or* to *and* loses every ring and
the check catches it. The committed 6.5 MB sample reproduces the full set
exactly (381 candidates, 7 strict rings over 20 accounts, 36 wide rings over
211 accounts).

**Consequences and costs.** The full dataset never reaches SurrealDB; it goes
to a separate `aml` database with only core, graph and detectors.

## 17. Official SDK for the demo client, standard library for tests

**Decision.** `demo/demo_client.py` uses the official Python SDK
(`surrealdb==3.0.0`): WebSocket, Python types, live queries; it is what a real
application would use. The test suites use only `urllib` from the standard
library, so they depend on nothing outside Python.

**Evidence.** Not applicable (tooling choice).

**Consequences.** Two client styles to maintain; the tests also exercise the
raw HTTP behaviour (status codes, the 400 conflict) that an SDK might hide.

## 18. Surrealist instead of a custom dashboard

**Decision.** Use Surrealist, the official GUI, for the demo: saved queries,
the Graph result mode (draws the ring), and the Live view over WebSocket.

**Alternatives considered.** A custom web dashboard (rejected: work outside the
graded deliverable, which is the database).

**Consequences.** The database persists on disk between sessions (about 32 MB)
so the demo can be prepared in advance. The iOS app still uses mock data.

## 19. The cluster runs on TiKV through TiUP, natively, and is not the demo node

**Context.** The course asks for scalability. SurrealDB distributes by running
stateless nodes on top of TiKV; our laptop has little free disk and no fan.

**Decision.** A local cluster of 1 PD, 3 TiKV and 2 SurrealDB nodes, started
with TiUP playground (`demo.sh cluster-up`), with the 5 GB per-node disk
reservation off and the block cache at 256 MB (`cluster/tikv.toml`). The live
demo and the time machine stay on the single SurrealKV node.

**Alternatives considered.** Docker images (rejected: about 1.1 GB of images
against about 110 MB of native binaries); `tiup cluster` on separate machines
(rejected: we have one laptop each).

**Evidence.** 15 s to start, about 1.1 GB of RAM and 2 % CPU idle, 299 MB of
binaries. Five of six suites pass on TiKV; time travel cannot ("does not
support versioned queries"). A live query on one node got 0 of 5 changes made
on the other. Killing the leader of the written region: writes failed with an
error for 9 to 12 s, none lost or half applied ([CLUSTER.md](CLUSTER.md)).

**Consequences and costs.** Two configurations to explain: a cluster that
survives a dead node but has no time travel or cross-node live queries, and a
single node that has both. On a real cluster the fraud dashboard would have to
listen on every node.

## 20. HAProxy in front of the SurrealDB nodes, health-checking the node and not the storage

**Context.** The SurrealDB nodes keep no state, so any of them can serve any
request. Without a balancer, the app would have to know every node and decide
which one is alive.

**Decision.** HAProxy (`cluster/haproxy.cfg`) on one address, round robin over
the nodes, active health check every second on `/status`, out after 2
failures; retry on the other node only when the connection fails, so a request
is never sent twice; WebSockets pinned to their node.

**Alternatives considered.** nginx, free version (rejected: it only notices a
dead node when a real request fails); Caddy (works, less control over
retries); the app talking to the nodes directly (rejected: every client would
need the node list and its own failover).

**Evidence** ([CLUSTER.md](CLUSTER.md)). Killing SurrealDB node A during 40
writes through HAProxy: 40 of 40 OK in three runs, slowest 52 ms. Our first
health check used `/health`, which also checks the storage: when the TiKV
leader died both nodes failed it, HAProxy removed both, and 22 of 40 writes
failed against 5 to 7 with no balancer. With `/status`, 6 and 7 failed, all
from the storage election. A live query opened through HAProxy received 5 of
10 changes when the writes were spread over both nodes, in three runs.

**Consequences and costs.** One more process, and in this setup a single point
of failure (production runs two balancers on a floating address, with TLS). A
health check must test the node, not what all nodes share. Live alerts need
one connection per node, or a re-read on reconnect.
