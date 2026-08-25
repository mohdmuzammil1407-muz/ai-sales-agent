import os
from dotenv import load_dotenv
load_dotenv()
import psycopg2

conn = psycopg2.connect(os.getenv('DATABASE_URL'))
conn.autocommit = True
cur = conn.cursor()

wipe_order = [
  'otp_codes', 'messages', 'leads', 'conversations',
]

for table in wipe_order:
  try:
    cur.execute(f'DELETE FROM {table}')
    print(f'Cleared {table}: {cur.rowcount} rows')
  except Exception as e:
    print(f'Skip {table}: {e}')

# Reset ID sequences
cur.execute("""
  SELECT sequence_name FROM information_schema.sequences
  WHERE sequence_schema = \'public\'
""")
for seq in cur.fetchall():
  cur.execute(f'ALTER SEQUENCE {seq[0]} RESTART WITH 1')
  print(f'Reset sequence: {seq[0]}')

cur.close()
conn.close()
print()
print('Database wiped and sequences reset.')
