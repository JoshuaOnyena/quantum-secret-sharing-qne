import random
from netqasm.sdk import EPRSocket
from netqasm.sdk.external import NetQASMConnection, Socket
from netqasm.logging.output import get_new_app_logger


def measure_basis(q, basis):
    if basis == "X":
        q.H()
    else:
        q.rot_Z(n=3, d=1)
        q.H()
    return q.measure()


def main(app_config=None, num_rounds=20, seed=3, mode=0):
    logger = get_new_app_logger(app_name=app_config.app_name,
                                log_config=app_config.log_config)
    num_rounds = int(num_rounds)
    mode = int(mode)
    rng = random.Random(int(seed))

    epr_alice = EPRSocket("alice")
    corr_alice = Socket("charlie", "alice", log_config=app_config.log_config, socket_id=0)
    cls_alice = Socket("charlie", "alice", log_config=app_config.log_config, socket_id=1)

    conn = NetQASMConnection(app_name=app_config.app_name,
                             log_config=app_config.log_config,
                             epr_sockets=[epr_alice], max_qubits=1)

    my_bases, my_bits = [], []
    with conn:
        for _ in range(num_rounds):
            q = epr_alice.recv_keep()[0]
            conn.flush()
            if corr_alice.recv() == "1":
                q.X()
            basis = rng.choice(["X", "Y"])
            out = measure_basis(q, basis)
            conn.flush()
            my_bases.append(basis)
            my_bits.append(int(out))

    _ = cls_alice.recv()  # alice bases
    cls_alice.send(",".join(my_bases))
    # in solo mode (2) Charlie withholds his bits — single party can't reconstruct
    if mode != 2:
        cls_alice.send(",".join(str(b) for b in my_bits))
    logger.log(f"CHARLIE: measured {num_rounds} rounds (mode={mode})")
    return {"party": "charlie", "rounds": num_rounds, "mode": mode}
