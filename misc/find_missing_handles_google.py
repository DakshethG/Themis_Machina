import time, re, json
from googlesearch import search

missing_acts = [
    'The Indian Penal Code, 1860',
    'The Code of Criminal Procedure, 1973',
    'The Indian Evidence Act, 1872',
    'The Bharatiya Sakshya Adhiniyam, 2023',
    'The Arms Act, 1959',
    'The Prevention of Money-Laundering Act, 2002',
    'The Limitation Act, 1963',
    'The Micro, Small and Medium Enterprises Development Act, 2006',
    'The Central Goods and Services Tax Act, 2017',
    'The Integrated Goods and Services Tax Act, 2017',
    'The Industrial Relations Code, 2020',
    'The Factories Act, 1948',
    'The Right to Information Act, 2005',
    'The Protection of Women from Domestic Violence Act, 2005',
    'The Protection of Children from Sexual Offences Act, 2012',
    'The Scheduled Castes and Scheduled Tribes (Prevention of Atrocities) Act, 1989',
    'The Digital Personal Data Protection Act, 2023',
    'The Telecommunications Act, 2023',
    'The Environment (Protection) Act, 1986',
    'The Indian Forest Act, 1927',
    'The Explosives Act, 1884'
]

results = {}
for title in missing_acts:
    query = f'site:indiacode.nic.in/handle/123456789/ "{title}"'
    found = False
    try:
        for url in search(query, num_results=3, sleep_interval=2):
            m = re.search(r'handle/123456789/(\d+)', url)
            if m:
                results[title] = m.group(1)
                found = True
                break
    except Exception as e:
        print(f"Error querying {title}: {e}")
    if not found:
        results[title] = 'NOT_FOUND'
    print(f"{title}: {results[title]}")

print("\n--- RESULTS JSON ---")
print(json.dumps(results, indent=2))
