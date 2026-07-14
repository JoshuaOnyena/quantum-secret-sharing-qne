# GHZ-Based Quantum Secret Sharing on the Quantum Network Explorer

*A Quantum Network Explorer (QNE) application implementing three-party quantum secret sharing on a genuine GHZ state. A dealer splits a secret so that two participants must combine their measurements to reconstruct it, while neither alone learns anything. Verify scenario confirmed on the QNE remote backend; all three scenarios verified on the local simulator. Published to the QNE Community Application Library (application 62).*

A dealer (Alice) wants to share a secret between two participants (Bob and Charlie) such that **both** must cooperate to recover it and **neither** can learn it alone. This is the quantum analogue of threshold cryptography, and the property that makes it a *security* primitive: the secret is protected against any single party. This application demonstrates the Hillery–Bužek–Berthiaume (HBB) scheme on a real three-party GHZ state, with three selectable scenarios that show the correlation is genuine, that reconstruction works, and that a lone party learns nothing.

## 1. The idea

The scheme rests on a genuine three-party GHZ state,

```
|GHZ> = (|000> + |111>) / sqrt(2)
```

shared one qubit each by Alice, Bob, and Charlie. Each party measures its qubit in a randomly chosen X or Y basis. After measurement, the bases are announced publicly (the outcomes are not). On the rounds where the basis combination is *compatible* — an even number of Y measurements: XXX, XYY, YXY, YYX — the three outcomes obey a deterministic relation:

```
a  XOR  b  XOR  c  =  parity(combination)
```

so Alice's bit `a` equals `b XOR c XOR parity`. Bob and Charlie must therefore **combine** their bits to recover Alice's share; either bit alone is uniformly random and carries no information about `a`. That asymmetry — jointly recoverable, individually useless — is the whole point.

## 2. The part that makes it real: a genuine GHZ state

The security property only holds if the three parties share a true GHZ state. A common implementation mistake is to distribute two independent Bell pairs (Alice–Bob and Alice–Charlie) and call it a GHZ state — but two Bell pairs are **not** GHZ, and Bob and Charlie end up uncorrelated with each other, so no shared secret exists.

This application builds a real GHZ state by **fan-out**: Alice prepares a data qubit in |+>, then entangles it into an EPR pair with each participant using a CNOT, measures the mediating qubit, and sends a classical correction. The result is one genuine three-party GHZ state per round, never exceeding two qubits held at any node.

```
Alice: data = |+>
       CNOT(data, EPR_half_to_Bob),     measure mediator -> correction to Bob
       CNOT(data, EPR_half_to_Charlie), measure mediator -> correction to Charlie
   ->  data, Bob's qubit, Charlie's qubit now form (|000> + |111>)/sqrt(2)
```

The correctness of this construction is confirmed directly by the verify scenario below: on every compatible round, the deterministic XOR relation holds exactly.

## 3. Roles and qubit budget

| Role | EPR partners | Peak local qubits |
|------|--------------|-------------------|
| `alice` (dealer) | bob, charlie | 2 (data qubit + one transient EPR half) |
| `bob` | alice | 1 |
| `charlie` | alice | 1 |

Well within the QNE 3-qubit-per-node ceiling. On the `europe` network the roles map cleanly onto paris (alice), inssbruck (bob), and barcelona (charlie).

## 4. Scenarios (selectable by the `mode` input)

The application exposes two inputs — `num_rounds` and `mode` — so all three scenarios run from one published app without code changes:

| `mode` | Scenario | Demonstrates |
|:------:|----------|--------------|
| 0 | **verify** | the GHZ correlation is genuine (a == b XOR c XOR parity on every compatible round) |
| 1 | **reconstruct** | Bob and Charlie together recover the dealer's secret bits |
| 2 | **solo** | Bob alone is uncorrelated with the secret (match rate ~ 0.5) — the threshold-security property |

## 5. Results

All figures are actual simulator output.

### 5.1 Verify — local and remote

On the compatible-basis rounds, the deterministic relation held on **every** round, both locally and on the QNE remote backend.

| Run | compatible rounds | correlated | `correlation_ok` |
|-----|:-----------------:|:----------:|:----------------:|
| Local | 12 | 12 | **true** |
| Remote (result 11982) | 12 | 12 | **true** |

The remote run executed on paris / inssbruck / barcelona and reproduced the local result exactly — genuine three-way GHZ correlation on the live backend.

### 5.2 Reconstruct — Bob + Charlie recover the secret

