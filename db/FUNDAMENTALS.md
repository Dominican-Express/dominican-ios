# SurrealDB fundamentals, explained with Dominican Express

This document explains what SurrealDB is and how it works, using our bank as
the running example. Every SurrealQL snippet comes from `db/schema/` or is
consistent with it. Every number comes from a measurement recorded in
[README.es.md](README.es.md) (Spanish) or [DATASET.md](DATASET.md); when there is
none, we say "not measured".

Related documents:

- [DECISIONS.md](DECISIONS.md): why we built it this way, decision by decision.
- [REFLECTION.md](REFLECTION.md): what worked, what did not, and where SurrealDB fits.
- [INSTALL.md](INSTALL.md): how to install and start the server.
- [DEMO.md](DEMO.md): the demo, step by step.
- [DATASET.md](DATASET.md): the IBM anti money laundering dataset and the ring detector.

Version used throughout: **SurrealDB 3.2.4** (macOS aarch64).

## 1. What kind of NoSQL database it is

SurrealDB is a **multi-model** database. One engine, one query language
(SurrealQL) and one transaction cover three ways of storing data:

| Model | In SurrealDB | In our bank |
|---|---|---|
| Document | A record is a JSON-like object with nested fields, arrays and typed values | `customer`, `account`, `fraud_alert` (its `detail` is a free object) |
| Graph | A relation is itself a record with `in` and `out`, and it can carry fields | `owns` (customer to account, with a `role`), `transfer`, `uses`, `favorite` |
| Key-value | Underneath, every record is a key in an ordered key-value store | not used directly; it is the storage layer (section 5) |

Every record has an ID of the form `table:id`, for example `account:ana` or
`customer:luis`. The ID is part of the value: you can store it in a field
(`TYPE record<account>`), follow it with a dot (`$card.account.kind`) and fetch
the record directly by it, without an index lookup on a separate key column.
An ID can also be an array, which we use to make alerts idempotent:
`fraud_alert:['mule_ring', account:ana, [...]]` (cheat sheet, example 10).

Although SurrealQL looks like SQL, the database is not relational: there are no
JOINs, records link to each other by ID, relations are first-class records,
and the schema is optional per table.

### What it solves better, and typical scenarios

SurrealDB is a good candidate when one application needs **documents and a
graph at the same time, under the same transaction and the same permissions**.
In a bank that is exactly the case:

- money must never go out of balance (multi-record ACID transactions);
- fraud is a graph problem (rings of accounts, phones shared by strangers);
- data is sensitive and must be filtered per record and per field.

Typical scenarios: fraud and risk analysis, recommendation and social data,
access-control models that are themselves graphs, and small or medium
applications that want the API, authentication and real-time updates inside
the database. Where it fits less well is discussed in
[REFLECTION.md](REFLECTION.md).

## 2. Data model

### Tables: SCHEMAFULL and SCHEMALESS

A table is either `SCHEMAFULL` (only declared fields are stored, every field is
type-checked) or `SCHEMALESS` (any field is accepted; declared fields are still
checked). Most of our tables are schemafull. `fraud_alert` is schemaless on
purpose, because each detector writes a different `detail`:

```surql
DEFINE TABLE OVERWRITE fraud_alert SCHEMALESS TYPE NORMAL
    PERMISSIONS FOR select WHERE account IN $auth.customer->owns->account;
DEFINE FIELD OVERWRITE kind  ON fraud_alert TYPE string;
DEFINE FIELD OVERWRITE score ON fraud_alert TYPE float;
```

`OVERWRITE` makes every schema file safe to re-apply. One trap: redefining a
table with `OVERWRITE` does **not** remove old fields; we use `REMOVE FIELD` or
`REMOVE TABLE` explicitly (README.es.md, SurrealQL traps table).

### Fields: TYPE, ASSERT, DEFAULT, VALUE, READONLY

