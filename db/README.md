# Dominican Express: the database

A bank backend built entirely inside **SurrealDB 3.2.4**: accounts, a ledger
that cannot be edited, transfers and Bizum, cards, customer permissions, an
HTTP API, real-time fraud alerts with an automatic and proportional response,
an audit trail and a time machine for investigations. There is no application
server: the iOS app and the web talk to the database directly.

University project (Advanced Databases, UFV). The database is the deliverable.

## Start in four commands

```sh
curl -sSf https://install.surrealdb.com | sh -s -- --version 3.2.4 ~/.local/bin
git clone https://github.com/Dominican-Express/dominican-ios.git && cd dominican-ios
./db/demo/demo.sh up          # SurrealDB on disk, demo data loaded on first start
./db/demo/test_all.sh --quick # the 6 test suites, ~15 s: expect ALL PASSED
```

Then connect Surrealist to `ws://127.0.0.1:8099` (root / root, namespace `dx`)
and follow [DEMO.md](DEMO.md). Stop with `./db/demo/demo.sh down`.

## Documents

| Read | For |
|---|---|
| [INSTALL.md](INSTALL.md) | Requirements, installation on macOS, Linux and Windows, first start, troubleshooting |
| [DEMO.md](DEMO.md) | The demo step by step: which database, which query, what you should see |
| [FUNDAMENTALS.md](FUNDAMENTALS.md) | SurrealDB explained with this project: data model, consistency, storage engines, distribution, security, SurrealQL cheat sheet |
| [DECISIONS.md](DECISIONS.md) | Every engineering decision: alternatives, evidence, costs |
| [REFLECTION.md](REFLECTION.md) | Strengths and limitations we observed, comparison, where SurrealDB fits |
| [DATASET.md](DATASET.md) | The fraud detector tested on IBM's public anti-money-laundering dataset |
| [CLUSTER.md](CLUSTER.md) | The same schema on a 3-node TiKV cluster: replication, killing a node, recovery |
| [APP_INTEGRATION.md](APP_INTEGRATION.md) | How the iOS app or the web talks to the database: sign-in, queries, endpoints, retries |
| [README.es.md](README.es.md) | The full development log in Spanish, with every measurement and every SurrealQL trap we hit |

## What is where

```
db/
├── schema/                 the whole backend, applied in order
│   ├── 01_core.surql       customers, accounts, append-only ledger, cards
│   ├── 02_graph.surql      relations: owns, transfer, uses, favorite; alerts
│   ├── 03_functions.surql  transfer, credit, balance (ACID, conflict-safe)
│   ├── 04_events.surql     in-transaction fraud checks (velocity, impossible travel)
│   ├── 05_detectors.surql  sweeps: mule rings (two tiers), shared devices, structuring
│   ├── 06_access.surql     record access for app users, PIN step-up
│   ├── 07_api.surql        HTTP endpoints inside the database (DEFINE API)
│   ├── 08_cards.surql      card payments, limits, notifications
│   ├── 09_time_travel.surql investigate an alert as it was (versioned storage)
│   └── 10_controls.surql   freeze, nothing is deleted, audit trail
├── demo/                   demo script, tests, red teams, benchmarks, IBM tools, Python client
├── cluster/                local TiKV cluster (cluster.sh, tikv.toml), see CLUSTER.md
└── data/ibm-aml/           6.5 MB sample of IBM's AML dataset (CDLA-Sharing-1.0)
```

## In numbers

| | |
|---|---|
| Concurrency | 10 simultaneous full-balance transfers: 0 overdrafts in 20 rounds (an unsafe variant: 11 to 13 of 20) |
| Mule rings, own data | naive cycle search 53 s and 75 false positives; forwarding rule 0.03 s and 0 (100 customers) |
| Mule rings, IBM data | 6 of 54 laundering cycles found before calibration; 33 of 54 after (98.6 % precision), 8 of 12 on a held-out set (86.9 %) |
| Prefilter | IBM's 4,487,133 transfers reduced to 381 without losing a ring |
| Tests | 6 suites; every test also run against code broken on purpose: 74 of 74 breaks caught |
| Cluster | 3 TiKV: a crashed follower goes unnoticed; a crashed leader, 9 to 12 s of errors and no write lost |

Where each number comes from: [DECISIONS.md](DECISIONS.md) and [DATASET.md](DATASET.md).

## Limits we declare

The cluster runs on one laptop: it shows replication and failover, not
performance across machines ([CLUSTER.md](CLUSTER.md)). On TiKV there is no
time travel, and live queries do not cross nodes. Fraud thresholds are calibrated on
synthetic data. The audit trail lives in the same database; a real bank copies
it out to write-once storage. More in [REFLECTION.md](REFLECTION.md).

## Licence

Code: MIT ([LICENSE](LICENSE)). The IBM data sample in `data/ibm-aml/` keeps
its own licence, CDLA-Sharing-1.0.
