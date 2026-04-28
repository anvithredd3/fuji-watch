import json
import sqlite3
from pathlib import Path


def _connect(db_path):
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path):
    with _connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                checked_at TEXT NOT NULL,
                source_url TEXT NOT NULL,
                selected_cameras_json TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS camera_snapshots (
                run_id INTEGER NOT NULL,
                camera_name TEXT NOT NULL,
                refurb_in_stock INTEGER NOT NULL,
                skus_json TEXT NOT NULL,
                options_json TEXT NOT NULL,
                PRIMARY KEY (run_id, camera_name),
                FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE
            )
            """
        )
        existing_columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(camera_snapshots)").fetchall()
        }
        if "product_url" not in existing_columns:
            conn.execute(
                "ALTER TABLE camera_snapshots ADD COLUMN product_url TEXT NOT NULL DEFAULT ''"
            )
        if "image_url" not in existing_columns:
            conn.execute(
                "ALTER TABLE camera_snapshots ADD COLUMN image_url TEXT NOT NULL DEFAULT ''"
            )
        if "specs_json" not in existing_columns:
            conn.execute(
                "ALTER TABLE camera_snapshots ADD COLUMN specs_json TEXT NOT NULL DEFAULT '[]'"
            )


def load_previous_state(db_path):
    init_db(db_path)
    with _connect(db_path) as conn:
        last_run = conn.execute(
            "SELECT id, checked_at, source_url, selected_cameras_json FROM runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if not last_run:
            return None

        rows = conn.execute(
            """
            SELECT camera_name, refurb_in_stock, skus_json, options_json, product_url, image_url, specs_json
            FROM camera_snapshots
            WHERE run_id = ?
            """,
            (last_run["id"],),
        ).fetchall()

        cameras = {}
        for row in rows:
            cameras[row["camera_name"]] = {
                "refurb_in_stock": bool(row["refurb_in_stock"]),
                "skus": json.loads(row["skus_json"]),
                "options": json.loads(row["options_json"]),
                "product_url": row["product_url"],
                "image_url": row["image_url"],
                "specs": json.loads(row["specs_json"]),
            }

        return {
            "run_id": last_run["id"],
            "checked_at": last_run["checked_at"],
            "source_url": last_run["source_url"],
            "selected_cameras": json.loads(last_run["selected_cameras_json"]),
            "cameras": cameras,
        }


def save_state(db_path, checked_at, source_url, selected_cameras, cameras):
    init_db(db_path)
    with _connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO runs (checked_at, source_url, selected_cameras_json)
            VALUES (?, ?, ?)
            """,
            (checked_at, source_url, json.dumps(selected_cameras)),
        )
        run_id = cur.lastrowid

        for camera_name, snapshot in cameras.items():
            conn.execute(
                """
                INSERT INTO camera_snapshots
                (run_id, camera_name, refurb_in_stock, skus_json, options_json, product_url, image_url, specs_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    camera_name,
                    1 if snapshot.get("refurb_in_stock") else 0,
                    json.dumps(snapshot.get("skus", [])),
                    json.dumps(snapshot.get("options", [])),
                    snapshot.get("product_url", ""),
                    snapshot.get("image_url", ""),
                    json.dumps(snapshot.get("specs", [])),
                ),
            )


def get_history(db_path, limit=365):
    init_db(db_path)
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT checked_at FROM runs ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [r["checked_at"] for r in reversed(rows)]
