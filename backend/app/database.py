from pathlib import Path
import aiosqlite

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR/ "waypoint.db"

async def init_db(db_path = DB_PATH):
    async with aiosqlite.connect(db_path) as db:

        await db.execute("PRAGMA foreign_keys = ON")
        # foreign key -> a missing document should belong to
        # a real application... 

        await db.execute("""
            CREATE TABLE IF NOT EXISTS applications(
            application_id TEXT PRIMARY KEY,
            destination TEXT NOT NULL,
            status TEXT NOT NULL,
            travel_date TEXT NOT NULL
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS missing_documents (
                application_id TEXT NOT NULL,
                document_code TEXT NOT NULL,

                PRIMARY KEY (application_id, document_code),

                FOREIGN KEY (application_id)
                    REFERENCES applications(application_id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS idempotency_records (
                idempotency_key TEXT PRIMARY KEY,
                operation TEXT NOT NULL,
                application_id TEXT NOT NULL,
                requested_value TEXT NOT NULL,
                response_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS handoff_requests (
                handoff_id TEXT PRIMARY KEY,
                application_id TEXT NOT NULL,
                reason_code TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,

                FOREIGN KEY (application_id)
                    REFERENCES applications(application_id)
            )
        """)


        
        seed_applications =  [
            ("APP001", "Solara", "blocked", "2026-09-10"),
            ("APP002", "Solara", "processing", "2026-10-05"),
            ("APP003", "Norvik", "action_required", "2026-09-28"),
            ("APP004", "Norvik", "approved", "2026-11-12"),
        ]

        seed_missing_documents = [
            ("APP001", "bank_statement"),
            ("APP003", "passport_scan"),
        ]

        await db.executemany("""
            INSERT OR IGNORE INTO applications
            (application_id, destination, status, travel_date)
            VALUES (? , ? , ? , ?)
        """, seed_applications)

        await db.executemany("""
            INSERT OR IGNORE INTO missing_documents
            (application_id, document_code)
            VALUES (?, ?)
        """, seed_missing_documents)

        await db.commit()