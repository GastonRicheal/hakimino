"""Exercise real CLI processes through a POSIX pseudo-terminal using fake data.

Run with the project's virtualenv Python. No third-party test driver is required.
Never pass real secrets: this disposable acceptance fixture is intentionally public.
"""
import errno
import hashlib
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import tempfile
import time

MASTER = "synthetic acceptance master only"
PASSWORD = "synthetic entry password only"
ROOT = Path(__file__).resolve().parents[1]


def run_cli(path, args, answers, expected_exit=0):
    import pty
    master_fd, slave_fd = pty.openpty()
    process = None
    output = bytearray()
    cursor = 0
    deadline = time.monotonic() + 20
    try:
        process = subprocess.Popen(
            [sys.executable, "-m", "hakimino", "--vault", str(path), *args],
            cwd=ROOT, stdin=slave_fd, stdout=slave_fd, stderr=slave_fd,
            start_new_session=True,
        )
        os.close(slave_fd)
        slave_fd = None

        def read_chunk():
            if time.monotonic() >= deadline:
                raise AssertionError("CLI timed out")
            if not select.select([master_fd], [], [], 0.1)[0]:
                return True
            try:
                data = os.read(master_fd, 65536)
            except OSError as exc:
                if exc.errno == errno.EIO:
                    return False
                raise
            output.extend(data)
            return bool(data)

        for prompt, answer in answers:
            token = prompt.encode()
            while token not in output[cursor:]:
                if not read_chunk():
                    raise AssertionError(f"CLI ended before expected prompt: {prompt}")
            cursor = output.index(token, cursor) + len(token)
            os.write(master_fd, answer.encode() + b"\n")
        while read_chunk():
            pass
        code = process.wait(timeout=2)
        if code != expected_exit:
            raise AssertionError(f"Unexpected exit status {code}, expected {expected_exit}")
        return output.decode(errors="replace")
    finally:
        if process is not None and process.poll() is None:
            process.kill()
            process.wait()
        os.close(master_fd)
        if slave_fd is not None:
            os.close(slave_fd)


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    if os.name != "posix":
        raise SystemExit("This pseudo-terminal acceptance driver requires POSIX; use the manual checklist on Windows.")
    results = []
    auth = [("Master password: ", MASTER)]
    with tempfile.TemporaryDirectory(prefix="hakimino-acceptance-") as directory:
        path = Path(directory) / "synthetic.vault"
        out = run_cli(path, ["init"], auth + [("Confirm master password: ", MASTER)])
        check(path.exists() and "Done." in out and MASTER not in out, "Creation or master masking failed")
        results.append("Create vault with confirmation and non-echoing master prompt")

        out = run_cli(path, ["add", "school"], auth + [
            ("Entry username: ", "synthetic-user"), ("Entry password: ", PASSWORD)])
        check("Done." in out and MASTER not in out and PASSWORD not in out, "Add or prompt masking failed")
        results.append("Add entry through real non-echoing prompts")

        out = run_cli(path, ["list"], auth)
        check('["school"]' in out and PASSWORD not in out, "List after process restart failed")
        results.append("Persist entries across separate CLI process launches")

        out = run_cli(path, ["show", "school"], auth)
        check("synthetic-user" in out and "[hidden; use --reveal]" in out and PASSWORD not in out, "Default masking failed")
        results.append("Hide stored password by default")

        out = run_cli(path, ["show", "school", "--reveal"], auth)
        check(PASSWORD in out and MASTER not in out, "Explicit reveal failed")
        results.append("Reveal only on explicit request")

        original = path.read_bytes()
        out = run_cli(path, ["show", "school"], [("Master password: ", "incorrect synthetic master")], 1)
        check("Wrong master password or damaged vault" in out and path.read_bytes() == original, "Wrong-password rejection failed")
        results.append("Reject incorrect master password without changing the vault")

        out = run_cli(path, ["init"], auth + [("Confirm master password: ", MASTER)], 1)
        check("already exists" in out and path.read_bytes() == original, "Overwrite refusal failed")
        results.append("Refuse initialization over an existing vault")

        out = run_cli(path, ["delete", "school"], auth + [("Delete this entry? Type DELETE: ", "CANCEL")])
        check("Cancelled." in out and path.read_bytes() == original, "Delete cancellation failed")
        results.append("Cancel deletion without changing stored data")

        run_cli(path, ["add", "generated", "--generate"], auth + [("Entry username: ", "synthetic-generated-user")])
        out = run_cli(path, ["show", "generated", "--reveal"], auth)
        record = next(json.loads(line) for line in out.splitlines() if line.startswith("{"))
        check(len(record["password"]) == 24, "Generated password length mismatch")
        results.append("Generate and persist a 24-character password")

        run_cli(path, ["delete", "school"], auth + [("Delete this entry? Type DELETE: ", "DELETE")])
        out = run_cli(path, ["list"], auth)
        check('["generated"]' in out, "Confirmed deletion failed")
        results.append("Confirm deletion and verify it from a new process")

        import base64
        damaged = Path(directory) / "damaged.vault"
        data = json.loads(path.read_bytes())
        cipher = bytearray(base64.b64decode(data["ciphertext"]))
        cipher[0] ^= 1
        data["ciphertext"] = base64.b64encode(cipher).decode()
        damaged.write_text(json.dumps(data))
        before = hashlib.sha256(damaged.read_bytes()).digest()
        out = run_cli(damaged, ["list"], auth, 1)
        check("Wrong master password or damaged vault" in out and
              hashlib.sha256(damaged.read_bytes()).digest() == before, "Tampering rejection failed")
        results.append("Reject a tampered disposable copy without rewriting it")

        raw = path.read_bytes()
        check(all(value.encode() not in raw for value in
                  (MASTER, "synthetic-generated-user", record["password"])), "Plaintext found in vault")
        check(not list(Path(directory).glob("*.lock")) and not list(Path(directory).glob("*.tmp")), "Temporary files leaked")
        results.append("Check ciphertext storage and normal lock/temp cleanup")
    print(json.dumps({"status": "passed", "checks": results,
                      "count": len(results), "temporary_vaults_removed": True}, indent=2))


if __name__ == "__main__":
    main()
