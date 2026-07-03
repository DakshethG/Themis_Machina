from googlesearch import search
import time
for q in [
    '"The Indian Penal Code" filetype:pdf',
    '"The Code of Criminal Procedure, 1973" filetype:pdf',
    '"The Indian Evidence Act, 1872" filetype:pdf',
    '"The Arms Act, 1959" filetype:pdf',
    '"The Limitation Act, 1963" filetype:pdf',
    '"The Central Goods and Services Tax Act, 2017" filetype:pdf',
    '"The Factories Act, 1948" filetype:pdf'
]:
    print(q)
    try:
        urls = list(search(q, num_results=2, sleep_interval=2))
        print(' ->', urls)
    except Exception as e:
        print('Error:', e)
