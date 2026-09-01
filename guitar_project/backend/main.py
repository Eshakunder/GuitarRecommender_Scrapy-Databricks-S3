"""
FastAPI backend for the guitar recommendation quiz.

Connects DIRECTLY to Databricks (no sqlite export step) via the
databricks-sql-connector, using a SQL Warehouse. Reads:

  guitar_project.gold.gold_guitar_catalog
  guitar_project.gold.guitar_clusters

Serves:
  GET  /api/quiz-options   -> brand list, fixed guitar-type options, and
                               price range, to populate the quiz UI
  POST /api/recommend      -> scored + KMeans-cluster-boosted recommendations
  POST /api/refresh        -> re-pull the tables from Databricks without restarting

USER INPUTS
-----------
The quiz collects exactly three things from the user:
  1. Guitar company / companies (brands) - multi-select
  2. Guitar type - single-select, fixed to Acoustic / Classical / Electric
  3. Price range in INR (budget_min / budget_max)

Those three answers are scored against gold_guitar_catalog. The top match's
KMeans cluster (guitar_clusters.cluster) is then used to pull a couple of
extra "similar" guitars into the results, so the model's clustering actually
does work in the recommendation, not just the exact brand/model filter.

COLUMN MAPPING
--------------
    guitar_id            -> logical "id"
    name_guitar           -> logical "model"
    final_company_name    -> logical "brand"
    type                   -> logical "guitar_type"  (kept, not user-facing)
    final_price_guitar     -> logical "price"
    guitar_rating           -> logical "rating"
    num_rating               -> logical "review_count"
    cluster                -> logical "cluster_id"  (guitar_clusters only)
"""

import os
from typing import Optional

import pandas as pd
from databricks import sql as databricks_sql
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Load variables from a .env file (in the same folder as this file) into
# os.environ. Without this, `python main.py` / `uvicorn main:app` will NOT
# see anything you put in .env, and os.environ[...] below will KeyError.
load_dotenv()

# ---------------------------------------------------------------------------
# Config - Databricks connection
# ---------------------------------------------------------------------------

DATABRICKS_SERVER_HOSTNAME = os.environ["DATABRICKS_SERVER_HOSTNAME"]  # e.g. adb-1234567890123456.7.azuredatabricks.net
DATABRICKS_HTTP_PATH = os.environ["DATABRICKS_HTTP_PATH"]              # e.g. /sql/1.0/warehouses/abc123def456
DATABRICKS_TOKEN = os.environ["DATABRICKS_TOKEN"]                       # a Databricks personal access token

DATABRICKS_CATALOG = os.environ.get("DATABRICKS_CATALOG", "guitar_project")
DATABRICKS_SCHEMA = os.environ.get("DATABRICKS_SCHEMA", "gold")

CATALOG_TABLE = f"{DATABRICKS_CATALOG}.{DATABRICKS_SCHEMA}.gold_guitar_catalog"
CLUSTERS_TABLE = f"{DATABRICKS_CATALOG}.{DATABRICKS_SCHEMA}.guitar_clusters"

# ---------------------------------------------------------------------------
# Config - column mapping
# ---------------------------------------------------------------------------

CONFIRMED_COLUMNS = {
    "id": "guitar_id",
    "brand": "final_company_name",
    "model": "name_guitar",
    "price": "final_price_guitar",
    "guitar_type": "type",
    "rating": "guitar_rating",       # 0-5 scale star rating
    "review_count": "num_rating",    # total number of ratings/reviews received
}

COLUMN_HINTS = {}


def detect_columns(columns: list[str]) -> dict:
    """Best-effort mapping from logical field -> actual column name, for the
    fields we don't already have ground truth for."""
    lower_cols = {c.lower(): c for c in columns}
    mapping = dict(CONFIRMED_COLUMNS)  # start from what we know for sure
    for field, hints in COLUMN_HINTS.items():
        if field in mapping:
            continue
        for hint in hints:
            for lc, original in lower_cols.items():
                if hint == lc or hint in lc:
                    mapping[field] = original
                    break
            if field in mapping:
                break
    return mapping


# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(title="Guitar Recommendation API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this to your frontend's origin in production
    allow_credentials=False,  # "*" + credentials=True is an invalid combo that
                               # Safari rejects outright; the frontend never
                               # sends cookies/credentials, so this is safe
    allow_methods=["*"],
    allow_headers=["*"],
)

