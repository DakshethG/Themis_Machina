import re

with open('scrape_india_code_1.py', 'r', encoding='utf-8') as f:
    content = f.read()

keys_to_remove = ['ipc', 'crpc', 'evidence_act']

for key in keys_to_remove:
    pattern = r'\s*"' + key + r'":\s*\{[^}]+\},?'
    content = re.sub(pattern, '', content)

with open('scrape_india_code_1.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Removed from scrape_india_code_1.py')
