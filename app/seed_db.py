import sqlite3
DB = "/app/uniparking.db"
conn = sqlite3.connect(DB)
c = conn.cursor()
c.execute("""CREATE TABLE IF NOT EXISTS plate_authorizations (
  id INTEGER PRIMARY KEY,
  plate TEXT UNIQUE,
  active INT DEFAULT 1
)""")
c.execute("INSERT OR IGNORE INTO plate_authorizations(plate, active) VALUES (?, 1)", ("SBA1234",))
conn.commit(); conn.close()
print("Seed OK: SBA1234 activa")