import requests
import json

url = "https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline/58.91093418908123,-8.663193436749948/2024-07-17T22:00:00?key=N984KNMWVHBJU4B362VUTQHQU&include=current&elements=pressure&timezone=Z"
url2 = "https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timelinemulti?key=N984KNMWVHBJU4B362VUTQHQU&locations=57.04735417452501,-9.904648378296468|58.91093418908123,-8.663193436749948&datestart=2024-07-17T22:00:00&include=current"
x = requests.get(url)
if(x.status_code == 200):
    parsed = json.loads(x.text)
    with open("weatherAPI.json", "w") as f:
        json.dump(parsed, f, indent=4)
print(x.status_code)
print(x.elapsed)