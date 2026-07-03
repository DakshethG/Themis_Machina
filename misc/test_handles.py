import httpx
from bs4 import BeautifulSoup
import asyncio

HEADERS = {'User-Agent': 'Mozilla/5.0'}

async def check(handle, name):
    url = f'https://www.indiacode.nic.in/handle/123456789/{handle}?sam_handle=123456789%2F1362'
    async with httpx.AsyncClient() as c:
        r = await c.get(url, headers=HEADERS, follow_redirects=True, timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')
        title = soup.find('h3', class_='page-header-heading')
        print(f'{name} ({handle}): {r.status_code} - {title.get_text(strip=True) if title else "NO TITLE"}')

async def main():
    await asyncio.gather(
        check('1572', 'CrPC'),
        check('1920', 'SC_ST_Act')
    )

asyncio.run(main())
