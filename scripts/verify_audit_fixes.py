"""Repeat the original audit in a fresh migrated institution, preserving old evidence."""

import contextlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

import httpx


def main():
    root = Path(__file__).resolve().parents[1]
    run_id = uuid4().hex
    output = root / "backups" / f"acceptance-{run_id}"
    logs = root / "backups" / f"audit-verification-{run_id}.log"
    environment = {**os.environ, "NEXO_ACCEPTANCE_ID": run_id, "NEXO_ACCEPTANCE_PORT": "8013"}
    url = "http://127.0.0.3:8013"
    with httpx.Client(trust_env=False) as client:
        try:
            client.get(url + "/health", timeout=1)
        except httpx.TransportError:
            pass
        else:
            raise SystemExit("Isolated audit port is already in use; refusing to reuse a server")
    with logs.open("w", encoding="utf-8") as log:
        server = subprocess.Popen(
            [sys.executable, "-B", "-m", "scripts.acceptance_server"],
            cwd=root,
            env=environment,
            stdout=log,
            stderr=log,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        try:
            with httpx.Client(trust_env=False) as client:
                deadline = time.monotonic() + 180
                while time.monotonic() < deadline:
                    if server.poll() is not None:
                        raise RuntimeError(f"Isolated server failed; inspect {logs}")
                    try:
                        if client.get(url + "/health", timeout=1).status_code == 200:
                            break
                    except httpx.TransportError:
                        pass
                    time.sleep(0.5)
                else:
                    raise RuntimeError("Isolated server did not become ready")
            from scripts import audit_institutional as audit
            from scripts import audit_institutional_completion as completion
            from scripts import audit_institutional_followup as followup

            audit.OUT, audit.DB, audit.URL = output, output / "acceptance.db", url
            summaries = []
            with contextlib.redirect_stdout(log):
                for name, run in [
                    ("api-evidence.json", None),
                    ("api-followup.json", followup.main),
                    ("api-completion.json", completion.main),
                ]:
                    audit.CHECKS.clear()
                    audit.CLIENTS.clear()
                    audit.EVIDENCE_FILE = name
                    try:
                        if run:
                            run()
                        else:
                            for label, function in [
                                ("baseline", audit.smoke_and_scope),
                                ("institutional cycle", audit.institutional_cycle),
                                ("finance and communications", audit.finance_and_communications),
                                ("edge cases", audit.edge_cases),
                                ("integrity", audit.integrity_and_restore),
                            ]:
                                audit.scenario(label, function)
                        audit.save()
                        summaries.append(
                            {
                                "file": name,
                                "passed": sum(c["pass"] for c in audit.CHECKS),
                                "failed": sum(not c["pass"] for c in audit.CHECKS),
                            }
                        )
                    finally:
                        for client in audit.CLIENTS.values():
                            client.close()
            summary = {"evidence": str(output), "runs": summaries}
            (output / "verification-summary.json").write_text(
                json.dumps(summary, indent=2), encoding="utf-8"
            )
            print(json.dumps(summary, indent=2))
            if any(s["failed"] for s in summaries):
                raise SystemExit(1)
        finally:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=10)


if __name__ == "__main__":
    main()
