import math
import random
from netqasm.sdk import EPRSocket, Qubit
from netqasm.sdk.external import NetQASMConnection, Socket
from netqasm.logging.output import get_new_app_logger

# GHZ compatible-basis combos (even number of Y): expected parity of a^b^c
VALID = {"XXX": 0, "XYY": 1, "YXY": 1, "YYX": 1}
MODES = {0: "verify", 1: "reconstruct", 2: "solo"}
MIN_SAMPLE = 30  # below this, a match rate can't be distinguished from chance


def measure_basis(q, basis):
    if basis == "X":
        q.H()
    else:  # Y basis: S-dagger (3*pi/2 == -pi/2 mod 2pi) then H, then measure Z
        q.rot_Z(n=3, d=1)
        q.H()
    return q.measure()


def main(app_config=None, num_rounds=20, seed=1, mode=0):
    logger = get_new_app_logger(app_name=app_config.app_name,
                                log_config=app_config.log_config)
    num_rounds = int(num_rounds)
    mode = int(mode)
    mode_name = MODES.get(mode, "verify")
    rng = random.Random(int(seed))

    epr_bob = EPRSocket("bob")
    epr_charlie = EPRSocket("charlie")
    corr_bob = Socket("alice", "bob", log_config=app_config.log_config, socket_id=0)
    corr_charlie = Socket("alice", "charlie", log_config=app_config.log_config, socket_id=0)
    cls_bob = Socket("alice", "bob", log_config=app_config.log_config, socket_id=1)
    cls_charlie = Socket("alice", "charlie", log_config=app_config.log_config, socket_id=1)

    conn = NetQASMConnection(app_name=app_config.app_name,
                             log_config=app_config.log_config,
                             epr_sockets=[epr_bob, epr_charlie],
                             max_qubits=2)

    my_bases, my_bits = [], []
    with conn:
        for _ in range(num_rounds):
            data = Qubit(conn)
            data.H()
            mb = epr_bob.create_keep()[0]
            data.cnot(mb)
            cb = mb.measure()
            conn.flush()
            corr_bob.send(str(int(cb)))
            mc = epr_charlie.create_keep()[0]
            data.cnot(mc)
            cc = mc.measure()
            conn.flush()
            corr_charlie.send(str(int(cc)))
            basis = rng.choice(["X", "Y"])
            out = measure_basis(data, basis)
            conn.flush()
            my_bases.append(basis)
            my_bits.append(int(out))

    cls_bob.send(",".join(my_bases))
    cls_charlie.send(",".join(my_bases))
    bob_bases = cls_bob.recv().split(",")
    charlie_bases = cls_charlie.recv().split(",")
    bob_bits = [int(x) for x in cls_bob.recv().split(",")]
    if mode == 2:
        charlie_bits = None            # solo: Alice never gets Charlie's bits
    else:
        charlie_bits = [int(x) for x in cls_charlie.recv().split(",")]

    compatible = [i for i in range(num_rounds)
                  if (my_bases[i] + bob_bases[i] + charlie_bases[i]) in VALID]

    result = {"party": "alice", "mode": mode_name,
              "num_rounds": num_rounds, "compatible_rounds": len(compatible)}

    if mode == 0:  # verify
        correct = 0
        for i in compatible:
            combo = my_bases[i] + bob_bases[i] + charlie_bases[i]
            if my_bits[i] == (bob_bits[i] ^ charlie_bits[i] ^ VALID[combo]):
                correct += 1
        result["correct"] = correct
        result["correlation_ok"] = (len(compatible) > 0 and correct == len(compatible))
        logger.log(f"VERIFY: {correct}/{len(compatible)} compatible rounds correlated")

    elif mode == 1:  # reconstruct
        secret = [my_bits[i] for i in compatible]
        recovered = []
        for i in compatible:
            combo = my_bases[i] + bob_bases[i] + charlie_bases[i]
            recovered.append(bob_bits[i] ^ charlie_bits[i] ^ VALID[combo])
        result["secret_len"] = len(secret)
        result["reconstruction_ok"] = (secret == recovered)
        matched = sum(1 for s, r in zip(secret, recovered) if s == r)
        logger.log(f"RECONSTRUCT: Bob+Charlie recovered {matched}/{len(secret)} secret bits")

    else:  # mode == 2, solo
        secret = [my_bits[i] for i in compatible]
        bob_guess = [bob_bits[i] for i in compatible]
        n = len(secret)
        matches = sum(1 for s, g in zip(secret, bob_guess) if s == g)
        rate = matches / n if n else 0.0
        result["secret_len"] = n
        result["bob_alone_match_rate"] = round(rate, 3)

        # sample-aware verdict: standard error of a rate is ~0.5/sqrt(n).
        # "consistent with chance" = within 3 standard errors of 0.5.
        if n < MIN_SAMPLE:
            result["verdict"] = "insufficient_sample"
            result["note"] = (f"Only {n} compatible rounds; a match rate cannot be "
                              f"distinguished from chance below {MIN_SAMPLE}. "
                              f"Increase num_rounds to judge protection.")
            logger.log(f"SOLO: rate {rate:.2f} on {n} rounds -- INSUFFICIENT SAMPLE "
                       f"(need >= {MIN_SAMPLE} compatible rounds)")
        else:
            se = 0.5 / math.sqrt(n)
            consistent_with_chance = abs(rate - 0.5) <= 3 * se
            result["chance_band"] = [round(0.5 - 3 * se, 3), round(0.5 + 3 * se, 3)]
            result["secret_protected"] = bool(consistent_with_chance)
            result["verdict"] = "protected" if consistent_with_chance else "possible_leak"
            logger.log(f"SOLO: rate {rate:.3f} on {n} rounds, chance band "
                       f"{result['chance_band']} -> "
                       f"{'PROTECTED' if consistent_with_chance else 'POSSIBLE LEAK'}")

    return result
