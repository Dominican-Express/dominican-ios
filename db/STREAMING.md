# Streaming with Kafka

Payments made in the app go through the API inside SurrealDB. A real bank also
receives payments from outside: the card network, other banks, the Bizum
gateway. Those arrive as a stream, and the fraud alerts they cause have to
reach every analyst's dashboard. This document covers how that stream enters
and leaves the bank through Apache Kafka, and why Kafka and not Redis Streams.

SurrealDB stays the source of truth. Kafka carries messages in and out; it
never decides whether a payment is valid.

```
card network, other banks ──► topic payments (key = source account, 3 partitions)
                                   │
                                   ▼
                             stream_consumer.py ──► fn::stream_apply in SurrealDB
                                                      │ pays, records the message id,
                                                      │ events and the ring sweep raise alerts
                                                      ▼
dashboards ◄── topic fraud-alerts ◄── alert_bridge.py (LIVE SELECT on every node)
```

## Why Kafka and not Redis Streams

Both are append-only logs with consumer groups, and both would run this demo.
What separates them is what happens to the messages after they are written.

| | Kafka | Redis Streams |
|---|---|---|
| Where messages live | On disk, kept for a retention period (7 days by default) whether or not they have been read | In memory, persisted by snapshots or an append file; trimmed by length or id |
| Losing an acknowledged message | With `acks=all` and `min.insync.replicas=2` on three brokers, the write is on at least two brokers before the producer gets its OK | Replication is asynchronous; `WAIT` can ask for copies, but a failover can still lose writes that were already acknowledged |
| Reading again | Any consumer group can rewind its offset and replay the topic | Possible while the entries have not been trimmed |
| Scaling one stream | A topic is split into partitions over many brokers; order is kept per key | One stream is one key, so it lives on one node; spreading it means splitting it by hand into several keys |
| Duplicates from the producer | Idempotent producer: the broker drops a retried copy | Not built in |
| Cost | A JVM process; measured here at about 340 MB of memory | Very light, and probably already there as a cache |

We chose Kafka for three reasons, all of them about money:

1. **A payment cannot disappear after it was accepted.** A queue that keeps
   messages in memory and replicates them asynchronously can lose writes it
   already acknowledged. For a notification that is acceptable; for a payment
   it is not. Kafka gives that guarantee with replication across brokers; our
   single broker shows the mechanism, not the guarantee (see Limits).
2. **The stream is a log we can read again.** It is the same idea as our
   ledger, where nothing is deleted. If a consumer lost messages, we can fix
   it, rewind the offset and replay the topic: `fn::stream_apply` skips every
   message it has already recorded, paid or rejected, and applies only the
   missing ones.
3. **Order per account at scale.** The key is the source account, so all the
   payments of one account go to one partition and arrive in order, while
   different accounts are processed in parallel. A single Redis stream would
   keep one order for everything, on one node.

Redis is the right tool for other jobs in a bank: a cache, rate limiting,
session data, short-lived notifications. We did not need any of those, so we
did not add it.

## Running it

Kafka 3.9.1 runs locally, without Docker, like SurrealDB. The first
`kafka-up` downloads it from the Apache archive (about 120 MB), checks its
SHA-512 and installs it in `~/.local/share/dominican-express/`. It needs Java
11 or newer. We use 3.9 and not 4.x because 4.x needs Java 17; the KRaft mode
is the same.

```sh
./db/demo/demo.sh up              # SurrealDB on :8099
./db/demo/demo.sh kafka-up        # Kafka on :9092, topics payments, fraud-alerts, payments-dlq
./db/demo/demo.sh stream-reset    # database `stream` with the seed, empty topics

./db/demo/demo.sh stream-consume  # terminal 1: payments into SurrealDB
./db/demo/demo.sh stream-bridge   # terminal 2: alerts from SurrealDB into Kafka
./db/demo/demo.sh stream-alerts   # terminal 3: a dashboard that reads Kafka
./db/demo/demo.sh stream-produce  # terminal 4: the scripted payments

./db/demo/demo.sh kafka-down      # stops Kafka and deletes the messages
./db/demo/demo.sh down
```

The Python scripts need `confluent-kafka` (and `websockets` for the bridge);
`demo.sh` runs them with `uv run --with`, so nothing is installed globally.

## What you should see

The producer sends 15 payments and one repeated message: normal payments, a
mule ring (ana to luis to marta to ana), a burst from sara, the burst's first
message sent again with the same id, and two payments from ring accounts.

Consumer (terminal 1):

```
p0@1     1795619524-0004    ana -> luis    900.00  done
p1@2     1795619524-0005   luis -> marta   880.00  done
p0@2     1795619524-0006  marta -> ana     860.00  done
      ring sweep: 3 accounts in rings
p0@4     1795619524-0009   sara -> luis     40.00  done
...
p0@9     1795619524-0009   sara -> luis     40.00  duplicate, not charged again
p0@10    1795619524-0014    ana -> jose     50.00  rejected (account_frozen)
p1@4     1795619524-0015   luis -> jose     40.00  rejected (account_frozen)
```

`p0@4` is partition 0, offset 4. The sweep found the ring, the alert froze the
three accounts (DECISIONS.md, 10), and their next payments are refused.

Dashboard (terminal 3), reading Kafka and not SurrealDB:

