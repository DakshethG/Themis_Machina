import httpx
from bs4 import BeautifulSoup
import urllib.parse
import asyncio

HEADERS = {'User-Agent': 'Mozilla/5.0'}

async def search_act(query_str):
    q = urllib.parse.quote(f'"{query_str}"')
    url = f'https://www.indiacode.nic.in/simple-search?query={q}'
    async with httpx.AsyncClient(verify=False) as c:
        try:
            r = await c.get(url, headers=HEADERS, follow_redirects=True, timeout=15)
            soup = BeautifulSoup(r.text, 'html.parser')
            for a in soup.find_all('a', href=True):
                if '/handle/123456789/' in a['href'] and '?' not in a['href']:
                    title = a.get_text(strip=True)
                    if query_str.lower() in title.lower():
                        return a['href'].split('/handle/123456789/')[1]
        except Exception as e:
            return f'Error: {e}'
    return 'Not found'

async def main():
    missing = [
        'The Indian Penal Code, 1860',
        'The Code of Criminal Procedure, 1973',
        'The Indian Evidence Act, 1872',
        'The Factories Act, 1948'
    ]
    results = await asyncio.gather(*(search_act(m) for m in missing))
    for m, r in zip(missing, results):
        print(f'{m}: {r}')

asyncio.run(main())
