# End-to-End Guitar Recommender System

An end-to-end Data Engineering, Machine Learning, and Web Application platform that **extracts web-scale guitar product data using Scrapy**, ingests it into an **AWS S3 Lakehouse**, processes it using **Databricks PySpark** and **MLflow** via a **Medallion Data Architecture**, and serves interactive recommendations through a modern **React frontend** powered by a **Node.js REST API**.

The system leverages **Bayesian Average Rating** scoring to handle rating confidence across sparse product reviews, combined with **$k$-Means clustering** and **PCA** for feature vector segmentation.

---

---

## Architecture Overview
```
+------------------+      +--------------------+      +-------------------------------------------+
|   Web Scraping   |      |   Cloud Storage    |      | Databricks Delta Lakehouse (Medallion)    |
| - Scrapy Spider  | ---> | - Amazon S3        | ---> | - Bronze: Raw Ingestion & Schema Capture  |
| - Playwright     |      |   Landing Zone     |      | - Silver: Bayesian Score & Vectorization  |
+------------------+      +--------------------+      | - Gold: Clustered ML Models & Tables      |
                                                      +-------------------------------------------+
                                                                            |
                                                                            v
+------------------+      +--------------------+      +-------------------------------------------+
| Node.js Frontend | <--- | Fast API / Backend | <--- |         MLflow & Model Tracking           |
| - React Explorer |      | - Node.js Express  |      | - K-Means & PCA Pipeline                  |
| - Dynamic Search |      |                    |      | - Similarity Vector Matcher               |
+------------------+      +--------------------+      +-------------------------------------------+
```

---

## ✨ Key Features

* **Automated Web Extraction:** Custom Scrapy spiders crawling web-scale guitar specifications, pricing, review counts, brand metadata, and product attributes.
* **AWS S3 Landing Area:** Cloud staging zone storing raw, unstructured crawl outputs.
* **Databricks Medallion Architecture:**
  * **Bronze Layer:** Ingests raw JSON/Parquet directly from S3 into Delta Lake without schema loss.
  * **Silver Layer:** Standardizes schema types, handles missing values, calculates **Bayesian Average Rating scores** to adjust raw review averages based on review confidence/volume, and generates $L_2$-normalized feature vectors.
  * **Gold Layer:** Serves dynamic product recommendation vectors, model clusters, and analytics catalogs.
* **Machine Learning & MLOps:**
  * Hyperparameter grid search across cluster counts ($k$) using PySpark `$k$-Means`.
  * Model evaluation using PySpark `ClusteringEvaluator` (Silhouette Score).
  * Dimensionality reduction via `PCA` for 2D spatial cluster visualization.
  * Full lifecycle, metrics, and pipeline artifact logging tracked via **MLflow**.
* **Interactive Frontend Application:** Modern Node.js/React interface allowing users to explore guitar cluster spaces, search catalogs, and receive item-to-item similarity recommendations.

---

##  Feature Scoring Method: Bayesian Average Rating

To prevent guitars with a single 5-star review from outranking highly rated instruments with thousands of reviews, the Silver pipeline calculates a **Bayesian Adjusted Score**:

$$W = \frac{v}{v + m} \cdot R + \frac{m}{v + m} \cdot C$$

Where:
* $R$ = Average rating of the guitar
* $v$ = Number of reviews for the guitar
* $m$ = Minimum reviews required threshold (prior weight parameter)
* $C$ = Mean rating across the entire catalog

---

##  Tech Stack

* **Web Scraping:** Python, Scrapy, Playwright
* **Cloud Storage & Lakehouse:** Amazon S3, Databricks Unity Catalog Volumes, PySpark, Delta Lake
* **Algorithms & Machine Learning:** Bayesian Scoring, PySpark ML (`KMeans`, `PCA`, `Normalizer`), MLflow
* **Frontend Application:** Node.js, React, Express, REST API
* **Environment Management:** Python 3.11+, Node.js 18+

---

## Project Structure

```text
.
├── backend/               # Server-side API & backend application logic
├── frontend/              # Web user interface (Node.js/React)
├── guitar_project/        # Scrapy spiders & data extraction pipeline
├── .gitignore             # Ignored tracking files (secrets, caches, dependencies)
├── raw_guitars1.json      # Sample raw scraped JSON dataset output
├── requirements.txt       # Global Python package dependencies
├── run_pipeline.py        # Entry point script to trigger the scraper/pipeline
├── scrapy.cfg             # Scrapy deployment and project configuration file
└── test.jsonl             # Scraped test output file (JSON Lines format)
```