catalog_df: pd.DataFrame = pd.DataFrame()
clusters_df: pd.DataFrame = pd.DataFrame()
cols: dict = {}


def get_connection():
    return databricks_sql.connect(
        server_hostname=DATABRICKS_SERVER_HOSTNAME,
        http_path=DATABRICKS_HTTP_PATH,
        access_token=DATABRICKS_TOKEN,
    )


def query_to_df(conn, query: str) -> pd.DataFrame:
    """Run a query over the Databricks SQL connector and return a DataFrame.
    Goes via cursor.fetchall() rather than pandas.read_sql, since the
    Databricks connector isn't a SQLAlchemy engine and this is the
    documented, reliable path."""
    with conn.cursor() as cursor:
        cursor.execute(query)
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
    return pd.DataFrame(rows, columns=columns)


def load_data():
    """Pull both gold tables straight from Databricks. Called at startup and
    again from POST /api/refresh whenever you want to pick up new data
    without restarting the server."""
    global catalog_df, clusters_df, cols

    conn = get_connection()
    try:
        catalog_df = query_to_df(conn, f"SELECT * FROM {CATALOG_TABLE}")
        try:
            clusters_df = query_to_df(conn, f"SELECT * FROM {CLUSTERS_TABLE}")
        except Exception as e:
            print(f"⚠ Could not load {CLUSTERS_TABLE}: {e}")
            clusters_df = pd.DataFrame()
    finally:
        conn.close()

    cols = detect_columns(list(catalog_df.columns))

    print("=" * 60)
    print(f"Loaded {len(catalog_df)} guitars from {CATALOG_TABLE}")
    print("Column mapping (✓ = confirmed from notebook, ? = auto-detected):")
    for field in ["id", "brand", "model", "price", "guitar_type", "rating", "review_count"]:
        marker = "✓" if field in CONFIRMED_COLUMNS else "?"
        print(f"  {marker} {field:>12} -> {cols.get(field, '⚠ NOT FOUND')}")
    if not clusters_df.empty:
        print(f"Loaded {len(clusters_df)} rows from {CLUSTERS_TABLE}")
    else:
        print(f"⚠ No cluster data loaded (table '{CLUSTERS_TABLE}' missing or empty)")
    print("=" * 60)

    # Merge cluster id onto the catalog on guitar_id
    id_col = cols.get("id")
    cluster_id_col = None
    if not clusters_df.empty and id_col and id_col in clusters_df.columns:
        for c in clusters_df.columns:
            if "cluster" in c.lower():
                cluster_id_col = c
                break
        if cluster_id_col:
            catalog_df = catalog_df.merge(
                clusters_df[[id_col, cluster_id_col]], on=id_col, how="left"
            )
            cols["cluster_id"] = cluster_id_col


@app.on_event("startup")
def startup():
    load_data()


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

# The type step is a fixed set, not driven by whatever raw strings happen to
# be in the `type` column (which may contain messier values like
# "Acoustic-Electric", "Semi-Hollow", etc). We match these against the
# `type` column with a substring check in score_row.
GUITAR_TYPE_OPTIONS = ["Acoustic", "Classical", "Electric"]


class QuizAnswers(BaseModel):
    brands: Optional[list[str]] = None  # multi-select: one or more companies
    guitar_type: Optional[str] = None    # one of GUITAR_TYPE_OPTIONS
    budget_min: float = Field(default=0)
    budget_max: float = Field(default=1_000_000)
    limit: int = Field(default=6, ge=1, le=20)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def col(field: str):
    """Return the actual Databricks column name for a logical field, or None."""
    return cols.get(field)


def row_to_card(row: pd.Series, reasons: list[str]) -> dict:
    def get(field, default=None):
        c = col(field)
        if c and c in row and pd.notna(row[c]):
            val = row[c]
            try:
                if field in ("price", "rating"):
                    return float(val)
                if field == "review_count":
                    return int(val)
            except (TypeError, ValueError):
                pass
            return val
        return default

    return {
        "id": get("id"),
        "brand": get("brand", "Unknown brand"),
        "model": get("model", "Unknown model"),
        "price": get("price"),
        "guitar_type": get("guitar_type"),
        "rating": get("rating"),
        "review_count": get("review_count"),
        "match_reasons": reasons,
    }


