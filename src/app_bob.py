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


def main(app_config=None, num_rounds=20, seed=2):
    logger = get_new_app_logger(app_name=app_config.app_name,
                                log_config=app_config.log_config)
    num_rounds = int(num_rounds)
    rng = random.Random(int(seed))

    epr_alice = EPRSocket("alice")
    corr_alice = Socket("bob", "alice", log_config=app_config.log_config, socket_id=0)
    cls_alice = Socket("bob", "alice", log_config=app_config.log_config, socket_id=1)

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
    cls_alice.send(",".join(str(b) for b in my_bits))
    logger.log(f"BOB: measured {num_rounds} rounds")
    return {"party": "bob", "rounds": num_rounds}