```
[0.85]  money-mule ring    account:ana   (partition 0, offset 0)
[0.85]  money-mule ring    account:luis   (partition 0, offset 1)
[0.85]  money-mule ring    account:marta   (partition 1, offset 0)
[0.60]  burst of charges   account:sara   (partition 2, offset 0)
```

## Delivery: no payment twice, no payment lost

There are two hops, and each one has its own guarantee.

**Producer to Kafka.** `acks=all` and the idempotent producer: if the broker's
reply is lost and the producer retries, the broker drops the copy. With one
broker, `acks=all` waits for that broker only; with three and
`min.insync.replicas=2` it waits for two.

**Kafka to SurrealDB.** Kafka delivers at least once. The consumer pays first
and commits the offset only after SurrealDB answers OK. If it dies in
between, Kafka delivers the message again. `fn::stream_apply`
(`schema/11_stream.surql`) records the message id in `stream_msg` in the same
transaction as the payment, so the second copy finds the record and does not
pay. If two copies arrive at once, they write the same record, one is undone
by the write conflict and its retry sees the first. A rejection is final for
its id, like a payment: replaying does not retry it, and a payment that should
be tried again is a new message with a new id. A different message that
reuses an id already seen is refused as `id_reused`: the record keeps a
SHA-256 of the content (accounts, amount and kind), and a true copy has the
same one. It is the mechanism of the
API's idempotent payment orders and of the materialised balance
([FUNDAMENTALS.md](FUNDAMENTALS.md), isolation).

**Malformed messages.** A message that cannot be read (not JSON, a missing
field, an amount like `1.`, a kind other than `transfer`, `bizum` or
`payroll`) goes to the topic `payments-dlq` with the reason
in a header, and its offset is committed. Without that, Kafka would hand the
same message back after every restart and the consumer would stop on it
forever, with the whole partition behind it. If the copy to `payments-dlq`
fails, the offset is not committed.

**The test** (`demo.sh stream-test`, about 1 min) publishes 2 malformed
messages and 60 payments, kills the consumer at message 25, at the worst
moment for each mode, then starts it again until the topic is empty:

| Consumer mode | Transfers applied | |
|---|---|---|
| `safe`: pay, record the id, then commit | 60 of 60 | correct |
| `no-dedup`: pay without recording the id | 61 of 60 | the redelivered message is paid twice |
| `commit-first`: commit, then pay | 59 of 60 | the message is lost |

In all three the total balance is unchanged, `fn::reconcile()` is empty and
the 2 malformed messages are in `payments-dlq`: the ledger is never half
written, the damage is a whole payment too many or too few. The two wrong
modes are there so that the test is seen failing; if either gave 60, the test
would not be checking what it claims. Then, without Kafka, 8 copies of one
message sent at once are paid once, and a different message with the same id
is refused as `id_reused`. Both checks were also run against code broken on
purpose (the consumer without the dead-letter topic: 0 of 60, stuck on the
first malformed message; `fn::stream_apply` without the content check: the
reused id accepted) and failed, as they should.

## Order and scaling

The message key is the source account. Kafka sends all messages with the same
key to the same partition and keeps their order inside it, so the payments of
one account are applied in the order they were sent.

All consumers in the group `ledger` share the partitions: start two and Kafka
gives each its share. Stop one with Ctrl-C and it hands its partitions over at
once; if it crashes, the group waits 6 s (`session.timeout.ms`) before giving
them to the other. Two consumers can still pay into the same destination
account at once; the conflict on its balance undoes one and the consumer
retries it.

## Alerts out: one topic for every node

A `LIVE SELECT` only sees the changes made through its own node; live queries
across nodes are an Enterprise feature ([REFLECTION.md](REFLECTION.md)). With
two subscribers on one node we also measured lost notifications, 23 and 24 of
30, without an error.

`alert_bridge.py` opens one `LIVE SELECT` per node (`SURREAL_WS`, comma
separated) and publishes every alert into `fraud-alerts`, keyed by account.
Dashboards read Kafka, so a dashboard sees every alert whichever node created
it, and a dashboard started late reads the alerts from the beginning of the
topic.

A live query keeps nothing for a client that was not listening. So the
bridge, on start, opens its live query first and then publishes the alerts
already stored in the table. In that order there is no gap; the cost is that
an alert can be published twice, and the dashboard drops repeated ids.

Each dashboard uses its own consumer group, so each one gets every alert. Two
processes with the same group would split the alerts between them: that is
the difference between one screen per analyst and a team of workers sharing a
queue.

## Limits

- **One broker.** Every partition has one copy, so this shows topics,
  partitions, groups and offsets, not Kafka's own fault tolerance: if this
  broker lost its disk, acknowledged messages would be gone. Production would
  run three brokers with replication factor 3 and `min.insync.replicas=2`, the
  same majority idea as Raft in TiKV.
- **The ring sweep runs every 2 s**, not per message: graph search is too
  expensive for the payment path (DECISIONS.md, 7). The burst detector runs
  inside each payment.
- **The consumer signs in as root**, like the other bank-side scripts. A
  deployment would give it a database user that can only call
  `fn::stream_apply`.
- **Throughput not measured.** The consumer applies one message per request
  and commits each offset synchronously, which is simple to reason about and
  slow. Batching would be the next step.
