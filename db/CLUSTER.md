# Running a cluster: SurrealDB on TiKV

The rest of the project runs on one SurrealDB node. This guide runs the same
schema on a small distributed cluster on one laptop and shows what a cluster
gives a bank: **replication** (every piece of data on 3 machines),
**fault tolerance** (kill one, keep working), **stateless compute** (any
SurrealDB node serves any request) and **one entry point**: a load balancer
in front of the SurrealDB nodes, which is what the app talks to. The concepts are in
[FUNDAMENTALS.md, section 5](FUNDAMENTALS.md#5-storage-engines-and-architecture).

Every number and every output below was measured on a MacBook Air M3 (16 GB)
with SurrealDB 3.2.4, TiKV and PD v8.5.8, TiUP 1.17.1, HAProxy 3.4.7.

## What runs

```
        client (the iOS app, curl, Surrealist, the Python SDK)
                           |
                    HAProxy :8100                          one entry point: spreads requests,
                           |                               takes a dead node out (stats :8404)
               +-----------+-------------+
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
(3 PD for a highly available placement driver), terminates TLS at the load
balancer and runs two of them, and uses `tiup cluster` instead; the software
and the behaviour are the same.

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

## Step 1: install TiUP and HAProxy

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

HAProxy, the load balancer (6.3 MB): `brew install haproxy` on macOS,
`sudo apt install haproxy` on Debian or Ubuntu. Check: `haproxy -v` (3.x).

## Step 2: start the cluster

SurrealDB 3.2.4 must be installed (see [INSTALL.md](INSTALL.md)). From the
repository root:

```sh
./db/demo/demo.sh cluster-up
```

```
starting 1 PD + 3 TiKV v8.5.8 (the first time downloads ~110 MB)…
cluster up: HAProxy :8100 -> SurrealDB nodes :8101 (A), :8102 (B) -> PD :2379 -> 3 TiKV
schema and seed loaded in dx/cluster; HAProxy stats on http://127.0.0.1:8404
remember: ./db/demo/demo.sh cluster-down when you finish
```

It needs ports 2379 (PD), 20160 to 20162 (TiKV), 8100 and 8404 (HAProxy),
8101 and 8102 free. It does
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
haproxy sees node A UP
haproxy sees node B UP
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

Two terminals. In the first, 40 writes through HAProxy, one every 0.25 s
(each line says which SurrealDB node served it):

```sh
./db/demo/demo.sh cluster-write 40
```

In the second, while it runs, kill with `SIGKILL` (a crash, not a clean stop)
the TiKV that leads the most regions:

```sh
./db/demo/demo.sh cluster-kill
```

What happens depends on whether the dead node led the region being written.
We ran it four ways (the first three writing straight to node A, before we
added the load balancer; the last one through HAProxy):

| Killed | Writes during the run | Recovery |
|---|---|---|
| A follower (led nothing) | 20 of 20 OK, slowest 45 ms | nothing to recover |
| The leader of 3 of 5 regions, not of the one being written | 40 of 40 OK, slowest 44 ms | nothing visible |
| The leader of all 5 regions (two runs) | 5 and 7 failed with an error, then OK again | writes resumed 9 to 12 s after the kill |
| The leader of all 5 regions, through HAProxy (two runs) | 6 and 7 failed with an error, then OK again | writes resumed about 13 s after the kill |

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

## Step 6: kill a SurrealDB node

The other half of the cluster: the compute nodes. Same two terminals, and this
time kill (`SIGKILL`) SurrealDB node A while the writes go through HAProxy:

```sh
./db/demo/demo.sh cluster-write 40      # terminal 1
./db/demo/demo.sh cluster-kill-node     # terminal 2, while it runs
```

From our run (trimmed):

```
19:35:45  write 9 via HAProxy -> node A: OK 49 ms
19:35:45  write 10 via HAProxy -> node B: OK 41 ms
          (node A killed)
19:35:45  write 11 via HAProxy -> node B: OK 44 ms
...                                          every write now goes to B
19:35:55  write 40 via HAProxy -> node B: OK 46 ms
the cluster now holds: 40 beats in total
```

Three runs, **40 of 40 writes OK every time, none slower than 52 ms**. The
requests alternate A, B, A, B until A dies; from then on all go to B. The
request that tries A after it died fails to connect, and HAProxy sends it to B
before anything was sent, so the client never sees an error. HAProxy takes A
out of the rotation after two failed health checks; `./db/demo/demo.sh
cluster-revive-node` starts it again and it goes back in after two good ones.
The page at http://127.0.0.1:8404 shows each node turn red and green.

## Step 7: stop

```sh
./db/demo/demo.sh cluster-down
```

Stops HAProxy, the two SurrealDB nodes, PD and the three TiKV (only the processes this
cluster started) and deletes the cluster data. The binaries stay in `~/.tiup`.

## The load balancer

**Why one.** The SurrealDB nodes keep no state, so any of them can serve any
request. Without a balancer the app would have to know every node and decide
itself which one is alive. With one, the app has a single address, the load is
spread, and a dead node is taken out before the app notices (step 6). It is
the usual design in front of stateless services.

**Why HAProxy.** It checks every node actively, once a second, so a dead node
leaves the rotation even when no request has failed yet; the free version of
nginx only notices when a real request fails. It passes WebSockets (the SDKs
and live queries), can retry on another node, and has a status page. Caddy
would also work, with less control over retries.

**How it is configured** (`cluster/haproxy.cfg`):

| Setting | Why |
|---|---|
| `balance roundrobin` | requests take turns between A and B |
| health check `GET /status` every 1 s, out after 2 failures, back after 2 successes | a dead node leaves in about 2 s |
| `retry-on conn-failure` + `redispatch` | retry on the other node **only if the connection failed**, so the request was never sent: a payment can never reach the database twice because of the balancer (and if it did, the order `id` makes it idempotent) |
| `timeout tunnel 1h` | a WebSocket stays open on the node where it started |
| `X-Served-By` response header | shows which node answered |

**The health check must not test what all nodes share.** Our first version
checked `/health`, which also checks the storage. When the TiKV leader died,
both nodes answered `/health` too slowly, HAProxy took **both** out ("backend
has no server available") and answered errors itself until they passed two
checks again: **22 of 40 writes failed**, against 5 to 7 with no balancer at
all. The balancer was making a storage failure worse. With `/status` (is this
node alive?) the same test gave 6 and 7 failures, all of them from the storage
election, none from HAProxy. If what fails is shared by every node, taking
nodes out fixes nothing.

**Live queries through a balancer.** A WebSocket goes through HAProxy fine: a
live query opened through it got 3 of 3 changes made on the same connection,
in three runs. But the connection stays on one node, and live queries do not
cross nodes. With the live query open through HAProxy and 10 writes spread by
HAProxy over A and B, it received **5 of 10** in each of three runs: all the
writes that landed on its own node, none from the other. So, in this
architecture, a fraud dashboard listens on every node (one connection per
node), and the app reads its alerts again when it reconnects, instead of
trusting a single live query.

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

- **A health check on a shared dependency.** `/health` checks the storage too;
  with it HAProxy removed both nodes during a TiKV election and turned 6 or 7
  failed writes into 22. Use `/status` (see "The load balancer").
- **Our own test lost live notifications.** A test client that waits for the
  reply to its own query and throws away everything else also throws away the
  live notifications that arrive in between: it reported 0 of 3. Counting
  them while waiting gave 3 of 3.

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
haproxy -f db/cluster/haproxy.cfg
SURREAL_URL=http://127.0.0.1:8101 SURREAL_DB=cluster ./db/demo/apply.sh
SURREAL_URL=http://127.0.0.1:8101 SURREAL_DB=cluster ./db/demo/surql.sh 01_seed.surql
```

`--without-monitor` skips Prometheus and Grafana, which playground starts by
default. PD's HTTP API shows the state: `curl -s http://127.0.0.1:2379/pd/api/v1/stores`.

## What this does not show

Separate machines, network partitions between them, a second load balancer
(here HAProxy itself is a single point of failure; in production two of them
share a floating address), TLS, and performance: three TiKV on one laptop share one
disk and one CPU, so throughput here says nothing about a real cluster.
