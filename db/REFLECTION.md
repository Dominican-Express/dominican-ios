# Critical reflection

What SurrealDB did well for this project, where it hurt, how it compares with
the alternatives, and what kind of project it suits. Figures come from
[README.es.md](README.es.md) and [DATASET.md](DATASET.md); the decisions behind them
are in [DECISIONS.md](DECISIONS.md), and the concepts in
[FUNDAMENTALS.md](FUNDAMENTALS.md).

## Strengths observed

**One model for accounting, fraud and authorization.** The ledger, the
`transfer` graph and the `owns` permissions live in one database and commit in
one transaction. The same traversal, `$auth.customer->owns->account`, filters
what a customer sees and feeds the fraud detectors. No ETL, no second system,
no bridge table.

**Logic close to the data, and hard to bypass.** Functions, events, params and
HTTP endpoints let us remove the planned Java backend entirely. The audit
trail is written by events, so no client path avoids it. Field permissions
hide the PAN and CVV from everyone except the cardholder within 90 seconds of
a PIN check, and the database applies them on every query.

**Transactions that hold under load, once understood.** With the materialised
balance as the conflict point, 0 of 20 concurrency rounds ended in overdraft,
against 13 of 20 for a pure ledger. Payment orders double as idempotency keys
through the same mechanism.

**Fast enough at our scale.** At 3,000 customers (200,846 entries), normal
activity ran at 1,342 operations/s, the ring sweep took 1.31 s and the other
sweeps under 0.4 s, all with 0 false positives on our generated bank. On IBM
data the ring sweep over 20,874 transfers took 1.0 s once written correctly.

**A language with useful extras.** `decimal` for money, `geometry<point>` and
`geo::distance` for impossible travel, array record IDs for idempotent alerts,
`LIVE SELECT` for the dashboard and `SELECT ... VERSION` for investigations.
Among the five engines we compared, it was the only one with queries into the
past inside the language.

## Limitations observed

| Area | What we found | Evidence |
|---|---|---|
| Maturity | Many 3.x renames and removals (`type::thing`, `duration::from::hours`, `type::is::string`, fuzzy `~`); `DEFINE TABLE OVERWRITE` keeps old fields | README.es.md traps table |
| Docs vs binary | `api::req::max_body()` is documented but missing in 3.2.4 ("no such builtin function found") | README.es.md traps table |
| Time travel bug | surrealdb#7601: traversals with `VERSION` return records deleted before that date; only on SurrealKV; depends on execution path | red team 6/10 on memory, 10/10 on SurrealKV |
| Versioning | SurrealKV is beta; 3.3 removes versioning from the memory engine; purge of old versions in SurrealKV unconfirmed | README.es.md |
| Live delivery | One subscriber: 30/30. Two subscribers at once: 23/30 and 24/30 as clients, 28/30 as root, with no error and the row saved | `demo/live_delivery_check.py` |
| Distribution | Live queries do not cross nodes (Enterprise feature); versioning is SurrealKV only, so not on TiKV | 3-TiKV cluster: live query got 0 of 5 changes made on the other node; time travel suite fails ([CLUSTER.md](CLUSTER.md)) |
| Planner | `WHERE field = $var.field` ignores the index: 72 ms against 1.2 ms per transfer | `EXPLAIN`, `write_bench.py` |
| Hidden complexity | `.map` calling a function that queries grows quadratically: 5,000 items 2.8 s, 20,000 items 49 s; the IBM ring sweep took 54 s, 1.0 s with `SELECT VALUE` | README.es.md traps table |
| Silent failures | `RETURN` inside `FOR` exits on the first iteration; `LET` inside `FOR` does not update the outer variable; a function's privileged `UPDATE` silently does nothing and still returns success | README.es.md traps table |
| HTTP semantics | A write conflict comes back as HTTP 400; malformed JSON in an endpoint gives 500 (no try/catch) | `payments_test.py`, README.es.md |
| Missing locking | `SELECT ... FOR UPDATE` only from 3.3 (beta); in 3.2 a write must be used as the conflict point | README.es.md |
| Input parsing | `api::req::body("json")` turns `"Cena: viernes"` into the record `Cena:viernes` | README.es.md traps table |

