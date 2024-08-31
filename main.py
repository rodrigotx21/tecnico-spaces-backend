from flask import Flask, jsonify, request
from flask_cors import CORS
from google.cloud import storage
import requests
import json
import os


app = Flask(__name__)

# Enable CORS for all routes and origins
CORS(app)

BASE_URL = 'https://fenix.tecnico.ulisboa.pt/api/fenix/v1/spaces'
CACHE_FILE = 'data.json'
BUCKET_NAME = 'tecnico-spaces-data'  # Replace with your bucket name
FILE_NAME = 'data.json'

def fetch_data(url):
    """Fetch data from a given URL and return the JSON response."""
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"An error occurred: {e}")
        return {}

def build_location_path(space, path):
    """Build the location path for a given space."""
    return path + [
        {
            "type": space.get("type"),
            "name": space.get("name")
        }
    ]

def fetch_all_spaces(url, path=[]):
    """Recursively fetch all spaces and build location paths."""
    # Initialize a dictionary with lists for each space type
    all_spaces = {
        'CAMPUS': [],
        'BUILDING': [],
        'FLOOR': [],
        'ROOM': []
    }
    
    # Fetch the data from the URL
    data = fetch_data(url)

    # Determine if the data is a list or a dictionary and extract spaces
    if isinstance(data, list):
        spaces = data
    elif isinstance(data, dict):
        spaces = data.get('containedSpaces', [])
    else:
        spaces = []

    # Process each space in the list
    for space in spaces:
        location_path = build_location_path(space, path)
        space_info = {
            "id": space.get("id"),
            "name": space.get("name"),
            "type": space.get("type"),
            "location": path
        }

        # Append the space_info to the appropriate list in all_spaces
        space_type = space.get("type")
        if space_type in all_spaces:
            all_spaces[space_type].append(space_info)

        # Recursively fetch child spaces if applicable
        if space_type in ['CAMPUS', 'BUILDING', 'FLOOR']:
            child_spaces_url = f"{BASE_URL}/{space['id']}"
            child_spaces = fetch_all_spaces(child_spaces_url, location_path)

            # Merge the child spaces into the current all_spaces dictionary
            for key, value in child_spaces.items():
                if key in all_spaces:
                    all_spaces[key].extend(value)

    return all_spaces


def save_data_to_cache(data):
    """Save data to cache file."""
    storage_client = storage.Client()
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(FILE_NAME)

    with blob.open('w') as f:
        json.dump(data, f)

@app.route('/api/spaces', methods=['GET'])
def spaces():
    """Serve spaces data from cache."""
    
    storage_client = storage.Client()
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(FILE_NAME)

    with blob.open('r') as f:
        data = json.load(f)
    return data

@app.route('/api/fetch-new-data', methods=['GET'])
def fetch_new_data():
    """Fetch new data from the API and update the cache."""
    print("Fetching new data...")
    all_spaces = fetch_all_spaces(BASE_URL)
    save_data_to_cache(all_spaces)
    print("Data fetched and updated successfully!")
    print(len(all_spaces["CAMPUS"]))
    print(len(all_spaces["BUILDING"]))
    print(len(all_spaces["FLOOR"]))
    print(len(all_spaces["ROOM"]))
    return jsonify({"status": "Data fetched and updated successfully!"}), 200

if __name__ == '__main__':
    app.run(port=5000)