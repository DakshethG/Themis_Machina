import httpx
import urllib.parse
from bs4 import BeautifulSoup
import asyncio

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36', 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'Accept-Language': 'en-US,en;q=0.9', 'Referer': 'https://indiankanoon.org/'}

async def test():
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=30.0) as client:
        # 1. doctypes first
        query = 'doctypes:supremecourt year:2024'
        url = 'https://indiankanoon.org/search/?formInput=' + urllib.parse.quote(query) + '&pagenum=0'
        r = await client.get(url)
        soup = BeautifulSoup(r.text, 'html.parser')
        print('doctypes first Found:', len(soup.select("a[href^='/doc/']")))
        
        # 2. doctypes last
        query = 'year:2024 doctypes:supremecourt'
        url = 'https://indiankanoon.org/search/?formInput=' + urllib.parse.quote(query) + '&pagenum=0'
        r = await client.get(url)
        soup = BeautifulSoup(r.text, 'html.parser')
        print('doctypes last Found:', len(soup.select("a[href^='/doc/']")))

if __name__ == '__main__':
    asyncio.run(test())