The common thread: almost none of these show up when reading the code. Every
one was found by running it, measuring it or breaking it on purpose. Several
fail **silently**, which is the dangerous kind in a bank.

What we could not prove: scalability beyond 3,000 customers and about 100,000
operations, behaviour on a disk server under heavy load, and a cluster on
separate machines. Our cluster ran on one laptop ([CLUSTER.md](CLUSTER.md)):
it shows replication and failover, not throughput or network partitions. The 100 % detection on our own
bank only shows the implementation is correct, because we planted the fraud
with the same rules.

## Comparison with a relational database (PostgreSQL)

| Aspect | PostgreSQL | SurrealDB (as we used it) |
|---|---|---|
| Transactions | Mature ACID, `SELECT ... FOR UPDATE`, serializable isolation | ACID with snapshot isolation; no `FOR UPDATE` in 3.2 |
| Graph queries | Recursive CTEs | Native traversal syntax and edges with fields |
| Row and field security | Row-level security policies, column privileges | Table and field permissions written as graph traversals |
| Query into the past | "does not currently support system time" (needs an extension or triggers) | `SELECT ... VERSION`, beta, with bug #7601 |
| Logic and API | Functions and triggers; an HTTP layer is a separate product | Functions, events and `DEFINE API` endpoints in the database |
| Maturity, tooling, people who know it | Decades | Young; we hit several engine bugs |
| Performance for our workload | not measured | measured only on SurrealDB |

An honest summary: PostgreSQL is far more mature, with decades of tooling and
many more people who know it, and the course's NoSQL requirement ruled it out
anyway. For this problem we would lose the graph as a first-class model shared
by permissions and fraud detection, the API and real-time updates inside the
database, and built-in time travel. Which one is faster for our workload is
not measured: a comparison of the ring detector against a recursive CTE is
pending.

## Comparison with other NoSQL databases

- **MongoDB** has the same multi-document atomicity, so ACID is not a
  difference. The difference is the graph (`$graphLookup` is limited to
  100 MB) and per-field permissions (only through views).
- **Cassandra** is built for write throughput across partitions; transactions
  stay within one partition and there is no graph. Wrong fit for moving money
  between two arbitrary accounts.
- **Neo4j** is the strongest graph engine of the group, but per-property
  permissions are Enterprise only, which is exactly what the PAN and CVV need.
- **ArangoDB** is the closest alternative (documents + graph); its permissions
  stop at database and collection, and full ACID is single-server only.

None of these comparisons were measured; they come from documentation.

## Where SurrealDB fits, and where it does not

**Good fit:**

- applications where documents, graph relationships and fine-grained
  permissions meet, such as fraud, risk, social or access-control data;
- small and medium systems that benefit from keeping API, auth and real-time
  updates inside the database, with a small team;
- prototypes and teaching, where one engine shows several data models.

**Poor fit, today:**

- systems that need a long, proven operational record and stable semantics
  across versions (we hit renames, a false-evidence bug and lost live events);
- real-time features that must scale across nodes without an Enterprise
  licence;
- legal evidence storage: versioning is beta and short-retention, so audit
  data must be copied out to WORM storage anyway;
- heavy batch analytics on a single small node: a graph search started from
  each of IBM's 4.5 million transfers kept a laptop at full CPU for minutes.
  That is mostly our algorithm (any engine needs the prefilter we added, 4.5
  million to 381), and on the way we hit a `.map` that turned quadratic
  (see the README.es.md traps).

## What we would do differently

- Test as a record user and on the production engine from day one; testing as
  root and in memory hid real problems twice.
- Treat every engine feature as a hypothesis: measure it (`EXPLAIN`, delivery
  counts, red-team breaks) before building on it.
- Build the WORM copy of the audit log and a login attempt limit, both still
  missing.