def score_row(row: pd.Series, answers: QuizAnswers) -> tuple[float, list[str]]:
    score = 0.0
    reasons = []

    def val(field):
        c = col(field)
        if c and c in row and pd.notna(row[c]):
            return str(row[c]).lower()
        return None

    # Brand (company) match - exact, case-insensitive, against any of the
    # user's selected companies
    if answers.brands:
        v = val("brand")
        wanted = {b.lower() for b in answers.brands}
        if v and v in wanted:
            score += 4
            reasons.append(f"Made by {row[col('brand')]}")

    # Guitar type match - substring, case-insensitive, against the fixed
    # Acoustic / Classical / Electric choice
    if answers.guitar_type:
        v = val("guitar_type")
        if v and answers.guitar_type.lower() in v:
            score += 4
            reasons.append(f"{answers.guitar_type} guitar")

    price_col = col("price")
    if price_col and price_col in row and pd.notna(row[price_col]):
        price = float(row[price_col])
        if answers.budget_min <= price <= answers.budget_max:
            score += 2
            reasons.append("Within your budget")
        else:
            span = max(answers.budget_max - answers.budget_min, 1)
            dist = min(abs(price - answers.budget_min), abs(price - answers.budget_max))
            score -= min(dist / span, 3)  # soft penalty, doesn't fully exclude it

    rating_col = col("rating")
    review_count_col = col("review_count")
    if rating_col and rating_col in row and pd.notna(row[rating_col]):
        rating_val = float(row[rating_col])
        score += rating_val * 0.1  # tiebreaker nudge
        if rating_val >= 4.5:
            reasons.append("Highly rated")

    if review_count_col and review_count_col in row and pd.notna(row[review_count_col]):
        count_val = float(row[review_count_col])
        # small popularity nudge, capped so it can't dominate the score
        score += min(count_val, 200) * 0.002

    return score, reasons


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health():
    return {"status": "ok", "guitars_loaded": len(catalog_df)}


@app.post("/api/refresh")
def refresh():
    """Re-pull gold_guitar_catalog and guitar_clusters from Databricks right
    now, without restarting the server. Call this after your notebook job
    reruns and overwrites the tables."""
    load_data()
    return {"status": "reloaded", "guitars_loaded": len(catalog_df)}


@app.get("/api/quiz-options")
def quiz_options():
    """Returns everything needed to populate all three quiz steps at once:
    the full brand list (for multi-select), the fixed guitar type options,
    and the price range (in whatever currency final_price_guitar is stored
    in - the frontend labels this as INR)."""
    brand_c = col("brand")
    price_c = col("price")

    def distinct(series: pd.Series):
        return sorted({str(v) for v in series.dropna().unique()})[:200]

    price_range = {"min": 0, "max": 500000}
    if price_c and price_c in catalog_df.columns and not catalog_df[price_c].dropna().empty:
        price_range = {
            "min": float(catalog_df[price_c].min()),
            "max": float(catalog_df[price_c].max()),
        }

    return {
        "brands": distinct(catalog_df[brand_c]) if brand_c and brand_c in catalog_df.columns else [],
        "guitar_types": GUITAR_TYPE_OPTIONS,
        "price_range": price_range,
        "detected_columns": cols,  # handy for debugging schema detection in the UI/devtools
    }


@app.post("/api/recommend")
def recommend(answers: QuizAnswers):
    if catalog_df.empty:
        raise HTTPException(status_code=503, detail="Catalog not loaded")

    scored = []
    for _, row in catalog_df.iterrows():
        s, reasons = score_row(row, answers)
        scored.append((s, reasons, row))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[: answers.limit]
    results = [row_to_card(row, reasons) for _, reasons, row in top]

    # KMeans cluster boost: pull a couple more from the same cluster as the
    # #1 pick, so the recommendation isn't just an exact brand/model filter -
    # it surfaces guitars the clustering considers similar.
    cluster_col = col("cluster_id")
    if results and cluster_col and cluster_col in catalog_df.columns:
        top_id = results[0]["id"]
        top_row = catalog_df[catalog_df[col("id")] == top_id]
        if not top_row.empty and pd.notna(top_row.iloc[0].get(cluster_col)):
            cluster_val = top_row.iloc[0][cluster_col]
            already_shown = {r["id"] for r in results}
            same_cluster = catalog_df[
                (catalog_df[cluster_col] == cluster_val)
                & (~catalog_df[col("id")].isin(already_shown))
            ].head(2)
            for _, row in same_cluster.iterrows():
                results.append(
                    row_to_card(row, ["Similar to your top pick (same cluster)"])
                )

    return {"count": len(results), "results": results}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)