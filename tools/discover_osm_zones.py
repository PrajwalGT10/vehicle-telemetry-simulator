import urllib.request
import urllib.parse
import json

overpass_url = "http://overpass-api.de/api/interpreter"
overpass_query = """
[out:json];
area[name="Bengaluru"]->.searchArea;
(
  relation["admin_level"="9"](area.searchArea);
);
out tags;
"""

data = urllib.parse.urlencode({'data': overpass_query}).encode()
req = urllib.request.Request(overpass_url, data=data)

try:
    with urllib.request.urlopen(req) as response:
        result = json.loads(response.read().decode())
        print(f"Found {len(result['elements'])} elements")
        for el in result['elements']:
            print(f"Name: {el.get('tags', {}).get('name', 'N/A')}")
except Exception as e:
    print(f"Error: {e}")