| Clause | Meaning | Example from `01_core.surql` |
|---|---|---|
| `TYPE` | the value must have this type; `option<T>` allows NONE | `TYPE option<record<account>>` |
| `ASSERT` | a boolean condition on `$value`, checked on every write | IBAN format |
| `DEFAULT` | value used when none is given | `DEFAULT 0dec` |
| `VALUE` | value computed on every write, overriding the client | `VALUE time::now()` |
| `READONLY` | cannot change after creation | every field of `entry` |

```surql
DEFINE FIELD OVERWRITE iban     ON account TYPE string ASSERT string::matches($value, "^ES[0-9]{22}$");
DEFINE INDEX OVERWRITE account_iban ON account FIELDS iban UNIQUE;
DEFINE FIELD OVERWRITE kind     ON account TYPE string DEFAULT 'customer' ASSERT $value IN ['customer','external'];
DEFINE FIELD OVERWRITE opened   ON account TYPE datetime VALUE time::now() READONLY;
DEFINE FIELD OVERWRITE balance  ON account TYPE decimal DEFAULT 0dec;
```

The ledger entry is immutable field by field. A wrong entry is never
corrected; it is compensated by another one:

```surql
DEFINE FIELD OVERWRITE account ON entry TYPE record<account> READONLY;
DEFINE FIELD OVERWRITE txn     ON entry TYPE record<txn>     READONLY;
DEFINE FIELD OVERWRITE amount  ON entry TYPE decimal         READONLY;
```

Money uses the `decimal` type (`12.50dec`), never `float`.

### Record links

A field of type `record<table>` stores the ID of another record. It is a
pointer, not a foreign key with cascading rules. You follow it with a dot:
in `04_events.surql` the condition `$after.account.kind = 'customer'` reads the
`kind` of the account that the new entry points to.

### Graph edges: RELATE and TYPE RELATION

An edge table is declared with `TYPE RELATION`. `IN` and `OUT` restrict which
tables it may connect, and `ENFORCED` refuses an edge whose endpoints do not
exist. Edges are records, so they can have fields, indexes and permissions:

```surql
DEFINE TABLE OVERWRITE owns TYPE RELATION IN customer OUT account ENFORCED
    PERMISSIONS FOR select WHERE out IN $auth.customer->owns->account;
DEFINE FIELD OVERWRITE role ON owns TYPE string ASSERT $value IN ['titular','cotitular'];
```

Joint ownership is an attribute on the edge (`role`), not a bridge table.
Edges are created with `RELATE` (from `demo/01_seed.surql`):

```surql
RELATE customer:ana->owns->account:ana   SET role = 'titular';
RELATE customer:luis->owns->account:ana  SET role = 'cotitular';
```

### Graph traversal

Arrows follow edges. `->` goes out, `<-` comes in:

| Expression | Reads as |
|---|---|
| `$auth.customer->owns->account` | the accounts I own |
| `$after.account<-owns<-customer` | every owner of this account |
| `$auth.customer->owns->account<-owns<-customer` | everyone who shares an account with me |
| `$node->transfer` | the transfer edges leaving this account |

Traversals return arrays, so they combine with array functions:
`fn::detect_shared_devices` intersects `$c->owns->account<-owns<-customer` with
the users of a device to count households instead of people. The naive ring detector we kept for comparison used recursive
paths, `id.{2..5+path}(->transfer->account)`, which is the syntax for "follow
2 to 5 hops and return the paths" (see [DECISIONS.md](DECISIONS.md)).

## 3. Consistency and transactions

Every SurrealQL request runs in a transaction; `BEGIN` and `COMMIT` group
several statements explicitly. A function call, the events it triggers and
the writes they make all commit or roll back together. Our concurrency test
sends each transfer like this (`demo/concurrency_test.sh`):

```surql
BEGIN;
LET $r = fn::transfer(account:ana, account:luis, 100dec);
COMMIT;
```

**Isolation.** SurrealDB 3.2 uses **snapshot isolation** with write-write
conflict detection on the same record at commit time. This has a consequence
we only found by testing: an append-only ledger alone does **not** prevent an
overdraft. Two concurrent transfers from the same account insert *different*
entries, so they do not collide; both read balance 100, both pass the check,
both commit.