| compatible rounds | secret bits recovered | `reconstruction_ok` |
|:-----------------:|:---------------------:|:-------------------:|
| 12 | 12 / 12 | **true** |

Bob and Charlie, combining their measurements, recovered every bit of Alice's secret.

### 5.3 Solo — a single party learns nothing

The security property: one participant's data alone should be uncorrelated with the secret — a match rate at chance (0.5). The verdict is **sample-aware**, because at small sample sizes a match rate cannot be distinguished from chance.

| rounds | compatible rounds | Bob-alone match rate | verdict |
|:------:|:-----------------:|:--------------------:|---------|
| 20 | 12 | (small sample) | **insufficient_sample** |
| 200 | 100 | **0.53** | **protected** (within the chance band) |

At 100 compatible rounds the match rate settled at 0.53, comfortably inside the chance band (0.5 ± 3·standard error) — Bob alone learns essentially nothing. At 20 rounds the app correctly reports `insufficient_sample` rather than a spurious verdict, because 12 rounds cannot statistically distinguish protection from noise.

### 5.4 The three scenarios together

| Scenario | Result | What it establishes |
|----------|--------|---------------------|
| verify | 12/12 correlated | the GHZ state is genuine and three-way correlated |
| reconstruct | 12/12 recovered | Bob + Charlie together recover the secret |
| solo | 0.53 at n=100, protected | one party alone learns nothing (threshold security) |

Genuine entanglement (verify), correct functionality (reconstruct), and the actual security guarantee (solo) — each shown from real runs.

## 6. Implications for quantum security

Classical secret-sharing schemes protect the shares with computational assumptions or trusted infrastructure. This scheme's protection is **information-theoretic**: a lone participant's bit is uniformly random with respect to the secret as a matter of the physics of the GHZ state, not as a matter of a hard computational problem. An adversary with unbounded computing power — including a quantum computer — gains nothing against a single share.

The framing that makes this industry-legible: this is the primitive underneath **privacy-preserving multiparty aggregation** (several parties compute a joint result without exposing individual inputs) and **distributed key custody** (no single party holds a complete master key; a threshold must cooperate to reconstruct it). The demonstrated guarantee is narrow and exact rather than universal — it protects a single share, consumes entanglement per round, and assumes honest execution — which is precisely the kind of scoped, verifiable property worth building on.

## 7. Scope and limitations

- **Information-theoretic demonstration on a discrete-event simulator.** The correlations and the threshold property are exact in simulation. This is a protocol demonstrator, not a hardened deployment.
- **Solo verdict requires sufficient rounds.** Because it is a statistical property (match rate at chance), the solo scenario needs roughly 30+ compatible rounds to render a verdict; below that it honestly reports `insufficient_sample`. The verify and reconstruct properties are deterministic and hold at any round count.
- **Remote coverage.** The verify scenario is confirmed on the QNE remote backend (result 11982). Reconstruct and solo are verified on the local simulator; the solo scenario in particular requires ~100+ rounds for a decisive verdict, which exceeds the remote backend's 60-second execution budget, so it is verified locally.

## 8. Reproduce it

Environment: Python 3.10 venv (not 3.12 — NetSquid's pinned numpy will not build on 3.12), `qne-adk`, and `squidasm` via NetSquid forum credentials in a `~/.netrc`.

```bash
qne application create quantum_secret_sharing alice bob charlie
# copy src/ and config/ from this repo into the created directory
cd quantum_secret_sharing
qne application validate

# verify (mode 0, default)
qne experiment create exp_verify quantum_secret_sharing europe
qne experiment run exp_verify
qne experiment results exp_verify

# reconstruct (mode 1) and solo (mode 2): set the general 'mode' input
# in the experiment.json before running; use more rounds for solo (>= 100).
```

The Y-basis measurement uses `rot_Z(n=3, d=1)` (a 3*pi/2 rotation, equal to S-dagger up to global phase) — netqasm 2.0 rejects negative rotation multiples, so `n=3` rather than `n=-1`. If the compatible-round correlation does not come out deterministic, that rotation is the first thing to check.

## References

[1] M. Hillery, V. Bužek, A. Berthiaume, "Quantum Secret Sharing," *Physical Review A*, 1999.

---

*Published to the QNE Community Application Library as application 62. Verify scenario confirmed on the QNE remote backend (result 11982); all three scenarios verified on the local SquidASM simulator. Part of a portfolio of QNE quantum-networking and security applications by DrJoshy96.*
