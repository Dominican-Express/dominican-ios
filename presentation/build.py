"""Genera presentation/dominican-express.pptx (18 diapositivas, notas del orador).

    uv run --with python-pptx --with matplotlib --with pillow --with qrcode --with networkx python presentation/build.py

Diseño: Brainstorm/slides-design.md en x-brain; cifras: db/*.md (ver README.md).
"""
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

import qrcode
from pptx import Presentation
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches as I

import charts
from style import (BG, CARD, H, LILAC, LINE, MARGIN, MONO, MUTED, PINK, TEXT, TOP,
                   VIOLET, W, arrow, box, frame, grid, picture, text)

REPO = "github.com/Dominican-Express/dominican-ios"


def qr_png():
    q = qrcode.QRCode(border=2, box_size=20)
    q.add_data("https://" + REPO)
    img = q.make_image(fill_color="#" + TEXT, back_color="#" + BG)
    path = HERE / "assets" / "gen" / "qr.png"
    img.save(path)
    return path


def app_icon():
    """Icono de la app con las esquinas redondeadas de iOS (radio 22,4 %)."""
    from PIL import Image, ImageDraw
    src = HERE.parent / "Project" / "Resources" / "Assets.xcassets" / "AppIcon.appiconset" / "AppIcon.png"
    im = Image.open(src).convert("RGBA")
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, *im.size), radius=int(im.size[0] * 0.224), fill=255)
    im.putalpha(mask)
    path = HERE / "assets" / "gen" / "app-icon.png"
    im.save(path)
    return path


def cover(s):
    """Portada: el grafo real de transferencias de `volume`, anillos en violeta."""
    picture(s, charts.graph("graph-right", 6.6, 6.6), x=int(I(6.6)), y=int(I(0.45)),
            max_w=I(6.6), max_h=I(6.6))
    picture(s, app_icon(), x=int(MARGIN), y=int(I(1.05)), max_w=I(1.1), max_h=I(1.1))
    text(s, MARGIN, I(2.55), I(6.0), I(0.9), "Dominican Express", size=42, bold=True)
    text(s, MARGIN, I(3.5), I(6.0), I(0.6), "A bank built inside SurrealDB", size=24,
         color=MUTED)
    text(s, MARGIN, I(4.65), I(6.0), I(1.2), "Jorge Pérez\nXabier Ariznabarreta\nJavier Pérez",
         size=20)
    text(s, MARGIN, I(6.05), I(6.0), I(0.4), "Advanced Databases, UFV", size=18, color=MUTED)
    text(s, I(7.0), I(6.75), I(5.8), I(0.4), "2,827 transfers, 22 accounts in rings",
         size=18, color=MUTED, font=MONO, align=PP_ALIGN.RIGHT)


def commands(slide, lines, y=TOP + I(0.2)):
    """Chuleta de la demo: una línea por paso, número atenuado y orden en mono."""
    for i, (cmd, what) in enumerate(lines):
        yy = y + I(0.78) * i
        text(slide, MARGIN, yy, I(0.5), I(0.5), f"{i + 1}", size=22, color=MUTED, font=MONO)
        text(slide, MARGIN + I(0.6), yy, I(7.4), I(0.5), cmd, size=22, font=MONO)
        text(slide, MARGIN + I(8.2), yy + I(0.04), I(4.0), I(0.5), what, size=20, color=MUTED)