What serialises them is `UPDATE account SET balance`, because both
transactions write the same record. The materialised balance is therefore not
a cache: it is the concurrency control mechanism. Measured with
`demo/concurrency_test.sh`, 10 simultaneous transfers of the full balance:

| Implementation | Rounds with overdraft |
|---|---|
| `fn::transfer` (writes `balance`) | 0 / 20 (README.es.md); 0 / 30 (comment in `03_functions.surql`) |
| `fn::transfer_unsafe` (pure ledger) | 13 / 20 (README.es.md); 7 / 30 (comment in `03_functions.surql`) |

`SELECT ... FOR UPDATE`, which would express this explicitly, exists only from
3.3 (beta at the time of this work); in 3.2 it is a parse error.

**Conflicts and retries.** A write conflict rolls back the whole transaction.
SurrealDB 3.2 returns it as **HTTP 400**, which looks like a client error, so
our client recognises it by its text and retries (`api()` in
`demo/session.py`). In a race of 10 payment orders for the whole balance:
without retry, 5 of the 10 ended in a conflict; with retry, exactly one
succeeds and the other nine are rejected for insufficient funds.

A second invariant check runs inside `fn::transfer`: the two entries of a
transaction must sum to zero or the whole transaction is undone:

```surql
LET $txid = $tx.id;
LET $sum = math::sum(SELECT VALUE amount FROM entry WHERE txn = $txid);
IF $sum != 0dec { THROW "Asiento descuadrado" };
```

## 4. Indexes and the query planner

`DEFINE INDEX` creates normal or `UNIQUE` indexes (for example
`entry_by_account ON entry FIELDS account, at`). `EXPLAIN` shows whether the
planner uses them. One trap cost us a factor of 60: comparing with the
**field of a variable** (`WHERE txn = $tx.id`) makes 3.2 ignore the index
(`TableScan`); copying it to a plain variable first (`LET $txid = $tx.id`)
uses it (`IndexScan`). At 1,000 customers, `fn::transfer` went from 72 ms to
1.2 ms ([DECISIONS.md](DECISIONS.md), README.es.md "Volumen").

## 5. Storage engines and architecture

SurrealDB separates **compute** from **storage**. A SurrealDB server parses
SurrealQL, checks permissions, plans queries and runs functions and events.
Underneath, it stores everything as keys and values in a pluggable engine:

| Engine | Start with | What it is | Notes |
|---|---|---|---|
| Memory | `surreal start memory` | in-process, lost on restart | fast for development |
| RocksDB | `surreal start rocksdb:<path>` | embedded on-disk key-value store | single node |
| SurrealKV | `surreal start surrealkv:<path>` | SurrealDB's own on-disk engine | supports **versioning** (time travel); officially beta |
| TiKV | `surreal start tikv://<pd-address>` | distributed transactional key-value store | multi-node |

With memory, RocksDB or SurrealKV, one process holds both compute and data.
With TiKV the two layers split:

- **SurrealDB nodes are stateless.** Any number of them can sit behind a load
  balancer; each one translates queries into key-value reads and writes.
- **TiKV holds the data.** The key space is split into contiguous ranges
  called *regions* (range partitioning). Regions split automatically as they
  grow and are moved between TiKV nodes to balance load. A placement driver
  (PD) tracks where every region lives.
- **Replication.** Each region is replicated, by default on 3 TiKV nodes, and
  the replicas agree through the **Raft** consensus protocol. A write commits
  once a majority of replicas (2 of 3) has it.
- **Fault tolerance.** If one TiKV node of three fails, every region still has
  a majority, Raft elects new leaders where needed and the cluster keeps
  serving. When the node returns, it catches up from the log. If a majority of
  a region's replicas is lost, that region stops accepting writes rather than
  diverge.
