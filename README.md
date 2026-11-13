# Dominican Express

A digital bank whose whole backend lives inside SurrealDB 3.2.4: accounts, an append-only ledger,
transfers and Bizum, cards, per-customer permissions, an HTTP API, fraud detection with a live
response and an audit trail, with no application server in front of it.

Built for the Advanced Databases course at Universidad Francisco de Vitoria (UFV). The database is
the deliverable; a native iOS app talks to it through a load balancer, and the same schema runs on
one node or on a three-store TiKV cluster.

![A mule ring forms and six fraud alerts arrive on their own in Surrealist, over a live query](docs/demo.gif)

[Watch the full demo](presentation/assets/video/demo.mp4) (4:40: live alerts, a node and a storage
leader killed during payments, the Python SDK) and the
[slides](presentation/dominican-express.pptx).

## The path of a request

![The app, HAProxy, two stateless SurrealDB nodes, PD and three TiKV stores](docs/figures/architecture.png)

The app signs in with the customer's own token and calls the database's HTTP API through HAProxy.
The SurrealDB nodes keep no state, so any of them can answer: permissions, functions and the API are
in the schema. Storage is TiKV, where Raft keeps every region on the three stores and a write counts
once two of them have it.

## Fraud, live

![The real transfer graph of the volume database, with the rings in violet](docs/figures/graph.png)

Rings, shared devices, structuring and impossible travel are found by the database itself. Alerts
are pushed to whoever listens (a `LIVE SELECT`), and an event freezes the ring accounts in
proportion: a ring is frozen, a split withdrawal only goes to review. A suspect who tries to erase
the trail is blocked, and the attempt is audited by an event that no path can skip.

![Laundering cycles found on IBM's dataset, and the prefilter](docs/figures/ibm.png)

The detector is checked on data we did not make: IBM's public anti-money-laundering set, calibrated
on one part and measured on a held-out one.

## Consistency under a race

![0 of 20 overdrafts with fn::transfer, 11 to 16 of 20 with an unsafe variant](docs/figures/race.png)

Ten simultaneous transfers of the whole balance, twenty rounds. The real transfer function updates a
stored balance, so concurrent transfers conflict on it and only one wins; it has never overdrawn. A
control variant that only sums the ledger has nothing to conflict on, and overdraws in most rounds.

## Surviving failures

![40 writes through HAProxy while node A dies, and while the TiKV leader dies](docs/figures/failover.png)

Taken from the recorded demo. A dead SurrealDB node costs nothing: HAProxy takes it out after two
failed checks and every write lands on the other one. A dead storage leader costs a few seconds of
errors while Raft elects a new one, and nothing half applied: the final count is exactly the writes
that answered OK. The health check asks `/status`, not `/health`: with `/health` a storage election
took both nodes out and 22 of 40 writes failed.

## How results are verified

![Every suite also run against code broken on purpose: 74 of 74 breaks caught](docs/figures/redteam.png)

A test only counts if it has been seen failing: each suite is also run against the code broken on
purpose, and every break is caught.

| | |
|---|---|
| Concurrency | 0 overdrafts in 20 rounds; an unsafe variant, 11 to 16 of 20 |
| Mule rings, IBM data | 33 of 54 cycles at 98.6 % precision; 8 of 12 on a held-out set (86.9 %) |
| Prefilter | IBM's 4,487,133 transfers reduced to 381 without losing a ring |
| Node A killed through HAProxy | 40 of 40 writes OK in three runs, slowest 52 ms |
| TiKV leader killed | 5 to 7 writes fail, then OK again 9 to 13 s after the kill; nothing lost |
| Tests | 6 suites; 74 of 74 breaks caught |

## Usage

Requires [SurrealDB 3.2.4](https://surrealdb.com/install). The cluster also needs TiUP and HAProxy
([db/CLUSTER.md](db/CLUSTER.md)).

```sh
curl -sSf https://install.surrealdb.com | sh -s -- --version 3.2.4 ~/.local/bin
git clone https://github.com/Dominican-Express/dominican-ios.git && cd dominican-ios
./db/demo/demo.sh up              # SurrealDB on disk, demo data loaded on first start
./db/demo/test_all.sh --quick     # the 6 test suites: expect ALL PASSED
./db/demo/demo.sh stage           # a clean bank for the live demo, then attack and coverup
./db/demo/demo.sh cluster-up      # HAProxy :8100, two SurrealDB nodes, PD, three TiKV
```

Start with [db/README.md](db/README.md).

| Document | For |
|---|---|
| [db/INSTALL.md](db/INSTALL.md) | Installation on macOS, Linux and Windows |
| [db/DEMO.md](db/DEMO.md) | The demo step by step, with the output you should see |
| [db/FUNDAMENTALS.md](db/FUNDAMENTALS.md) | SurrealDB explained with this project |
| [db/DECISIONS.md](db/DECISIONS.md) | Every engineering decision and its evidence |
| [db/REFLECTION.md](db/REFLECTION.md) | Strengths, limitations, comparison |
| [db/DATASET.md](db/DATASET.md) | The detector on IBM's AML dataset |
| [db/CLUSTER.md](db/CLUSTER.md) | The cluster and the load balancer |
| [db/APP_INTEGRATION.md](db/APP_INTEGRATION.md) | How the app talks to the database |

## The iOS app

<p>
  <img src="docs/screenshots/home.png" width="230" alt="Home screen">
  <img src="docs/screenshots/cards.png" width="230" alt="Cards screen">
</p>

SwiftUI (MVVM, async/await, Swift 6, iOS 26+), with the eight screens of the design reference. It
starts on mock data; with four launch arguments it signs in to the database and pays for real
([db/APP_INTEGRATION.md](db/APP_INTEGRATION.md)). Open `DominicanExpress.xcodeproj`, choose the
**DominicanExpress** scheme and a simulator, and press Cmd+R. Tests: `./scripts/test.sh`.

## Repository

| | |
|---|---|
| `db/` | schema, functions, API, detector, demo scripts, tests, cluster and documents |
| `Project/` | the iOS app: features, design system, the mock and the SurrealDB repositories |
| `Tests/` | Swift Testing and XCUITest |
| `presentation/` | the slides, generated by `build.py`, and the demo video |
| `docs/figures/` | `figures.py` draws the figures in this README |

## Notes

Course project by Xabier Ariznabarreta (database and architecture), Jorge Pérez (iOS app) and
Javier Pérez.

## License

The database code in `db/` is under the MIT licence ([db/LICENSE](db/LICENSE)). The IBM data sample
in `db/data/ibm-aml/` is under CDLA-Sharing-1.0, as its source.
