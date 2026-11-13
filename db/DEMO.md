# Demo guide

Step by step, with the output you should see. Install first: [INSTALL.md](INSTALL.md).
All commands run from the repository root. Every query says **which database**
to select in Surrealist (namespace is always `dx`) and, where it matters,
which **query mode**.

```sh
./db/demo/demo.sh up        # if it is not running yet
```

Surrealist: connection `ws://127.0.0.1:8099`, Root `root` / `root`, namespace `dx`.

| Part | What it shows | Time |
|---|---|---|
| [A](#a-the-model-database-bank) | Documents + graph in one model | 3 min |
| [B](#b-live-fraud-response-database-live) | Live alerts, proportional freeze, nothing can be erased | 5 min |
| [C](#c-concurrency-terminal) | ACID under a race: the safe vs the unsafe transfer | 1 min |
| [D](#d-permissions-terminal) | Customers only see their own data | 1 min |
| [E](#e-python-with-the-official-sdk-terminal) | Insert, query, update, delete from Python; live query | 1 min |
| [F](#f-rings-at-scale-database-volume) | Graph detection on a generated bank | 2 min |
| [G](#g-independent-data-database-aml) | The detector on IBM's public AML dataset | 2 min |
| [H](#h-a-cluster-that-survives-a-dead-node-terminal) | 3 TiKV nodes: kill one during writes, bring it back | 3 min |

---

## A. The model (database `bank`)

**Explorer** (left menu): tables `customer`, `account`, `entry` (the ledger),
and relation tables `owns`, `transfer`, `uses`. **Designer** draws the schema.

In **Query**, database `bank`:

```sql
-- who owns what: a graph traversal from a document
SELECT name, ->owns->account.iban AS ibans FROM customer;

-- the other direction: the holders of Ana's account, with the role on the edge
SELECT <-owns<-customer.name AS holders, <-owns.role AS roles FROM account:ana;
```

Expected: Ana and Luis both hold `account:ana` (`titular`, `cotitular`). The
co-holder is an attribute of the **edge**, not a join table.

```sql
-- the mule ring the sweep found; switch the result view to Graph
SELECT VALUE account FROM fraud_alert WHERE kind = 'mule_ring';
```

Three accounts (Ana, Luis, Marta) joined by the transfers that went round.

---

## B. Live fraud response (database `live`)

**1. Reset** `live` (terminal):

```sh
./db/demo/demo.sh stage
# live: 5 customers, no attack yet
```

**2. Subscribe** (Surrealist, database `live`, switch the query mode to **Live**):

```sql
LIVE SELECT kind, account, device, score FROM fraud_alert;
```

**3. Attack** (terminal):

```sh
SURREAL_DB=live ./db/demo/demo.sh attack
```

Six alerts appear in Surrealist as they are created, without refreshing:

| kind | on | score |
|---|---|---|
| `impossible_travel` | account:ana | 0.9 |
| `mule_ring` | account:ana, account:luis, account:marta | 0.85 |
| `shared_device` | device:mula | 0.75 |
| `structuring` | account:jose | 0.7 |

**4. The response was proportional** (normal query mode, `live`):

```sql
SELECT id, frozen_at != NONE AS frozen, review_at != NONE AS in_review
FROM account WHERE frozen_at != NONE OR review_at != NONE;
```

Ana, Luis and Marta are **frozen** (mule ring: money cannot leave; incoming
money still arrives). José is only **in review** (structuring can be innocent).
Sara does not appear. No application code did this: an event on `fraud_alert`
did, inside the database (`schema/10_controls.surql`).

**5. The mules try to cover their tracks** (terminal):

```sh
SURREAL_DB=live ./db/demo/demo.sh coverup
```

```
Marta (one of the mules) tries to cover her tracks:

  BLOCKED  delete the shared phone straight from the database  → no permission, the phone is still there
  BLOCKED  move her money out  → HTTP 423 account_frozen
  BLOCKED  unlink the phone in the app  → HTTP 200, but it is only marked as ended (kept), not deleted

The audit log recorded it: app_user:marta
```

The API answers `account_frozen` and nothing else: telling a money-laundering
suspect they are under investigation is illegal in Spain (art. 24, Ley 10/2010).

**6. Who did what** (`live`):

```sql
SELECT at, action, tbl, actor, via FROM audit_log WHERE actor != NONE ORDER BY at DESC;
```

One row: `UPDATE` on `uses` by `app_user:marta` via `banca` (the app). The audit
trail is written by events: there is no path that skips it.

**7. An insider with root access** (terminal):

```sh
SURREAL_DB=live ./db/demo/demo.sh insider
# an insider with root deleted the shared phone, removed a co-holder and drained an account
# every step is in audit_log; fn::investigate rebuilds the alert as it was
```

Root *can* delete. Investigate the shared-device alert as it was when it fired
(`live`):

```sql
RETURN fn::investigate((SELECT VALUE id FROM fraud_alert WHERE kind = 'shared_device')[0]);
```

Look for: `changes` lists `device_deleted` with the four customers who used it;
`owners_then` of `account:ana` has Luis, `owners_now` does not; Marta's
`balance_then` is 3220 and `balance_now` 0. The time machine (versioned
storage) shows the state before the cover-up. It is an investigation tool, not
the evidence store: see [DECISIONS.md](DECISIONS.md).

---

## C. Concurrency (terminal)

```sh
./db/demo/demo.sh race
```

```
10 simultaneous transfers of the full balance, 20 rounds each

fn::transfer  ->  0/20 rounds ended in an overdraft
fn::transfer_unsafe  ->  12/20 rounds ended in an overdraft
```

The unsafe count varies from run to run (11 and 12 out of 20 in ours); the safe
one is always 0. Ten transfers of the whole balance at once: only one may
succeed. The safe version writes `account.balance`, so concurrent transactions
conflict and all but one are rejected; the unsafe version only appends to the
ledger and lets the race through. It uses its own database (`race`), recreated
every time.

---

## D. Permissions (terminal)

```sh
./db/demo/demo.sh access
```

Signs in as Ana and Luis (record access) and tries to read what is not theirs.
Output is in Spanish; every line must be `[ok   ]` and the last `TODO EN ORDEN`.
Examples: Ana does not see other accounts; Luis, co-holder of Ana's account,
sees it but not Ana's card number, even after verifying his PIN.

---

## E. Python with the official SDK (terminal)

```sh
./db/demo/demo.sh sdk
```

Six sections, in order: **create** a customer with an account and an `owns`
edge; **read** it and traverse the graph; **update** (an invalid phone is
rejected by the schema, not by the app); a **customer session** where Ana sees
only her account, pays through the API, and a retry of the same order is charged
once, while her attempt to delete her ledger entries removes nothing; staff
**delete**s the test customer and the audit trail shows CREATE, UPDATE, DELETE;
a **live query** receives three `mule_ring` alerts while a ring forms, and the
accounts end up frozen.

It runs in its own database, `sdk`, recreated each time, so it works before or after part B (after the attack Ana is frozen in `live`, and her payment would be refused with 423).

---

## F. Rings at scale (database `volume`)

300 generated customers, 60 days, fraud planted by the generator. In **Query**,
database `volume`, result view **Graph**:

```sql
SELECT VALUE account FROM fraud_alert WHERE kind = 'mule_ring';
```

Six planted rings over 22 accounts. Some share accounts, so the graph shows
fewer islands than rings. The naive cycle search took 53 s and flagged 75
innocent accounts at 100 customers; the forwarding rule finds every planted
ring with none (see [DECISIONS.md](DECISIONS.md)).

Never run `SELECT *` without `LIMIT` here in Graph view: Surrealist tries to draw
everything.

---

## G. Independent data (database `aml`)

```sh
./db/demo/demo.sh aml
# aml: IBM sample loaded and swept (expected: 20 mule_ring, 191 possible_ring)
```

In **Query**, database `aml`:

```sql
SELECT kind, count() AS n FROM fraud_alert GROUP BY kind;
-- [{ kind: 'mule_ring', n: 20 }, { kind: 'possible_ring', n: 191 }]

-- do the flagged accounts really launder? IBM's labels, kept apart from the detector
LET $flagged = (SELECT VALUE account FROM fraud_alert WHERE kind = 'mule_ring');
SELECT pattern, count() AS transfers FROM aml_truth WHERE src IN $flagged GROUP BY pattern;
```

Strict rings freeze (100 % precision on both IBM sets); rings only the wide rule
sees go to review (one in eight would be innocent on unseen data). The full
story and how to reproduce every number: [DATASET.md](DATASET.md).

---

## H. A cluster that survives a dead node (terminal)

Needs TiUP once ([CLUSTER.md](CLUSTER.md), step 1). Start it before the
presentation: the first start downloads ~110 MB, later ones take 15 s.

```sh
./db/demo/demo.sh cluster-up       # 1 PD + 3 TiKV + SurrealDB nodes A (:8101) and B (:8102)
./db/demo/demo.sh cluster-status   # which TiKV leads which regions
./db/demo/demo.sh cluster-write 40 # terminal 1: writes through A, then counts through B
./db/demo/demo.sh cluster-kill     # terminal 2, during the writes: SIGKILL the busiest TiKV
./db/demo/demo.sh cluster-revive   # it comes back and catches up
./db/demo/demo.sh cluster-down     # stop it all (about 45 s) and delete the cluster data
```

If the dead TiKV led the region being written, a few writes fail **with an
error** for 9 to 12 s while Raft elects a new leader, then everything continues
on the other two; node B counts exactly the writes that answered OK. If it led
other regions, nothing is visible. Full results and what does not work on
TiKV: [CLUSTER.md](CLUSTER.md).

---

## Finish

```sh
./db/demo/demo.sh down
```
