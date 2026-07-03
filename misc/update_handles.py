import re

with open('scrape_india_code_1.py', 'r', encoding='utf-8') as f:
    content = f.read()

updates = {
    'ipc': '2263',
    'crpc': '1572',
    'evidence_act': '2252',
    'bsa': '20063',
    'arms_act': '1612',
    'pmla': '2036',
    'limitation_act': '1353',
    'msme_act': '2013',
    'cgst': '20857',
    'igst': '2251',
    'labour_code': '22040',
    'factories_act': '1908',
    'right_to_information': '2065',
    'domestic_violence': '2021',
    'pocso': '2079',
    'sc_st_act': '1920',
    'digital_personal_data': '22037',
    'telecom_act': '20101',
    'environment_protection': '1876',
    'forest_act': '2388',
    'explosive_act': '2301'
}

for key, new_handle in updates.items():
    # Regex to match "key": { ... "handle": "old_handle"
    pattern = r'("' + key + r'":\s*\{[^}]*"handle":\s*")(\d+)(")'
    def repl(m):
        print(f"Replaced {key}: {m.group(2)} -> {new_handle}")
        return m.group(1) + new_handle + m.group(3)
    content, count = re.subn(pattern, repl, content)
    if count == 0:
        print(f"NOT FOUND: {key}")

with open('scrape_india_code_1.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Updated scrape_india_code_1.py successfully.')
