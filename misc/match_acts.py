import scrape_india_code_1
from bs4 import BeautifulSoup
import re

with open('browse.html', 'r', encoding='utf-8') as f:
    soup = BeautifulSoup(f, 'html.parser')

browse_items = {}
for a in soup.select('div.artifact-title a'):
    title = a.get_text(strip=True).lower()
    href = a.get('href', '')
    m = re.search(r'/handle/123456789/(\d+)', href)
    if m:
        browse_items[title] = m.group(1)

updates = {}
for key, val in scrape_india_code_1.ACTS.items():
    title_matches = [t.lower() for t in val['title_match']]
    for b_title, handle in browse_items.items():
        if any(t in b_title for t in title_matches):
            updates[key] = handle
            break

print(f'Found {len(updates)} matches!')
for key, handle in updates.items():
    if scrape_india_code_1.ACTS[key]['handle'] != handle:
        print(f'{key}: {scrape_india_code_1.ACTS[key]["handle"]} -> {handle}')

with open('scrape_india_code_1.py', 'r', encoding='utf-8') as f:
    content = f.read()

for key, new_handle in updates.items():
    pattern = r'("' + key + r'":\s*\{[^}]*"handle":\s*")(\d+)(")'
    def repl(m, nh=new_handle):
        return m.group(1) + nh + m.group(3)
    content, count = re.subn(pattern, repl, content)

with open('scrape_india_code_1.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Updated handles successfully!')
