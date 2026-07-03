import time, re
from duckduckgo_search import DDGS
from scrape_india_code import ACTS

missing = [k for k in ACTS if not ACTS[k].get('known_handle')]
print(f'Missing handles: {len(missing)}')
results = {}
with DDGS() as ddgs:
    for k in missing[:5]: # testing 5 first
        query = f'site:indiacode.nic.in/handle/123456789/ "{ACTS[k]["title"]}"'
        print(f'Searching: {query}')
        try:
            for r in ddgs.text(query, max_results=3):
                m = re.search(r'handle/123456789/(\d+)', r['href'])
                if m:
                    results[k] = m.group(1)
                    break
        except Exception as e:
            print("Error", e)
        time.sleep(1)
print(results)
