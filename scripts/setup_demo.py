"""Crea (o reconstruye) la base SQLite con datos DEMO y los archivos de ejemplo del ETL.

Uso (desde la raíz del proyecto):
    python scripts/setup_demo.py            # crea la base solo si está vacía
    python scripts/setup_demo.py --reset    # reconstruye la base desde cero (borra datos actuales)
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import SAMPLE_DIR, database_url  # noqa: E402
from src.data.demo_generator import load_demo  # noqa: E402
from src.data.sample_files import write_samples  # noqa: E402
from src.database.connection import get_engine, init_db, is_populated  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reset", action="store_true", help="Reconstruye la base (borra los datos actuales).")
    args = parser.parse_args()
    engine = get_engine()
    init_db(engine)
    if is_populated(engine) and not args.reset:
        print(f"La base ya tiene datos ({database_url()}). Use --reset para reconstruirla.")
    else:
        t0 = time.perf_counter()
        counts = load_demo(engine)
        print(f"Base DEMO creada en {time.perf_counter() - t0:.1f} s:")
        for table, n in counts.items():
            print(f"  {table:<24}{n:>8}")
    for path in write_samples(SAMPLE_DIR):
        print(f"Archivo de ejemplo: {path.relative_to(SAMPLE_DIR.parents[1])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
