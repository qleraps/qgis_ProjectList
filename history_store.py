# -*- coding: utf-8 -*-
"""SQLite-lag for ProjectList: gemmer historik over åbnede/gemte projekter."""

import os
import sqlite3
from datetime import datetime
from urllib.parse import urlsplit, parse_qs


class HistoryStore:
    """En række pr. projekt (unik på sti/URI), med tæller, tidsstempler og
    pin-status. Ubegrænset i antal - der slettes aldrig automatisk, kun via
    brugerens egen "Fjern fra historik".

    Et projekt kan enten være en almindelig fil (path normaliseres til en
    absolut sti) eller et projekt gemt via en QgsProjectStorage-backend
    (f.eks. en PostGIS-forbindelse) - her er "path" den fulde URI som QGIS
    selv bruger til at genåbne det, og den normaliseres IKKE som en filsti."""

    COLUMNS = [
        "path", "filename", "folder", "first_opened", "last_opened",
        "opened_count", "pinned", "is_storage",
    ]

    def __init__(self, db_path):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._create_schema()

    def _create_schema(self):
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS history (
                path TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                folder TEXT NOT NULL,
                first_opened TEXT NOT NULL,
                last_opened TEXT NOT NULL,
                opened_count INTEGER NOT NULL DEFAULT 1,
                pinned INTEGER NOT NULL DEFAULT 0,
                is_storage INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        # Migration for baser oprettet før is_storage-kolonnen fandtes.
        existing_cols = {row[1] for row in self._conn.execute("PRAGMA table_info(history)")}
        if "is_storage" not in existing_cols:
            self._conn.execute("ALTER TABLE history ADD COLUMN is_storage INTEGER NOT NULL DEFAULT 0")
        self._conn.commit()

    @staticmethod
    def normalize(path):
        return os.path.normpath(os.path.abspath(path))

    @staticmethod
    def _describe_storage(path):
        """Læsbart navn + placering for et projekt gemt via en
        QgsProjectStorage-backend (f.eks. PostGIS), ud fra dets URI.
        Bruger kun ikke-følsomme dele af URI'en (aldrig brugernavn/kodeord)."""
        try:
            parsed = urlsplit(path)
            query = parse_qs(parsed.query)
        except ValueError:
            return path, ""

        scheme = parsed.scheme or "?"

        if scheme.startswith("postgres"):
            dbname = query.get("dbname", [None])[0]
            schema = query.get("schema", [None])[0]
            project = query.get("project", [None])[0]
            parts = [p for p in (dbname, schema, project) if p]
            name = ".".join(parts) if parts else path
            host = parsed.hostname or ""
            port = f":{parsed.port}" if parsed.port else ""
            location = f"{scheme}://{host}{port}" if host else scheme
            return name, location

        project_name = query.get("projectName", [None])[0]
        name = project_name or os.path.basename(parsed.path) or path
        location = f"{scheme}:{os.path.dirname(parsed.path)}" if parsed.path else scheme
        return name, location

    def record_open(self, path, is_storage=False):
        """Opretter en ny historik-række, eller opdaterer sidst åbnet/tæller
        på en eksisterende. Filstier normaliseres til en absolut sti;
        storage-URI'er (is_storage=True) bruges uændret som nøgle."""
        if not path:
            return
        now = datetime.now().isoformat(timespec="seconds")

        if is_storage:
            key = path
            filename, folder = self._describe_storage(path)
        else:
            key = self.normalize(path)
            filename = os.path.basename(key)
            folder = os.path.dirname(key)

        cur = self._conn.execute("SELECT 1 FROM history WHERE path = ?", (key,))
        if cur.fetchone() is None:
            self._conn.execute(
                "INSERT INTO history "
                "(path, filename, folder, first_opened, last_opened, opened_count, pinned, is_storage) "
                "VALUES (?, ?, ?, ?, ?, 1, 0, ?)",
                (key, filename, folder, now, now, 1 if is_storage else 0),
            )
        else:
            self._conn.execute(
                "UPDATE history SET last_opened = ?, opened_count = opened_count + 1, "
                "filename = ?, folder = ? WHERE path = ?",
                (now, filename, folder, key),
            )
        self._conn.commit()

    def get_all(self):
        cur = self._conn.execute(
            "SELECT path, filename, folder, first_opened, last_opened, opened_count, pinned, is_storage "
            "FROM history"
        )
        return [dict(zip(self.COLUMNS, row)) for row in cur.fetchall()]

    def set_pinned(self, path, pinned):
        # `path` skal være nøglen som gemt (fra get_all()) - må IKKE
        # filsti-normaliseres igen her, ellers ødelægges storage-URI'er.
        self._conn.execute("UPDATE history SET pinned = ? WHERE path = ?", (1 if pinned else 0, path))
        self._conn.commit()

    def remove(self, path):
        self._conn.execute("DELETE FROM history WHERE path = ?", (path,))
        self._conn.commit()

    def update_path(self, old_path, new_path):
        """Bruges når en manglende fil bliver fundet igen et andet sted -
        historikken (pin, tæller, first_opened) følger med til den nye sti.
        Kun relevant for almindelige filer, ikke storage-URI'er."""
        new_key = self.normalize(new_path)
        filename = os.path.basename(new_key)
        folder = os.path.dirname(new_key)
        self._conn.execute(
            "UPDATE history SET path = ?, filename = ?, folder = ? WHERE path = ?",
            (new_key, filename, folder, old_path),
        )
        self._conn.commit()

    def close(self):
        self._conn.close()
