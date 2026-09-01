"""
Run this from the backend folder: python debug_env.py

Prints what got loaded from .env, with the token masked, so you can spot
blank values, stray quotes, whitespace, or a wrong-length token without
ever touching Databricks.
"""
from dotenv import load_dotenv
import os

load_dotenv()

host = os.environ.get("DATABRICKS_SERVER_HOSTNAME")
path = os.environ.get("DATABRICKS_HTTP_PATH")
token = os.environ.get("DATABRICKS_TOKEN")

print("DATABRICKS_SERVER_HOSTNAME:", repr(host))
print("DATABRICKS_HTTP_PATH:", repr(path))

if token is None:
    print("DATABRICKS_TOKEN: NOT SET")
else:
    print(f"DATABRICKS_TOKEN: length={len(token)}, starts_with={token[:5]!r}, "
          f"has_leading/trailing_whitespace={token != token.strip()}")