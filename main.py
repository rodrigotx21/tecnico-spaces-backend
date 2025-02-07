import json
from datetime import datetime

import requests
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, jsonify
from flask_cors import CORS
from pytz import timezone

from globals import ALWAYSOPEN, MISTAKES, CORRECTIONS, MAPS

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

def fetch_all_spaces(url, path=None):
    """Recursively fetch all spaces and build location paths."""
    # Initialize a dictionary with lists for each space type
    if path is None:
        path = []
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
        space_info = {
            'id': space.get("id"),
            'name': space.get("name"),
            'type': space.get("type"),
            'location': path
        }

        # Error Correction
        if space_info['id'] in MISTAKES:
            space_info[CORRECTIONS[space_info['id']]] = CORRECTIONS[space_info['id'] + 'c']

        location_path = build_location_path(space_info, path)

        # Add always Open
        if space_info["type"] == 'ROOM':
            space_info["alwaysOpen"] = space_info["name"] in ALWAYSOPEN
        
        # Add Maps
        if space_info["id"] in MAPS:
            space_info["map"] = MAPS[space_info["id"]]

        # Append the space_info to the appropriate list in all_spaces
        space_type = space_info["type"]

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
    with open(CACHE_FILE, 'w') as f:
        json.dump(data, f)

@app.route('/api/spaces', methods=['GET'])
def spaces():
    """Serve spaces data from cache."""

    with open(CACHE_FILE, 'r') as f:
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

@app.route('/api/schedule/<space_id>', methods=['GET'])
def schedule(space_id):
    day = datetime.today().strftime('%d/%m/%Y')
    print("Fetching space events data..."  + day)
    room_data = fetch_data(f"{BASE_URL}/{space_id}?day={day}")
    original_events = room_data.get("events", [])
    events = []
    
    for event in original_events:
        if event.get("type") == 'LESSON':
            title = event.get("course").get("name")
        else: 
            title = event.get("title")
        
        period = event.get("period")
        start = datetime.strptime(period.get("start"), '%d/%m/%Y %H:%M').strftime('%Y-%m-%d %H:%M')
        end = datetime.strptime(period.get("end"), '%d/%m/%Y %H:%M').strftime('%Y-%m-%d %H:%M')


        events.append({
            'title':  title,
            'time': {
                'start': start,
                'end': end
            },
            'isEditable': False,
            'id': space_id + start.replace(" ", "")
        })
    
    return jsonify(events)

def schedule_fetch_new_data():
    """Schedule the fetch_new_data function to run every Sunday at 3 AM."""
    scheduler = BackgroundScheduler()
    timezn = timezone('Europe/Lisbon')
    scheduler.add_job(fetch_new_data, 'cron', hour=3, minute=0, timezone=timezn)
    scheduler.start()

if __name__ == '__main__':
    fetch_new_data()
    schedule_fetch_new_data()
    app.run()
