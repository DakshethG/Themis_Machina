Write-Host "Scraping Priority/Landmark cases..."
.\.venv\Scripts\python scrape_sc_judgments.py --mode priority --output corpus/raw/cases/sc/

Write-Host "Scraping Recent Years..."
.\.venv\Scripts\python scrape_sc_judgments.py --mode bulk --year 2024 --target 100
.\.venv\Scripts\python scrape_sc_judgments.py --mode bulk --year 2023 --target 100
.\.venv\Scripts\python scrape_sc_judgments.py --mode bulk --year 2022 --target 75
.\.venv\Scripts\python scrape_sc_judgments.py --mode bulk --year 2021 --target 75
.\.venv\Scripts\python scrape_sc_judgments.py --mode bulk --year 2020 --target 50
.\.venv\Scripts\python scrape_sc_judgments.py --mode bulk --year 2019 --target 50
.\.venv\Scripts\python scrape_sc_judgments.py --mode bulk --year 2018 --target 50

Write-Host "All scraping completed!"
