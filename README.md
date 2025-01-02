# Search App - Meili Search Sample
### Sample item search for Vivitra using Meilisearch.

## Step 1 : Setup & Run Meilisearch

### Install Meilisearch
`curl -L https://install.meilisearch.com | sh`

### Launch Meilisearch
`./meilisearch`


[Install Meilisearch locally — Meilisearch documentation](https://www.meilisearch.com/docs/learn/self_hosted/install_meilisearch_locally)

## Step 2 : Run the Flask App

A flask app for API and Search GUI.

### Create a Virtual Environment
`python3 -m venv venv`

### Activate the Virtual Environment
`source venv/bin/activate`

### Run the App
`python app.py`

### GUI
`127.0.0.1:5000`

## Postman Collection

1. Import the postman collection
2. Run
	1. Sync - To sync data from csv to meilisearch
	2. Status - To see the sync task is processed
	3. Index - To see the settings
	4. Search - To test search API


