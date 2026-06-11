#!/usr/bin/env python3

import argparse
import json
import os
import socket
import subprocess
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent


class Doctor:
    def __init__(self, full=False):
        self.full = full
        self.results = []

    def add(self, status, component, message):
        self.results.append({
            "status": status,
            "component": component,
            "message": message,
        })

    def ok(self, component, message):
        self.add("OK", component, message)

    def warn(self, component, message):
        self.add("WARN", component, message)

    def fail(self, component, message):
        self.add("FAIL", component, message)

    def info(self, component, message):
        self.add("INFO", component, message)

    def check_port(self, host, port):
        try:
            with socket.create_connection((host, port), timeout=3):
                return True
        except Exception:
            return False

    def check_git(self):
        git_dir = ROOT / ".git"
        if git_dir.exists():
            self.ok("git", "Git repository detected")
        else:
            self.fail("git", ".git directory missing")
            return

        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.stdout.strip():
                self.warn("git", "Working tree has uncommitted changes")
            else:
                self.ok("git", "Working tree clean")

            log = subprocess.run(
                ["git", "log", "--oneline", "-1"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if log.stdout.strip():
                self.ok("git", f"Last commit: {log.stdout.strip()}")
        except Exception as exc:
            self.warn("git", f"Unable to inspect git status: {exc}")

    def check_fastapi(self):
        try:
            r = requests.get("http://localhost:8000/docs", timeout=3)
            if r.status_code == 200:
                self.ok("fastapi", "FastAPI responding on localhost:8000")
                return
        except Exception:
            pass

        if self.check_port("localhost", 8000):
            self.ok("fastapi", "Port 8000 reachable")
        else:
            self.fail("fastapi", "FastAPI not responding on localhost:8000")

    def check_postgres(self):
        try:
            import psycopg2
            conn = psycopg2.connect(
                host="localhost",
                port=5432,
                dbname=os.getenv("POSTGRES_DB", "postgres"),
                user=os.getenv("POSTGRES_USER", "postgres"),
                password=os.getenv("POSTGRES_PASSWORD", "postgres"),
            )
            cur = conn.cursor()

            cur.execute("SELECT extname FROM pg_extension WHERE extname='vector'")
            if cur.fetchone():
                self.ok("pgvector", "pgvector extension installed")
            else:
                self.fail("pgvector", "pgvector extension missing")

            cur.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name='documents'"
            )
            cols = [r[0] for r in cur.fetchall()]
            if cols:
                self.ok("postgres", "documents table present")
                self.info("postgres", f"columns: {', '.join(sorted(cols))}")

                cur.execute("SELECT COUNT(*) FROM documents")
                count = cur.fetchone()[0]
                self.ok("postgres", f"documents in knowledge base: {count}")
            else:
                self.fail("postgres", "documents table missing")

            conn.close()
        except Exception as exc:
            self.fail("postgres", str(exc))

    def check_minio(self):
        if self.check_port("localhost", 9000):
            self.ok("minio", "MinIO API reachable on localhost:9000")
        else:
            self.fail("minio", "MinIO API unavailable on localhost:9000")

        if self.check_port("localhost", 9001):
            self.ok("minio", "MinIO console reachable on localhost:9001")
        else:
            self.fail("minio", "MinIO console unavailable on localhost:9001")

    def check_watcher(self):
        watcher = ROOT / "minio_watcher.py"
        if watcher.exists():
            self.ok("watcher", "minio_watcher.py present")
        else:
            self.fail("watcher", "minio_watcher.py missing")

        try:
            result = subprocess.run(
                ["pgrep", "-f", "minio_watcher.py"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.stdout.strip():
                self.ok("watcher", f"Watcher process running (pid {result.stdout.strip()})")
            else:
                self.warn("watcher", "Watcher script present but not running")
        except Exception:
            self.info("watcher", "Unable to check watcher process status")

    def check_ollama(self):
        try:
            r = requests.get("http://localhost:11434/api/tags", timeout=5)
            data = r.json()
            models = data.get("models", [])
            self.ok("ollama", f"Ollama reachable ({len(models)} models installed)")

            names = {m.get("name", "") for m in models}
            expected = {"llama3.1:8b", "mistral:latest", "phi4-mini:latest", "phi3:mini"}
            for model in sorted(expected):
                if model in names:
                    self.ok("ollama", f"Model present: {model}")
                else:
                    self.warn("ollama", f"Model missing: {model}")
        except Exception as exc:
            self.fail("ollama", f"Ollama unreachable: {exc}")

    def check_gpu(self):
        try:
            import torch
            if torch.cuda.is_available():
                name = torch.cuda.get_device_name(0)
                self.ok("gpu", f"CUDA available — device: {name}")
                self.info("gpu", "CC 6.1 PyTorch compatibility warnings are non-fatal — do not reinstall PyTorch")
                return
            else:
                self.warn("gpu", "CUDA unavailable via torch — running on CPU")
                return
        except Exception as exc:
            self.warn("gpu", f"torch CUDA check failed: {exc}")

        try:
            subprocess.run(
                ["nvidia-smi"],
                capture_output=True,
                text=True,
                timeout=5,
                check=True,
            )
            self.ok("gpu", "GPU detected via nvidia-smi fallback")
        except Exception:
            self.fail("gpu", "No GPU detected")

    def check_embeddings(self):
        # Check package is installed without importing torch or triggering CUDA
        import importlib.util
        spec = importlib.util.find_spec("sentence_transformers")
        if spec is None:
            self.fail("embeddings", "sentence-transformers not installed")
            return

        self.ok("embeddings", "sentence-transformers package found")

        # Check for model files in common cache locations without loading anything
        cache_locations = [
            Path.home() / ".cache" / "torch" / "sentence_transformers",
            Path.home() / ".cache" / "huggingface" / "hub",
            ROOT / "venv" / "lib",
        ]
        found = any(p.exists() for p in cache_locations)
        if found:
            self.ok("embeddings", "Model cache directory found")
        else:
            self.warn("embeddings", "No cache directory found — model will download on first use")

        if not self.full:
            self.info("embeddings", "Deep load skipped (use --full to test model load and embedding dimension)")
            return

        # Force CPU — GTX 1070 CC 6.1 cannot execute CUDA kernels with current PyTorch build
        # Production stack (fuse.py) also falls back to CPU automatically
        # On a machine with a compatible GPU (CC >= 7.5) this warning will not appear
        try:
            import warnings
            os.environ["CUDA_VISIBLE_DEVICES"] = ""
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                from sentence_transformers import SentenceTransformer
                model = SentenceTransformer("all-MiniLM-L6-v2")
                vec = model.encode("test")
            if len(vec) == 384:
                self.ok("embeddings", f"Model loaded on CPU — embedding dimension: {len(vec)}")
                self.info("embeddings", "GTX 1070 CC 6.1 cannot execute CUDA kernels with current PyTorch build — CPU inference is correct production behavior. On a GPU with CC >= 7.5 this will run on GPU.")
            else:
                self.warn("embeddings", f"Unexpected embedding dimension: {len(vec)} (expected 384)")
        except Exception as exc:
            self.fail("embeddings", f"Full model load failed: {exc}")

    def check_observability(self):
        if self.check_port("localhost", 3000):
            self.ok("grafana", "Grafana reachable on localhost:3000")
        else:
            self.warn("grafana", "Grafana unavailable — monitoring stack may not be running")

        if self.check_port("localhost", 3100):
            self.ok("loki", "Loki reachable on localhost:3100")
        else:
            self.warn("loki", "Loki unavailable — monitoring stack may not be running")

    def analyze_failure_modes(self):
        statuses = {r["component"]: r["status"] for r in self.results}

        if statuses.get("fastapi") == "OK" and statuses.get("ollama") == "FAIL":
            self.warn("system", "FastAPI responding but Ollama unavailable — /ask endpoint will fail")

        if statuses.get("postgres") == "OK" and statuses.get("pgvector") == "FAIL":
            self.warn("system", "PostgreSQL healthy but pgvector missing — semantic search unavailable")

        if statuses.get("minio") == "OK" and statuses.get("watcher") == "WARN":
            self.warn("system", "MinIO healthy but watcher not running — new files will not be auto-ingested")

        if statuses.get("gpu") == "WARN":
            self.info("system", "Embeddings running on CPU — functional but slower than cuda:0")

    def run(self):
        self.check_git()
        self.check_fastapi()
        self.check_postgres()
        self.check_minio()
        self.check_watcher()
        self.check_ollama()
        self.check_gpu()
        self.check_embeddings()
        self.check_observability()
        self.analyze_failure_modes()

    def summary(self):
        fails = [r for r in self.results if r["status"] == "FAIL"]
        warns = [r for r in self.results if r["status"] == "WARN"]
        if not fails and not warns:
            return "HEALTHY", "Tier 1 Readiness: READY"
        elif not fails:
            return "DEGRADED", f"Tier 1 Readiness: READY WITH WARNINGS ({len(warns)} warnings)"
        else:
            return "UNHEALTHY", f"Tier 1 Readiness: NOT READY ({len(fails)} failures)"

    def print_text(self):
        print()
        print("=" * 60)
        print("  Prosjekt Øyenstikker — Doctor")
        print("  Read-only diagnostic. No files modified.")
        print("=" * 60)
        print()

        for r in self.results:
            label = f"[{r['status']}]".ljust(7)
            print(f"  {label} {r['component']}: {r['message']}")

        print()
        print("=" * 60)
        status, readiness = self.summary()
        print(f"  Overall Status: {status}")
        print(f"  {readiness}")
        print("=" * 60)
        print()

    def print_json(self):
        status, readiness = self.summary()
        output = {
            "status": status,
            "readiness": readiness,
            "checks": self.results,
        }
        print(json.dumps(output, indent=2))


    def set_model(self, force=False):
        """Change the default model in fuse.py from phi3:mini to llama3.1:8b.

        Safety rules:
          - Verify llama3.1:8b exists in Ollama
          - Create restore point before user confirmation
          - Show the exact line that will change
          - Require confirmation unless --force
        """

        target_model = "llama3.1:8b"

        try:
            r = requests.get(
                "http://localhost:11434/api/tags",
                timeout=5,
            )
            r.raise_for_status()
            models = {
                m.get("name", "")
                for m in r.json().get("models", [])
            }
        except Exception as exc:
            raise SystemExit(f"Unable to verify Ollama models: {exc}")

        if target_model not in models:
            raise SystemExit(f"Target model not installed: {target_model}")

        fuse_path = ROOT / "fuse.py"
        if not fuse_path.exists():
            raise SystemExit("fuse.py not found")

        original = fuse_path.read_text(encoding="utf-8")
        lines = original.splitlines()

        line_number = None
        old_line = None

        for idx, line in enumerate(lines, start=1):
            if "phi3:mini" in line:
                line_number = idx
                old_line = line
                break

        if line_number is None:
            raise SystemExit(
                "Expected model string 'phi3:mini' not found in fuse.py"
            )

        new_line = old_line.replace("phi3:mini", target_model, 1)

        restore_tag = self.protect()

        print()
        print(f"Restore point: {restore_tag}")
        print()
        print(f"File: {fuse_path}")
        print(f"Line: {line_number}")
        print()
        print(f"- {old_line}")
        print(f"+ {new_line}")
        print()

        if not force:
            answer = input("Proceed? [y/N] ").strip().lower()
            if answer not in ("y", "yes"):
                print(f"Cancelled. Restore point preserved: {restore_tag}")
                return

        updated = original.replace("phi3:mini", target_model, 1)
        fuse_path.write_text(updated, encoding="utf-8")

        print(f"[OK] Default model changed to {target_model}")
        print(f"[OK] Restore point: {restore_tag}")

    def protect(self):
        from datetime import datetime

        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )

        has_changes = bool(status.stdout.strip())
        timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")

        if has_changes:
            subprocess.run(["git", "add", "-A"], cwd=ROOT, check=True)
            subprocess.run(
                ["git", "commit", "-m", f"restore point: {timestamp}"],
                cwd=ROOT,
                check=True,
            )

        tag = f"backup-{timestamp}"
        subprocess.run(["git", "tag", tag], cwd=ROOT, check=True)
        print(f"[PROTECT] Restore point created: {tag}")
        return tag

    def backup(self):
        from datetime import datetime

        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )

        has_changes = bool(status.stdout.strip())

        if has_changes:
            timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
            subprocess.run(["git", "add", "-A"], cwd=ROOT, check=True)
            subprocess.run(
                ["git", "commit", "-m", f"restore point: {timestamp}"],
                cwd=ROOT,
                check=True,
            )

        tag = f"backup-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
        subprocess.run(["git", "tag", tag], cwd=ROOT, check=True)
        print(f"[OK] Created restore tag: {tag}")

    def restore(self, tag_name=None, force=False, list_only=False):
        if list_only:
            result = subprocess.run(
                ["git", "tag", "--list", "backup-*"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=True,
            )
            tags = result.stdout.strip()
            if tags:
                print(tags)
            else:
                print("[INFO] No restore tags found")
            return

        if not tag_name:
            raise SystemExit("restore requires a tag name or --list")

        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )

        dirty = bool(status.stdout.strip())
        if dirty and not force:
            raise SystemExit(
                "Working tree is dirty. Commit/stash changes or use --force."
            )

        verify = subprocess.run(
            ["git", "rev-parse", "--verify", tag_name],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        if verify.returncode != 0:
            raise SystemExit(f"Restore tag not found: {tag_name}")

        subprocess.run(
            ["git", "switch", "--detach", tag_name],
            cwd=ROOT,
            check=True,
        )
        print(f"[OK] Restored to {tag_name}")
        print("[INFO] Repository is now at the tagged snapshot.")
        print("[INFO] To return to main: git switch main")


def main():
    parser = argparse.ArgumentParser(prog="manage.py")
    sub = parser.add_subparsers(dest="command")

    doctor_parser = sub.add_parser("doctor", help="Read-only system diagnostic")
    doctor_parser.add_argument("--full", action="store_true", help="Include full embedding model load test")
    doctor_parser.add_argument("--json", action="store_true", help="Output as JSON")

    sub.add_parser("backup", help="Create a tagged restore point")

    restore_parser = sub.add_parser("restore", help="Restore to a tagged restore point")
    restore_parser.add_argument("tag", nargs="?", help="Tag name to restore to")
    restore_parser.add_argument("--list", action="store_true", help="List available restore tags")
    restore_parser.add_argument("--force", action="store_true", help="Restore even if working tree is dirty")

    set_model_parser = sub.add_parser("set-model", help="Change default model in fuse.py to llama3.1:8b")
    set_model_parser.add_argument("--force", action="store_true", help="Skip confirmation prompt")

    args = parser.parse_args()

    if args.command == "doctor":
        d = Doctor(full=args.full)
        d.run()
        if args.json:
            d.print_json()
        else:
            d.print_text()

    elif args.command == "backup":
        Doctor().backup()

    elif args.command == "restore":
        Doctor().restore(
            tag_name=args.tag,
            force=args.force,
            list_only=args.list,
        )

    elif args.command == "set-model":
        Doctor().set_model(force=args.force)

    elif args.command is None:
        parser.print_help()


if __name__ == "__main__":
    main()