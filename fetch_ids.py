import urllib.request
import re

queries = ['neon-portrait', 'dj-club', 'cocktail-bar', 'magazine-night']

for query in queries:
    url = f"https://unsplash.com/s/photos/{query}"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        html = urllib.request.urlopen(req).read().decode('utf-8')
        # Find images.unsplash.com/photo-xxx links
        photos = re.findall(r'https://images\.unsplash\.com/photo-[a-zA-Z0-9\-]+', html)
        photos = list(set(photos))
        print(f"--- {query} ---")
        for p in photos[:3]:
            print(p)
    except Exception as e:
        print(f"Error on {query}: {e}")
