import psycopg2

conn = psycopg2.connect(
    host='101.132.68.191',
    port=15432,
    user='sip_telecom',
    password='sN],Gb2hGmpRGRGDZhpP^tDGr_BW_C',
    database='carsem_alarm'
)
cur = conn.cursor()

# Check columns
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='llm_settings'")
cols = [row[0] for row in cur.fetchall()]
print("Current columns:", cols)

# Add missing columns
if 'text2sql_metadata' not in cols:
    cur.execute("ALTER TABLE llm_settings ADD COLUMN text2sql_metadata TEXT")
    print("Added text2sql_metadata column")

if 'text2sql_metrics' not in cols:
    cur.execute("ALTER TABLE llm_settings ADD COLUMN text2sql_metrics TEXT")
    print("Added text2sql_metrics column")

conn.commit()

# Verify
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='llm_settings'")
print("Final columns:", [row[0] for row in cur.fetchall()])

conn.close()