- **Distributed transactions.** TiKV implements multi-key transactions in the
  style of Google's **Percolator**: two-phase commit with timestamps from PD
  and multi-version concurrency control (MVCC). A SurrealDB transaction that
  touches records in different regions is still atomic.

In CAP terms this is a **CP** system: under a network partition it chooses
consistency and refuses writes on the minority side, instead of accepting
writes that might conflict.

Two features do not cross this line in the version we used:

- **Live queries across nodes.** `LIVE SELECT` notifies the connection that
  opened it. Delivering changes made on *other* nodes is listed in the
  SurrealDB documentation as an Enterprise feature ("distributed live
  queries"). Not measured by us on a cluster.
- **Versioning (time travel)** is a SurrealKV feature, so it is not available
  on TiKV. In 3.3, versioning is also removed from the memory engine.

So our real-time demo and time machine run on a single SurrealKV node; the
cluster is for showing replication and fault tolerance.

### Running more than one node

See CLUSTER.md (to be added).

## 6. Security

**Root and record users.** `root` bypasses **all** permissions. That is why
our tests act as application users: anything tested as root proves nothing
about permissions. Application users sign in through a record access method:

```surql
DEFINE ACCESS OVERWRITE banca ON DATABASE TYPE RECORD
    SIGNIN ( SELECT * FROM app_user
             WHERE email = $email AND crypto::argon2::compare(pass, $pass) )
    DURATION FOR TOKEN 15m, FOR SESSION 2h;
```

After signing in, `$auth` is the `app_user` record, so `$auth.customer` is the
customer behind the session.

**Table and field permissions.** A table without a `PERMISSIONS` clause is
`PERMISSIONS NONE` for record users: they see nothing. Our permissions are
graph traversals: you see an account if it hangs from an `owns` edge of yours.

```surql
DEFINE TABLE OVERWRITE account SCHEMAFULL TYPE NORMAL
    PERMISSIONS FOR select WHERE id IN $auth.customer->owns->account;
```

Field permissions narrow it further. A card is visible to every owner of its
account, but the PAN and CVV only to the person who carries it, and only
within 90 seconds of a PIN check:

```surql
DEFINE FIELD OVERWRITE pan ON card TYPE option<string>
    PERMISSIONS FOR select WHERE holder = $auth.customer AND $auth.verified_until > time::now();
DEFINE FIELD OVERWRITE pass ON app_user TYPE string PERMISSIONS FOR select NONE;
```

Edges have permissions too, so a client traversal only crosses edges it can
read. Tested by `demo/access_test.py` (18 checks) and broken on purpose by
`demo/access_redteam.py` (9/9 breaks detected).

**Who runs with which permissions** matters for design (README.es.md, PIN section):

| Piece | Runs with |
|---|---|
| `DEFINE FUNCTION` | the caller's permissions |
| `DEFINE EVENT` | no permission checks (privileged) |
| `DEFINE API` body | no permission checks; the endpoint must check `$auth` itself |

## 7. Logic inside the database

**DEFINE FUNCTION.** Named, typed functions. `PERMISSIONS NONE` means record
users cannot call them; only root, events and endpoints do.

```surql
DEFINE FUNCTION OVERWRITE fn::balance($acc: record<account>) {
    RETURN math::sum(SELECT VALUE amount FROM entry WHERE account = $acc);
} PERMISSIONS NONE;
```

**DEFINE EVENT.** Runs **inside the transaction** that triggered it (unless
marked `ASYNC`). If the event throws, the triggering write is undone. Our
in-line fraud detectors and the whole audit trail are events:

```surql
DEFINE EVENT OVERWRITE low_balance ON account
WHEN $event = "UPDATE" AND $after.balance < 50dec AND $before.balance >= 50dec
     AND $after.kind = 'customer' THEN {
    CREATE fraud_alert SET kind = 'low_balance', score = 0.2,
        account = $after.id, detail = { balance: $after.balance };
};
```

`$event`, `$before`, `$after` and `$value` describe the change.

**DEFINE PARAM.** Database-wide constants. The two ring rules are params:

```surql
DEFINE PARAM OVERWRITE $ring_rule VALUE { lo: 0.85dec, hi: 1dec, gap: 48h };
DEFINE PARAM OVERWRITE $ring_rule_wide VALUE { lo: 0.90dec, hi: 1.20dec, gap: 72h };
```

**DEFINE API.** HTTP endpoints written in SurrealQL, served at
`/api/<ns>/<db>/<path>` (stable since 3.0). This is our whole backend:

```surql
DEFINE API OVERWRITE "/transfers" FOR post
    MIDDLEWARE api::res::body("json")
    PERMISSIONS WHERE $auth.id != NONE
    THEN {
        LET $b = fn::read_json($request.body);
        LET $err = fn::check_order_input($b);
        IF $err != NONE { RETURN fn::bad_request($err) };
        -- the rest checks `from` and `to_iban` and calls fn::place_order:
        -- full text in schema/07_api.surql
    };
```

An endpoint returns `{ status, body }`, so it can reject with a real HTTP code
(401, 403, 404, 409, 422, 423) **without throwing**, and therefore keep what it
wrote (a failed PIN counter, a rejected payment order).

**LIVE SELECT.** A query that stays open on a WebSocket connection and pushes
every matching change. The fraud dashboard listens to one table:

```surql
LIVE SELECT kind, account, device, score FROM fraud_alert;
```

We treat it as a fast path, not as a source of truth: with two subscribers at
once, deliveries were lost without any error (see
[REFLECTION.md](REFLECTION.md)).

## 8. Time travel

On SurrealKV started with versioning, SurrealDB keeps every previous state of
every record during a retention period, and `SELECT ... VERSION` reads the
database as it was at a given instant. Our server starts with:

```sh
SURREAL_DATASTORE_VERSIONED=true SURREAL_DATASTORE_RETENTION=30d
```

```surql
SELECT id, balance FROM account:marta VERSION d'2026-10-28T10:00:00Z';
```

Measured cost: the same bank takes 26 MB without versioning and 42 MB with it
(+62 %), because each payment rewrites a balance and each version is kept.

**Bug surrealdb#7601.** Traversing a table or relation with `VERSION` also
returns records that were **deleted before** that date (fixed only on the main
branch at the time). Reading by ID is correct. So a traversal only produces
*candidates*, and each candidate is *confirmed* by reading it by ID at that
date (`09_time_travel.surql`):

```surql
DEFINE FUNCTION OVERWRITE fn::owners_at($acc: record<account>, $at: datetime) {
    LET $cand = (SELECT VALUE <-owns FROM ONLY $acc VERSION $at) ?? [];
    RETURN SELECT VALUE in FROM $cand VERSION $at;
} PERMISSIONS NONE;
```

The bug appears only on SurrealKV, not in memory, and depends on the execution
path (the same call was wrong when run directly and right inside a `.map`).
Other rules we hit: `VERSION` cannot take a subquery as its source, and a date
before the table existed is an error, not an empty list.

Why we use it only as an investigation tool, not as evidence, is in
[DECISIONS.md](DECISIONS.md).

## 9. How to access it

| Way | Endpoint | Used for |
|---|---|---|
| HTTP | `POST /sql` with headers `surreal-ns`, `surreal-db` | applying schema files, scripts, tests (`demo/surql.sh`) |
| HTTP | `POST /api/<ns>/<db>/<path>` | our `DEFINE API` endpoints |
| WebSocket | `/rpc` | SDKs, `LIVE SELECT`, Surrealist live mode |
| CLI | `surreal sql` | interactive one-liners only |
| GUI | Surrealist | the demo: queries, graph view, live view |
| SDK | official Python SDK `surrealdb==3.0.0` | `demo/demo_client.py` |

**Why not `surreal sql < file.surql`.** The CLI processes input line by line
and breaks every multi-line statement (`DEFINE FUNCTION`, `DEFINE EVENT`) with
false parse errors. We send whole files to `/sql` instead:

```sh
curl -sS -X POST "$SURREAL_URL/sql" -u "$SURREAL_USER:$SURREAL_PASS" \
  -H "Accept: application/json" -H "surreal-ns: $SURREAL_NS" -H "surreal-db: $SURREAL_DB" \
  --data-binary @"$1"
```

Namespaces and databases are not created implicitly in 3.x: they need
`DEFINE NAMESPACE` and `DEFINE DATABASE`, or the server answers "The database
'x' does not exist".

**Surrealist.** Connect over HTTP to `127.0.0.1:8099`; the Live view needs a
WebSocket connection. In the Query view, the **Graph** result mode draws each
returned record as a node and the edges between them, so
`SELECT * FROM account;` in database `bank` shows the ring ana, luis, marta.

**Python SDK.** The demo client signs in as root and as Ana, uses record IDs as
Python objects and subscribes to a live query:

```python
with Surreal(a.url) as ana:
    ana.signin({"namespace": a.ns, "database": a.db, "access": "banca",
                "variables": {"email": "ana@dominican.test", "pass": "demo-ana"}})
    print("accounts Ana can see:", ana.query("SELECT VALUE id FROM account").first())
```

## 10. SurrealQL cheat sheet (from our project)

```surql
-- 1. Define a namespace and database (not automatic in 3.x)
DEFINE NAMESPACE dx; DEFINE DATABASE bank;

-- 2. Create a record with a chosen ID
CREATE customer:ana SET name = 'Ana', nif = '00000000A', phone = '+34600000001';

-- 3. Create an edge with an attribute
RELATE customer:luis->owns->account:ana SET role = 'cotitular';

-- 4. Read with a graph traversal
SELECT name, ->owns->account.iban AS ibans FROM ONLY customer:ana;

-- 5. Who owns an account (incoming edges)
SELECT VALUE <-owns<-customer FROM ONLY account:ana;

-- 6. Partial update (MERGE) and an increment
UPDATE customer:ana MERGE { phone: '+34600000009' };
UPDATE account:ana SET balance -= 12.50dec;

-- 7. Upsert a settings record
UPSERT setting:limits MERGE { transfer_max: 50000dec, bizum_min: 0.50dec, bizum_max: 1000dec };

-- 8. Aggregate correctly (sum over the array, not per row)
RETURN math::sum(SELECT VALUE amount FROM entry WHERE account = account:ana);

-- 9. Group by
SELECT kind, count() AS n FROM fraud_alert GROUP BY kind;

-- 10. Idempotent insert with a deterministic array ID
INSERT IGNORE INTO fraud_alert {
    id: ['structuring', account:ana, time::floor(time::now(), 1d)],
    kind: 'structuring', score: 0.7, account: account:ana
};

-- 11. Explicit transaction
BEGIN;
LET $r = fn::transfer(account:ana, account:luis, 100dec);
COMMIT;

-- 12. Delete (root only in our bank; record users cannot delete)
DELETE owns WHERE in = customer:py123;

-- 13. Live query (WebSocket)
LIVE SELECT kind, account, device, score FROM fraud_alert;

-- 14. Time travel (SurrealKV with versioning)
SELECT id, balance FROM account:marta VERSION d'2026-10-28T10:00:00Z';

-- 15. Call a function and an endpoint from SurrealQL
RETURN fn::detect_rings_between(d'2022-08-31T00:00:00Z', d'2022-09-20T00:00:00Z', 12);
RETURN api::invoke('/transfers', { method: 'post', body: $b });

-- 16. See whether an index is used
SELECT * FROM entry WHERE txn = txn:abc EXPLAIN;

-- 17. Reconciliation: must always return nothing
RETURN fn::reconcile();
```

Common 3.x renames we hit: `type::thing` became `type::record`,
`duration::from::hours` became `duration::from_hours`, `type::is::string`
became `type::is_string`, and the fuzzy `~` operators were removed (use
`string::matches`). The full list of traps is in [README.es.md](README.es.md).
