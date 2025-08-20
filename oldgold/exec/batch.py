import json, subprocess, sys, time


def run(tokens):
    outs = []
    for t in tokens:
        print("==>", t)
        cp = subprocess.run([
            "oldgold",
            "run-one",
            "--chain",
            "bsc",
            "--token",
            t,
            "--base",
            "WBNB",
            "--grid",
            "1e3,5e3,1e4",
            "--slip-bps",
            "20",
        ], capture_output=True, text=True)
        print(cp.stdout)
        for line in cp.stdout.splitlines():
            if line.startswith('{"oldgold_summary"'):
                outs.append(json.loads(line)["oldgold_summary"])
                break
        time.sleep(1.0)
    json.dump(outs, open("out/batch_summary.json", "w"), indent=2)


if __name__ == "__main__":
    run(sys.argv[1:])
