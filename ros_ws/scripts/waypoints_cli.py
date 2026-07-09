import googlemaps
import requests
import os

def g_c(address, api_key):
    """
    使用 Google Maps Geocoding API 獲取地址的經緯度。
    """
    gmaps = googlemaps.Client(key=api_key)
    try:
        results = gmaps.geocode(address)
    except googlemaps.exceptions.ApiError as e:
        raise RuntimeError(f"Google Maps API error: {e}")
    
    if results:
        loc = results[0]['geometry']['location']
        return loc['lat'], loc['lng']
    else:
        raise ValueError("No results found for the given address.")


# Load API key from environment (see .env / .env.example); never hardcode secrets
API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY")
if not API_KEY:
    raise SystemExit("GOOGLE_MAPS_API_KEY not set. Copy .env.example to .env, fill it, then: source .env")
gmaps = googlemaps.Client(key=API_KEY)
origin= input("Enter the origin address: ")
destination = input("Enter the destination address: ")
directions = gmaps.directions(origin, destination, mode="walking")
waypoints = []
if directions:
    steps = directions[0]['legs'][0]['steps']
    for step in steps:
        lat = step['end_location']['lat']
        lng = step['end_location']['lng']
        waypoints.append((lat, lng))

    print("\n 航點列表（共 {} 點）:".format(len(waypoints)))
    for i, wp in enumerate(waypoints):
        print(f"第{i+1}點：緯度 {wp[0]}, 經度 {wp[1]}")
else:
    print("❌ 找不到路徑，請確認地址是否正確")