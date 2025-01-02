import time
from flask import Flask, request, jsonify, render_template
import requests
import csv
import os
import logging
import uuid

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Meilisearch Configuration
MEILISEARCH_URL = 'http://localhost:7700'
MASTER_KEY = 'masterKey'
INDEX_NAME = 'items'

# Path to your CSV data file
DATA_FILE = 'items.csv'

def load_data():
    """Load and parse CSV data, and add a unique primary key if not present."""
    try:
        items = []
        with open(DATA_FILE, mode='r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                # Add UUID if no id present
                if 'id' not in row:
                    row['id'] = str(uuid.uuid4())
                items.append(row)
                
        logger.info(f"✅ Loaded {len(items)} records from CSV with unique IDs added")
        if items:
            logger.info(f"🔄 First record for verification: {items[0]}")
        return items
        
    except FileNotFoundError:
        logger.error(f"❌ Could not find data file: {DATA_FILE}")
        return []
    except Exception as e:
        logger.error(f"❌ Error loading data: {str(e)}")
        return []

def sync_data_to_meilisearch():
    """Sync CSV data with Meilisearch."""
    try:
        data = load_data()
        
        # Configure Meilisearch client
        url = MEILISEARCH_URL
        headers = {'Authorization': f'Bearer {MASTER_KEY}'}
        
        # Delete existing index if any
        try:
            requests.delete(f'{url}/indexes/{INDEX_NAME}', headers=headers)
            logger.info("🗑️ Existing index deleted")
        except:
            logger.warning("Failed to delete existing index or matching index not found. Continuing...")

        # Create new index with settings
        index_config = {
            "primaryKey": "id",
            "searchableAttributes": [
                "item_name",
                "item_code",
                "brand",
                "category"
            ],
            "typoTolerance": {
                "enabled": True,
                "minWordSizeForTypos": {
                    "oneTypo": 3,
                    "twoTypos": 6
                }
            }
        }
        
        requests.post(f'{url}/indexes/{INDEX_NAME}', headers=headers, json=index_config)
        logger.info("✅ Index created with search settings")

        # Update search settings
        search_settings = {
            "rankingRules": [
                "typo",
                "proximity",
                "attribute",
                "words",
                "sort",
                "exactness"
            ],
            "distinctAttribute": None
        }
        
        requests.patch(f'{url}/indexes/{INDEX_NAME}/settings', headers=headers, json=search_settings)
        
        # Add documents
        response = requests.post(
            f'{url}/indexes/{INDEX_NAME}/documents', 
            headers=headers,
            json=data
        )
        
        logger.info(f"📤 Document sync response: {response.status_code} - {response.text}")
        return True

    except Exception as e:
        logger.error(f"❌ Sync failed: {str(e)}")
        return False

def configure_meilisearch():
    """Configure Meilisearch index settings."""
    headers = {'Authorization': f'Bearer {MASTER_KEY}'}
    
    settings = {
        "filterableAttributes": ["brand", "category"],
        "searchableAttributes": [
            "item_name",
            "brand",
            "category"
        ],
        "sortableAttributes": ["item_name"],
        "typoTolerance": {
            "enabled": True,
            "minWordSizeForTypos": {
                "oneTypo": 2,
                "twoTypos": 3
            },
            "disableOnWords": [],
            "disableOnAttributes": []
        },
        "rankingRules": [
            "words",
            "typo",
            "proximity",
            "attribute",
            "exactness"
        ],
        "faceting": {
            "maxValuesPerFacet": 100
        },
        "synonyms": {
            "ml": ["milliliter", "milliliters", "ml", " ml"],
            "tab": ["tablet", "tablets"],
            "cap": ["capsule", "capsules"],
            "asp": ["aspidosperma", "aspido"],
            "q": ["mother tincture", "tincture" "tinct"],
            "bioforce": ["bioforce", "bio force"]
        },
        "proximityPrecision": "byWord",
        "pagination": {
            "maxTotalHits": 30000
        }
    }

    response = requests.patch(
        f'{MEILISEARCH_URL}/indexes/{INDEX_NAME}/settings',
        json=settings,
        headers=headers
    )
    return response.json()


@app.route('/sync', methods=['POST'])
def sync():
    """Manually trigger data sync from CSV file to Meilisearch."""
    sync_response = sync_data_to_meilisearch()
    config_response = configure_meilisearch()
    return jsonify({"sync": sync_response, "config": config_response})


@app.route('/search', methods=['GET'])
def search():
    """Search query with optional filters."""
    query = request.args.get('q', '')
    brand = request.args.get('brand')
    category = request.args.get('category')

    if not query:
        return jsonify({"error": "Query parameter 'q' is required"}), 400

    headers = {'Authorization': f'Bearer {MASTER_KEY}'}
    search_url = f'{MEILISEARCH_URL}/indexes/{INDEX_NAME}/search'

    filters = []
    if brand:
        filters.append(f'brand = "{brand}"')
    if category:
        filters.append(f'category = "{category}"')

    payload = {'q': query}
    if filters:
        payload['filter'] = " AND ".join(filters)

    response = requests.post(search_url, json=payload, headers=headers)
    return jsonify(response.json())


@app.route('/status', methods=['GET'])
def check_status():
    """Check status of sync and config tasks."""
    try:
        headers = {'Authorization': f'Bearer {MASTER_KEY}'}
        
        # Get tasks status
        tasks_url = f'{MEILISEARCH_URL}/tasks'
        response = requests.get(tasks_url, headers=headers)
        tasks = response.json()
        
        # Get index stats
        stats_url = f'{MEILISEARCH_URL}/indexes/{INDEX_NAME}/stats'
        stats_response = requests.get(stats_url, headers=headers)
        stats = stats_response.json()
        
        return jsonify({
            "tasks": tasks['results'][:5],  # Last 5 tasks
            "index_stats": {
                "numberOfDocuments": stats.get('numberOfDocuments', 0),
                "isIndexed": stats.get('isIndexed', False)
            }
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/')
def index():

    # get unique brands and categories from CSV
    brands = set()
    categories = set()

    with open(DATA_FILE, mode='r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            brands.add(row.get('brand'))
            categories.add(row.get('category'))

    return render_template('index.html', brands=brands, categories=categories)

# Add to sync function to wait for completion
def wait_for_task(task_id):
    """Wait for Meilisearch task to complete."""
    headers = {'Authorization': f'Bearer {MASTER_KEY}'}
    task_url = f'{MEILISEARCH_URL}/tasks/{task_id}'
    
    while True:
        response = requests.get(task_url, headers=headers)
        status = response.json().get('status')
        if status in ['succeeded', 'failed']:
            return status
        time.sleep(0.5)


if __name__ == '__main__':
    print("Syncing and Configuring Meilisearch...")
    sync_data_to_meilisearch()
    configure_meilisearch()
    print("Setup Complete.")
    app.run(host='0.0.0.0', port=5000, debug=True)
