# Running a cluster: SurrealDB on TiKV

The rest of the project runs on one SurrealDB node. This guide runs the same
schema on a small distributed cluster on one laptop and shows what a cluster
gives a bank: **replication** (every piece of data on 3 machines),
**fault tolerance** (kill one, keep working) and **stateless compute** (any
SurrealDB node serves any request). The concepts are in
[FUNDAMENTALS.md, section 5](FUNDAMENTALS.md#5-storage-engines-and-architecture).

Every number and every output below was measured on a MacBook Air M3 (16 GB)
with SurrealDB 3.2.4, TiKV and PD v8.5.8, TiUP 1.17.1.

## What runs

```
            client (curl, Surrealist, the Python SDK)
               |                         |
     SurrealDB node A :8101     SurrealDB node B :8102     stateless: parse, check
               |                         |                 permissions, run functions
               +-----------+-------------+
                           |  tikv://127.0.0.1:2379
                     PD (placement driver)                 knows where every region lives
               +-----------+-------------+
             TiKV 1      TiKV 2      TiKV 3                each region on all 3,
                                                           kept in sync by Raft
```

All of it on one machine, started with **TiUP playground**, PingCAP's tool for
local TiKV clusters. A real deployment puts each TiKV and PD on its own host
(3 PD for a highly available placement driver) and uses `tiup cluster`
instead; the software and the behaviour are the same.

## Cost on a laptop

| | Measured |
|---|---|
| Download, first start only | TiUP 12 MB, then PD 59 MB and TiKV 45 MB (compressed) |
| Disk, permanent | `~/.tiup`: 299 MB (binaries) |
| Disk, while the cluster runs | 141 MB of cluster data, removed by `cluster-down` |
| RAM, cluster idle | about 1.1 GB: 3 TiKV 806 MB, PD 104 MB, 2 SurrealDB 161 MB, TiUP 31 MB |
| CPU, cluster idle | about 2 % |
| Start, after the first time | 15 s |
| Stop | about 45 s (TiKV shuts down cleanly) |

Two defaults would have cost much more, and `cluster/tikv.toml` turns them down:
each TiKV reserves a **5 GB placeholder file** on disk (15 GB for three), and
its block cache takes **about 45 % of RAM** per node. We checked the
placeholder is not created (`find ~/.tiup -name 'space_placeholder*'` finds
nothing).

## Step 1: install TiUP

macOS or Linux (on Windows, inside WSL; TiUP has no native Windows build):

```sh
curl --proto '=https' --tlsv1.2 -sSf https://tiup-mirrors.pingcap.com/install.sh | sh
```

No `sudo`. It installs into `~/.tiup` and appends `~/.tiup/bin` to your PATH
in your shell's startup file (`~/.zshrc` for zsh). Open a new terminal, or
skip that step: `demo.sh` finds `~/.tiup/bin/tiup` on its own. Check:

```sh
~/.tiup/bin/tiup --version     # 1.17.1 or later
```

To remove everything later: `rm -rf ~/.tiup` and delete that PATH line.

## Step 2: start the cluster

SurrealDB 3.2.4 must be installed (see [INSTALL.md](INSTALL.md)). From the
repository root:

```sh
./db/demo/demo.sh cluster-up
```

```
starting 1 PD + 3 TiKV v8.5.8 (the first time downloads ~110 MB)…
cluster up: PD 127.0.0.1:2379, 3 TiKV, SurrealDB nodes on :8101 (A) and :8102 (B)
schema and seed loaded in dx/cluster through node A
remember: ./db/demo/demo.sh cluster-down when you finish
```

It needs ports 2379 (PD), 20160 to 20162 (TiKV), 8101 and 8102 free. It does
not touch the single-node database on 8099.

```sh
./db/demo/demo.sh cluster-status
```

```
store  address            state         leaders regions
1      127.0.0.1:20160    Up                  5       5
5      127.0.0.1:20162    Up                  0       5
2      127.0.0.1:20161    Up                  0       5
surreal :8101 up
surreal :8102 up
```

Every TiKV holds all 5 regions (3 copies of each); one copy of each region is
the Raft **leader**, which serves its reads and writes.

## Step 3: write on one node, read on the other

```sh
curl -s -u root:root -H 'surreal-ns: dx' -H 'surreal-db: cluster' -H 'Accept: application/json' \
  http://127.0.0.1:8101/sql --data-binary "CREATE note:hello SET text = 'written through node A';"
curl -s -u root:root -H 'surreal-ns: dx' -H 'surreal-db: cluster' -H 'Accept: application/json' \
  http://127.0.0.1:8102/sql --data-binary "SELECT * FROM note:hello; SELECT name FROM customer;"
```

Node B returns the note at once, and the five customers the seed loaded
through node A. Neither SurrealDB node keeps data: both read the same TiKV
cluster. In Surrealist you can open one connection to `ws://127.0.0.1:8101`
and another to `ws://127.0.0.1:8102` (root / root, namespace `dx`, database
`cluster`) and do the same by hand.

## Step 4: kill a storage node and keep working

Two terminals. In the first, 40 writes through node A, one every 0.25 s:

```sh
./db/demo/demo.sh cluster-write 40
```

In the second, while it runs, kill with `SIGKILL` (a crash, not a clean stop)
the TiKV that leads the most regions:

```sh
./db/demo/demo.sh cluster-kill
```

What happens depends on whether the dead node led the region being written.
We ran it three ways:

| Killed | Writes during the run | Recovery |
|---|---|---|
| A follower (led nothing) | 20 of 20 OK, slowest 45 ms | nothing to recover |
| The leader of 3 of 5 regions, not of the one being written | 40 of 40 OK, slowest 44 ms | nothing visible |
| The leader of all 5 regions (two runs) | 5 and 7 failed with an error, then OK again | writes resumed 9 to 12 s after the kill |

The hard case, from our run (trimmed):

```
11:42:02 beat:9  OK     42 ms
         (TiKV killed)
11:42:04 beat:10 ERROR  1579 ms
...                                   five writes fail, about 1.6 s each
11:42:13 beat:15 OK     1576 ms
11:42:14 beat:16 OK       42 ms      back to normal on the other two TiKV
```

Node A logged `gRPC api error: code: 'The service is currently unavailable'`.
What matters for a bank:

- **No write was lost and none was half applied.** Node B counted exactly the
  writes that had answered OK (35 of 40, and 33 of 40 in the second run); the
  ones that failed are not there.
- **The client is told.** A failed write returns an error, never a silent
  success. Our payment API takes an idempotency key
  ([DECISIONS.md, section 2](DECISIONS.md#2-no-java-backend-the-api-lives-inside-the-database)), so the app can retry the same
  payment safely.
- **9 to 12 s of unavailability for the affected regions**, while Raft notices
  the leader is gone and elects a new one. This is the CP choice of
  [FUNDAMENTALS.md](FUNDAMENTALS.md#5-storage-engines-and-architecture): refuse
  briefly rather than risk two versions of a balance.

## Step 5: bring it back

```sh
./db/demo/demo.sh cluster-revive
```

```
TiKV 127.0.0.1:20160 is back; it catches up from the other two
```

It restarts the killed TiKV on its own data directory; it is `Up` again in
about 10 s and catches up from the Raft log of the other two. To prove it had
caught up we moved the leadership of every region to it (PD API,
`transfer-leader`) and read through node B: it returned all 35 writes,
including the ones made while it was dead.

## Step 6: stop

```sh
./db/demo/demo.sh cluster-down
```

Stops the two SurrealDB nodes, PD and the three TiKV (only the processes this
cluster started) and deletes the cluster data. The binaries stay in `~/.tiup`.

## What works on TiKV, and what does not

We ran the six test suites against the cluster, through node B:

| Suite | On TiKV |
|---|---|
| access, payments, cards, detect, controls | all checks pass |
| time_travel | fails: `The underlying datastore does not support versioned queries` |

**Time travel needs SurrealKV.** `SELECT ... VERSION` is a SurrealKV feature;
TiKV keeps versions internally (MVCC) but SurrealDB 3.2.4 does not expose
them.

**Live queries do not cross nodes.** We opened a `LIVE SELECT` on node B and
wrote 5 records through B and 5 through A. Node B was notified of **5 of 5**
written through B and **0 of 5** written through A. Distributed live queries
are listed by SurrealDB as an Enterprise feature. For our fraud alerts this
means: on a cluster, a dashboard must listen on every node, or alerts must be
written through the node it listens on.

That is why the live demo and the time machine stay on a single SurrealKV
node, and the cluster is the demonstration of replication and fault tolerance.

## Traps we hit

- **Starting with 1 TiKV and adding more leaves one copy of the data.**
  Playground sets `max-replicas` from the number of TiKV it starts with, and
  does not raise it on `scale-out`. With 3 TiKV up, every region still had 1
  copy until we set it by hand (`POST /pd/api/v1/config/replicate
  {"max-replicas":3}`); then PD made the copies in under 5 s. `cluster-up`
  starts with 3 and sets it anyway.
- **Playground does not restart a crashed TiKV**, and on Ctrl+C it does not
  always stop the others (one left without a majority kept running elections).
  `cluster-revive` and `cluster-down` handle both by PID.
- **`LIVE SELECT` on a table that does not exist yet** returns an error. Our
  schema defines every table, so it only matters for ad hoc tests.

## Doing it by hand

What `cluster-up` runs, without the script:

```sh
tiup playground v8.5.8 --mode tikv-slim --pd 1 --kv 3 --without-monitor \
     --tag dominican-express --kv.config db/cluster/tikv.toml
curl -s -X POST http://127.0.0.1:2379/pd/api/v1/config/replicate -d '{"max-replicas":3}'
surreal start --username root --password root --bind 127.0.0.1:8101 tikv://127.0.0.1:2379
surreal start --username root --password root --bind 127.0.0.1:8102 tikv://127.0.0.1:2379
SURREAL_URL=http://127.0.0.1:8101 SURREAL_DB=cluster ./db/demo/apply.sh
SURREAL_URL=http://127.0.0.1:8101 SURREAL_DB=cluster ./db/demo/surql.sh 01_seed.surql
```

`--without-monitor` skips Prometheus and Grafana, which playground starts by
default. PD's HTTP API shows the state: `curl -s http://127.0.0.1:2379/pd/api/v1/stores`.

## What this does not show

Separate machines, network partitions between them, a load balancer in front
of the SurrealDB nodes, and performance: three TiKV on one laptop share one
disk and one CPU, so throughput here says nothing about a real cluster.