def build():
    g = charts.all_charts()
    prs = Presentation()
    prs.slide_width, prs.slide_height = W, H

    # 1 ---------------------------------------------------------------- Jorge
    s = frame(prs, 1, None, notes="""
JORGE. Good morning. We are Jorge, Xabier and Javier, and this is Dominican Express:
a digital bank. The deliverable of this course is the database, and in our project the
database is not just storage: the whole backend, from payments to fraud detection,
lives inside it. On the right, real data from our test bank: 2,827 transfers between
300 customers over 60 days. The violet ones are the 22 accounts the database itself
found moving money in rings.""")
    cover(s)

    # 2 ---------------------------------------------------------------- Jorge
    s = frame(prs, 2, "The product", "iOS app in SwiftUI: mock data today", notes="""
JORGE. The product is a mobile bank: accounts, transfers, Bizum between customers,
cards, shared accounts. This is our iOS app, written in SwiftUI. To be clear: today
the app runs on mock data, it does not call the database yet. Everything you will see
in the demo is the database itself, which is the graded part. In a moment I'll show
how the app would talk to it.""")
    shots = HERE.parent / "docs" / "screenshots"
    picture(s, shots / "home.png", x=int(W / 2 - I(3.0)), max_w=I(2.8))
    picture(s, shots / "cards.png", x=int(W / 2 + I(0.2)), max_w=I(2.8))

    # 3 ---------------------------------------------------------------- Jorge
    s = frame(prs, 3, "What SurrealDB is", "NoSQL, multi-model. Looks like SQL, has no JOINs",
              notes="""
JORGE. SurrealDB is a NoSQL, multi-model database. One engine, one query language called
SurrealQL, and one transaction cover three ways of storing data. Documents: a customer
or an account is a JSON-like record. Graph: a relation, like "this customer owns this
account", is itself a record and can carry fields. And underneath, everything is stored
as keys in an ordered key-value store. It looks like SQL, but it is not relational:
records link to each other by ID, there are no JOINs.""")
    top = box(s, I(2.65), TOP + I(0.3), I(8.0), I(0.95),
              "One engine, one language, one transaction", accent=True, size=22)
    cols = [("Documents", "customer, account"), ("Graph", "owns, transfer"),
            ("Key-value", "storage layer")]
    for i, (name, sub) in enumerate(cols):
        x = I(1.45) + i * I(3.75)
        box(s, x, TOP + I(2.4), I(3.1), I(1.5), name, sub=sub, size=24)
        arrow(s, I(6.65), TOP + I(1.25), x + I(1.55), TOP + I(2.4))

    # 4 ---------------------------------------------------------------- Jorge
    s = frame(prs, 4, "Why a bank needs it", "Typical fits: fraud and risk, social data, access control",
              notes="""
JORGE. Why this database for a bank? A bank needs three things at once. Money that
never goes out of balance: that needs transactions over several records. Fraud is a
graph problem: rings of accounts, phones shared by strangers. And the data is sensitive,
so each customer must only see their own records, and some fields like the card number
only after a PIN. Of the engines we compared, SurrealDB is the one that gives all three
in one place.
Typical scenarios for it: fraud and risk analysis, social and recommendation data,
access-control models that are graphs.""")
    rows = [("Money never out of balance", "Multi-record ACID", False),
            ("Fraud is a graph", "Native graph", True),
            ("Sensitive data", "Per-record, per-field permissions", False)]
    for i, (need, cap, acc) in enumerate(rows):
        y = TOP + I(0.25) + i * I(1.65)
        box(s, I(1.2), y, I(4.6), I(1.15), need, size=22)
        arrow(s, I(5.8), y + I(0.575), I(7.4), y + I(0.575))
        box(s, I(7.4), y, I(4.7), I(1.15), cap, accent=acc, size=22)

    # 5 ---------------------------------------------------------------- Jorge
    s = frame(prs, 5, "How an app talks to it", "No backend in between", notes="""
JORGE. There is no backend between the app and the database. The app signs in and gets
a token that carries only that customer's permissions; it never holds database
credentials. Reads are plain queries, and the database filters them: you only get your
own accounts. Writes, like a payment, go through HTTP endpoints defined inside the
database, which check ownership and limits and answer with real HTTP codes. Our iOS app
reads through one protocol that today is implemented by mock data: connecting it means
writing one class, the screens do not change. Now Xabier will show you how the database
works inside.""")
    box(s, I(0.9), TOP + I(1.75), I(2.6), I(1.3), "iOS app, web", size=22)
    eps = [("/signin", "token: one customer"), ("/sql", "reads, filtered"),
           ("/api", "writes, checked")]
    for i, (ep, sub) in enumerate(eps):
        y = TOP + I(0.2) + i * I(1.6)
        box(s, I(4.75), y, I(3.6), I(1.15), ep, sub=sub, font=MONO, size=22)
        arrow(s, I(3.5), TOP + I(2.4), I(4.75), y + I(0.575))
        arrow(s, I(8.35), y + I(0.575), I(9.6), TOP + I(2.4))
    box(s, I(9.6), TOP + I(1.75), I(2.8), I(1.3), "SurrealDB", sub="permissions", accent=True,
        size=24)

    # 6 ---------------------------------------------------------------- Xabier
    s = frame(prs, 6, "One record, two models", "The role lives on the edge, not in a join table",
              notes="""
XABIER. Here is the data model in one query. Ana's account is a document. Who owns it is
a graph: the edge "owns" goes from customer to account, and it carries a field, the role.
Ana is the holder, Luis the co-holder. No join table. And the same traversal,
"my customer, owns, account", is both the permission rule (you see an account if it
hangs from one of your owns edges) and the input of the fraud detectors. We use a strict
schema where money is, and free-form fields where each detector writes different
details.""")
    box(s, MARGIN, TOP + I(0.2), W - 2 * MARGIN, I(1.0),
        "SELECT <-owns<-customer.name AS holders, <-owns.role AS roles FROM account:ana;",
        font=MONO, size=20, fill=CARD)
    for i, (name, role, acc) in enumerate([("Ana García", "titular", True),
                                          ("Luis Romero", "cotitular", False)]):
        y = TOP + I(2.0) + i * I(1.45)
        box(s, I(1.4), y, I(3.0), I(1.0), name, size=22)
        arrow(s, I(4.4), y + I(0.5), I(8.7), y + I(0.5))
        text(s, I(4.95), y + I(0.05), I(3.5), I(0.4), f"owns  role: {role}", size=18,
             font=MONO, color=LILAC if acc else MUTED, align=PP_ALIGN.CENTER)
    box(s, I(8.7), TOP + I(2.0), I(3.2), I(2.45), "account:ana", sub="document", accent=True,
        font=MONO, size=22)

    # 7 ---------------------------------------------------------------- Xabier
    s = frame(prs, 7, "Consistency under a race", "10 simultaneous full-balance transfers, 20 rounds",
              notes="""
XABIER. Consistency. Our first design was a pure ledger: the balance is the sum of the
entries. We fired ten transfers of the whole balance at the same time, twenty rounds.
The unsafe version ended in an overdraft in 11 to 16 of the 20 rounds. Why: SurrealDB
uses snapshot isolation, which only detects a conflict when two transactions write the
same record, and two transfers insert different ledger entries. The fix: every transfer
also updates the account's balance field. That write is the conflict point; one of the
two transactions is undone entirely. Result: zero overdrafts, every time. We only found
this by testing it.""")
    picture(s, g["race"])

    # 8 ---------------------------------------------------------------- Xabier
    s = frame(prs, 8, "Compute apart from storage", "3 copies, Raft majority 2 of 3: CP", notes="""
XABIER. Architecture. SurrealDB separates compute from storage. The same binary runs on
memory, on disk, or on TiKV, a distributed key-value store. With TiKV, SurrealDB nodes
are stateless: any node serves any request. TiKV splits the data in ranges called
regions, and keeps every region on three nodes, kept in agreement by the Raft protocol.
A write commits when two of three have it. Under a network partition the minority side
refuses writes: in CAP terms it is CP, consistency first. For a bank, the right side.
We built this cluster and I'll break it in a few minutes.""")
    nb_y, pd_y, kv_y = TOP + I(0.1), TOP + I(1.75), TOP + I(3.4)
    for x, label in [(I(3.4), "Node A"), (I(7.0), "Node B")]:
        box(s, x, nb_y, I(2.6), I(0.95), label, size=22)
        arrow(s, x + I(1.3), nb_y + I(0.95), I(6.0), pd_y)
    box(s, I(4.85), pd_y, I(2.3), I(0.95), "PD", size=22)
    for i in range(3):
        x = I(2.45) + i * I(3.0)
        box(s, x, kv_y, I(2.5), I(0.95), f"TiKV {i + 1}", accent=(i == 0), size=22)
        arrow(s, I(6.0), pd_y + I(0.95), x + I(1.25), kv_y)
    for y, label in [(nb_y, "stateless"), (pd_y, "placement"),
                     (kv_y, "3 copies each")]:
        text(s, I(11.2), y + I(0.25), I(1.9), I(0.5), label, size=18, color=MUTED)
    text(s, I(2.45), kv_y + I(1.05), I(2.5), I(0.4), "leader", size=18, color=LILAC,
         align=PP_ALIGN.CENTER)

    # 9 ---------------------------------------------------------------- Xabier
    s = frame(prs, 9, "Install, access, query", "HTTP, WebSocket, Surrealist, Python SDK", notes="""
XABIER. Installing it is one command; we pin version 3.2.4 because 3.3 changes features
we depend on. Our demo script starts the database on disk and loads three databases in
about a minute, and the six test suites run in fifteen seconds. You talk to it over HTTP
for queries and our API, over WebSocket for the SDKs and live queries, with Surrealist,
the official GUI, and from Python with the official SDK. Everything is in the public
repo, step by step, so another student can reproduce it.""")
    picture(s, g["install"])

    # 10 --------------------------------------------------------------- Xabier
    s = frame(prs, 10, "Live demo: the bank defends itself", "Surrealist, database live", notes="""
XABIER (demo, about 3 minutes; script in DEMO.md part B).
1. Surrealist, database live, Live mode: LIVE SELECT on fraud_alert. "The database is
   watching this table."
2. Terminal: SURREAL_DB=live ./db/demo/demo.sh attack. Six alerts appear on their own:
   mule ring on Ana, Luis and Marta, shared phone, impossible travel, structuring.
   "Pushed by the database, no refresh."
3. Saved query Frozen accounts: Ana, Luis, Marta frozen; Jose in review. "Proportional:
   the ring is frozen, structuring goes to review because it can be innocent. An event
   did this inside the transaction. No application code."
4. SURREAL_DB=live ./db/demo/demo.sh coverup: Marta tries to delete the phone, move the
   money, unlink herself. All blocked, and we never tell a suspect why.
5. Saved query Audit trail: one row, written by an event, by app_user:marta.
If short of time: skip step 4.""")
    commands(s, [("LIVE SELECT * FROM fraud_alert;", "alerts pushed live"),
                 ("demo.sh attack", "a ring forms"),
                 ("Frozen accounts", "frozen in proportion"),
                 ("demo.sh coverup", "nothing can be erased"),
                 ("Audit trail", "and who tried")])

    # 11 --------------------------------------------------------------- Xabier
    s = frame(prs, 11, "CRUD from Python", "Official SDK, surrealdb 3.0.0", notes="""
XABIER (demo, about 45 seconds): ./db/demo/demo.sh sdk
The same from the official Python SDK, the way a real app would do it, in its own
database. Create a customer, an account and the owns edge. Read it and traverse the
graph. Update: an invalid phone is rejected by the database, not by the app. Ana signs
in, sees only her account, pays through the API, and a retry of the same payment is
charged once. Staff deletes the test customer, and the audit trail shows it.""")
    commands(s, [("create", "customer + account + owns"),
                 ("read", "record and graph traversal"),
                 ("update", "invalid phone: rejected"),
                 ("Ana pays twice", "charged once"),
                 ("delete", "audited")])
    text(s, MARGIN, TOP + I(4.4), I(8), I(0.5), "$ ./db/demo/demo.sh sdk", size=22, font=MONO,
         color=LILAC)

    # 12 --------------------------------------------------------------- Xabier
    s = frame(prs, 12, "Tested on data we did not make", "Calibrated on one set, validated untouched on another",
              notes="""
XABIER. The ring in the demo we planted ourselves, so it can only confirm our own design.
So we ran the detector on IBM's public anti-money-laundering dataset, where the answer
is known. First result: 6 of 54 laundering cycles. We had assumed a mule keeps a
commission, so the amount shrinks; on IBM's data it grows half the time. We fixed the
method before looking, calibrated on one set, 33 of 54, and validated on another set we
had not touched: 8 of 12. At 87 percent precision, freezing would hit one innocent in
eight, so two tiers: strict rings freeze, wide ones go to an analyst. And a cheap
filter first: 4.5 million transfers down to 381, without losing a single ring.""")
    picture(s, g["ibm"])

    # 13 --------------------------------------------------------------- Xabier
    s = frame(prs, 13, "Live demo: kill a storage node", "1 PD, 3 TiKV, 2 SurrealDB nodes, one laptop",
              notes="""
XABIER (demo, about 2 minutes; CLUSTER.md). Cluster already up before class.
1. ./db/demo/demo.sh cluster-status: three TiKV up, every region on all three.
2. Terminal 1: ./db/demo/demo.sh cluster-write 40 (writes through node A).
3. Terminal 2, while it runs: ./db/demo/demo.sh cluster-kill (SIGKILL, a crash).
   If it led the written region: a few writes fail WITH AN ERROR for 9 to 12 seconds,
   Raft elects a new leader, then it continues. If not: "nobody notices a dead follower".
4. Node B counts exactly the writes that answered OK: none lost, none half applied.
5. cluster-revive: say it, run only if time allows. Never cluster-down in class.""")
    commands(s, [("demo.sh cluster-status", "3 TiKV, regions x3"),
                 ("demo.sh cluster-write 40", "payments through node A"),
                 ("demo.sh cluster-kill", "crash the busiest TiKV"),
                 ("node B counts", "exactly the OK ones"),
                 ("demo.sh cluster-revive", "it catches up")])

    # 14 --------------------------------------------------------------- Xabier
    s = frame(prs, 14, "What the cluster gives, what it costs",
              "The cluster proves failover. The live demo runs on one node", notes="""
XABIER. What we measured. Killing a follower: nothing visible. Killing the leader of the
region being written: 9 to 12 seconds of errors, and not one write lost or half applied.
The node comes back and catches up in about ten seconds. It costs about 1.1 GB of RAM
on this laptop. And two features do not cross nodes: time travel only exists on the
single-node engine, and live queries only see changes made on their own node; across
nodes it is an Enterprise feature. So the live demo runs on one node, and the cluster
proves the failover. Javier will now step back and judge the whole thing.""")
    grid(s, MARGIN + I(0.3), TOP + I(0.2), [I(5.8), I(5.8)], I(0.78), [
        ["Gives", "Costs"],
        ["Every write on 3 nodes", "About 1.1 GB of RAM"],
        ["Follower killed: 20 of 20 OK", "No time travel on TiKV"],
        ["Leader killed: 9 to 12 s of errors", "Live queries: 0 of 5 across nodes"],
        ["0 writes lost or half applied", "One laptop: mechanics, not speed"],
        ["5 of 6 test suites pass", ""],
    ], size=20, first_col_bold=False)

    # 15 --------------------------------------------------------------- Javier
    s = frame(prs, 15, "Don't trust the tool, test it", "74 of 74 deliberate breaks caught", notes="""
JAVIER. Now a critical look. Our main method: a test you have never seen fail is not
watching anything. So every protection was broken on purpose, and its test had to
catch it: 74 of 74 caught. Testing like this found real problems in SurrealDB: a
time-travel bug that brought deleted records back, which could produce false evidence
against an innocent; live notifications lost silently when two clients listen; and a
query planner that ignored our index, 72 milliseconds against 1.2. Every one became a
design decision. SurrealDB is powerful, but young.""")
    picture(s, g["redteam"])

    # 16 --------------------------------------------------------------- Javier
    s = frame(prs, 16, "Against the alternatives", "From the documentation. Speed not measured",
              notes="""
JAVIER. How it compares, from each vendor's documentation, not measured: we do not claim
it is faster than any of them. MongoDB also has multi-document transactions; what
separates them is the graph, limited to 100 MB, and permissions per field only through
views. Cassandra keeps transactions inside one partition. Neo4j is the strongest graph,
but property permissions are Enterprise only. ArangoDB was the serious alternative,
rejected for permissions. PostgreSQL is not NoSQL, which the course requires.
SurrealDB is the only one of these with queries into the past inside the language.""")
    grid(s, MARGIN, TOP + I(0.05), [I(2.35), I(2.4), I(2.4), I(2.5), I(2.45)], I(0.74), [
        ["", "Transactions", "Graph", "Field permissions", "Query the past"],
        ["MongoDB", "multi-document", "100 MB limit", "views only", "about 5 min"],
        ["Cassandra", "one partition", "no", "column masking", "no"],
        ["Neo4j", "yes", "native", "Enterprise only", "no"],
        ["ArangoDB", "single server", "native", "per collection", "no"],
        ["PostgreSQL", "yes, not NoSQL", "recursive CTE", "row-level", "no system time"],
        ["SurrealDB", "multi-record", "native", "per field", "VERSION, beta"],
    ], size=18, highlight_row=6)

    # 17 --------------------------------------------------------------- Javier
    s = frame(prs, 17, "Where SurrealDB fits", "Strengths we measured, limits we hit", notes="""
JAVIER. So, when would we use it? When documents, a graph and fine-grained permissions
meet, like fraud, risk or access control; for small and medium systems where a small
team benefits from having the API, authentication and real-time updates inside the
database; and for prototypes and teaching. Not yet for a system that needs a long,
proven operational record: we hit renames between versions, a bug and lost live events.
Not for real-time across nodes without the Enterprise licence. And legal evidence must
still be copied out to write-once storage.""")
    for i, (head, items, acc) in enumerate([
            ("Good fit", ["Documents + graph + permissions", "Small team, logic in the database",
                          "Prototypes and teaching"], True),
            ("Not yet", ["Long proven operational record", "Real-time across nodes, free",
                         "Legal evidence storage"], False)]):
        x = MARGIN + I(0.3) + i * I(6.1)
        box(s, x, TOP + I(0.2), I(5.6), I(0.85), head, accent=acc, size=24)
        for j, item in enumerate(items):
            box(s, x, TOP + I(1.35) + j * I(1.05), I(5.6), I(0.85), item, size=20)

    # 18 --------------------------------------------------------------- Javier
    s = frame(prs, 18, None, notes="""
JAVIER. To finish: every number you saw is in the public repository, with the steps to
reproduce it. The code was written with AI help; what we did was decide what to build,
measure it, and break it on purpose. Thank you. Questions?""")
    text(s, MARGIN, I(2.2), I(7), I(1.0), "Decisions, measured", size=48, bold=True)
    text(s, MARGIN, I(3.4), I(7), I(1.0), "Every number on these slides\nis in the repository.",
         size=24, color=MUTED)
    text(s, MARGIN, I(5.2), I(7), I(0.5), REPO, size=20, font=MONO, color=LILAC)
    picture(s, qr_png(), x=int(I(8.6)), y=int(I(1.8)), max_w=I(3.8), max_h=I(3.8))

    out = HERE / "dominican-express.pptx"
    prs.save(out)
    return out


if __name__ == "__main__":
    print(build())
