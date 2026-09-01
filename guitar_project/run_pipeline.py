import os
import time
import schedule
import subprocess
import boto3
from botocore.exceptions import BotoCoreError, ClientError
from dotenv import load_dotenv

# 1. Load variables from .env file
load_dotenv()

# 2. Read configuration parameters from .env
LOCAL_JSONL_FILE = os.getenv("LOCAL_JSONL_FILE", "raw_guitars1.json")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
S3_TARGET_KEY = os.getenv("S3_TARGET_KEY", "bronze/landing/raw_guitars1.json")
AWS_REGION = os.getenv("AWS_REGION", "eu-north-1")


# ==============================================================================
# PIPELINE EXECUTION FUNCTION
# ==============================================================================
def scrape_and_upload_job():
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    print(f"\n[{timestamp}] 🚀 Step 1: Running Scrapy spider (guitar1)...")

    # Clean up old local JSONL file if it exists so we start fresh
    if os.path.exists(LOCAL_JSONL_FILE):
        os.remove(LOCAL_JSONL_FILE)

    # 1. Trigger Scrapy spider via command line
    try:
        cmd = f"scrapy crawl guitar1 -o {LOCAL_JSONL_FILE}"
        subprocess.run(cmd, shell=True, check=True, cwd=os.path.dirname(os.path.abspath(__file__)))
        print(f"[{timestamp}] ✅ Scraping complete. Local file saved: '{LOCAL_JSONL_FILE}'.")
    except Exception as e:
        print(f"[{timestamp}] ❌ Error running Scrapy spider: {e}")
        return

    # 2. Upload file directly to Amazon S3
    try:
        print(f"[{timestamp}] 🚀 Step 2: Uploading file to Amazon S3 bucket '{S3_BUCKET_NAME}'...")
        
        # boto3 automatically uses AWS_ACCESS_KEY_ID & AWS_SECRET_ACCESS_KEY from .env
        s3_client = boto3.client('s3', region_name=AWS_REGION)
        
        s3_client.upload_file(
            Filename=LOCAL_JSONL_FILE,
            Bucket=S3_BUCKET_NAME,
            Key=S3_TARGET_KEY
        )
        
        print(f"[{timestamp}] ✅ Success! File uploaded to s3://{S3_BUCKET_NAME}/{S3_TARGET_KEY}")
    except (BotoCoreError, ClientError) as e:
        print(f"[{timestamp}] ❌ AWS S3 Error: {e}")
    except Exception as e:
        print(f"[{timestamp}] ❌ Unexpected error uploading to S3: {e}")


# ==============================================================================
# SCHEDULER SETTINGS (Every 3 Days at 01:00 AM)
# ==============================================================================
schedule.every(3).days.at("01:00").do(scrape_and_upload_job)

if __name__ == "__main__":
    print("==================================================")
    print("        VS Code Scrapy + AWS S3 Scheduler         ")
    print("==================================================")
    
    # Run once immediately when started (demo/test execution)
    print("[DEMO MODE] Executing initial run immediately...")
    scrape_and_upload_job()

    print("\nWaiting for 3-day periodic schedule... (Press Ctrl+C to exit)")
    while True:
        schedule.run_pending()
        time.sleep(10)