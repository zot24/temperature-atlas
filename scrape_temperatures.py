#!/usr/bin/env python3
"""
Scrape city temperature data from Wikipedia and store in SQLite database.
"""

import requests
from bs4 import BeautifulSoup
import sqlite3
import re

def fetch_wikipedia_page():
    """Fetch the Wikipedia page with city temperature data."""
    url = "https://en.wikipedia.org/wiki/List_of_cities_by_average_temperature"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.text

def parse_temperature(temp_str):
    """Parse temperature string and return float value in Celsius."""
    if not temp_str or temp_str.strip() in ['', '—', '-', 'N/A']:
        return None

    # Remove any parentheses content (Fahrenheit values)
    temp_str = re.sub(r'\([^)]*\)', '', temp_str)

    # Extract the number
    match = re.search(r'[-−]?\d+\.?\d*', temp_str)
    if match:
        # Replace unicode minus with standard minus
        value = match.group().replace('−', '-')
        try:
            return float(value)
        except ValueError:
            return None
    return None

def find_preceding_continent(table):
    """Find the continent name from the h2 header before this table."""
    continents = ['Africa', 'Asia', 'Europe', 'North America', 'Oceania', 'South America']

    # Search backwards through previous siblings and parents
    current = table
    while current:
        # Check previous siblings
        prev = current.find_previous_sibling()
        while prev:
            if prev.name == 'h2':
                headline = prev.find(id=True)
                if headline:
                    text = headline.get('id', '').replace('_', ' ')
                    if text in continents:
                        return text
            prev = prev.find_previous_sibling()

        # Move to parent and continue
        current = current.parent

    return None

def extract_tables(html):
    """Extract temperature data from all tables on the page."""
    soup = BeautifulSoup(html, 'html.parser')

    all_data = []

    # Map table index to continent based on page order
    continent_order = ['Africa', 'Asia', 'Europe', 'North America', 'Oceania', 'South America']

    # Find all wikitable tables
    tables = soup.find_all('table', class_='wikitable')

    for idx, table in enumerate(tables):
        # Assign continent based on table order (6 continents = 6 tables)
        if idx < len(continent_order):
            current_continent = continent_order[idx]
        else:
            continue

        rows = table.find_all('tr')

        for row in rows[1:]:  # Skip header row
            cells = row.find_all(['td', 'th'])
            if len(cells) >= 14:  # Country, City, 12 months, Year
                country = cells[0].get_text().strip()
                city = cells[1].get_text().strip()

                # Clean up country and city names
                country = re.sub(r'\[.*?\]', '', country).strip()
                city = re.sub(r'\[.*?\]', '', city).strip()

                # Skip if country or city is empty
                if not country or not city:
                    continue

                # Get monthly temperatures (cells 2-13)
                monthly_temps = []
                for i in range(2, 14):
                    if i < len(cells):
                        temp = parse_temperature(cells[i].get_text())
                        monthly_temps.append(temp)
                    else:
                        monthly_temps.append(None)

                # Get yearly average (cell 14, index 14)
                yearly_avg = None
                if len(cells) > 14:
                    yearly_avg = parse_temperature(cells[14].get_text())

                # If no yearly average in table, calculate from monthly
                if yearly_avg is None:
                    valid_temps = [t for t in monthly_temps if t is not None]
                    if valid_temps:
                        yearly_avg = sum(valid_temps) / len(valid_temps)

                all_data.append({
                    'continent': current_continent,
                    'country': country,
                    'city': city,
                    'jan': monthly_temps[0],
                    'feb': monthly_temps[1],
                    'mar': monthly_temps[2],
                    'apr': monthly_temps[3],
                    'may': monthly_temps[4],
                    'jun': monthly_temps[5],
                    'jul': monthly_temps[6],
                    'aug': monthly_temps[7],
                    'sep': monthly_temps[8],
                    'oct': monthly_temps[9],
                    'nov': monthly_temps[10],
                    'dec': monthly_temps[11],
                    'yearly_avg': yearly_avg
                })

    return all_data

def create_database(data, db_path='city_temperatures.db'):
    """Create SQLite database with temperature data."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create tables
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS continents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS countries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            continent_id INTEGER,
            FOREIGN KEY (continent_id) REFERENCES continents(id),
            UNIQUE(name, continent_id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            country_id INTEGER,
            FOREIGN KEY (country_id) REFERENCES countries(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS temperatures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            city_id INTEGER,
            jan REAL,
            feb REAL,
            mar REAL,
            apr REAL,
            may REAL,
            jun REAL,
            jul REAL,
            aug REAL,
            sep REAL,
            oct REAL,
            nov REAL,
            dec_temp REAL,
            yearly_avg REAL,
            FOREIGN KEY (city_id) REFERENCES cities(id)
        )
    ''')

    # Create a view for easy querying
    cursor.execute('''
        CREATE VIEW IF NOT EXISTS city_temperature_view AS
        SELECT
            cont.name as continent,
            coun.name as country,
            c.name as city,
            t.jan, t.feb, t.mar, t.apr, t.may, t.jun,
            t.jul, t.aug, t.sep, t.oct, t.nov, t.dec_temp as dec,
            t.yearly_avg
        FROM temperatures t
        JOIN cities c ON t.city_id = c.id
        JOIN countries coun ON c.country_id = coun.id
        JOIN continents cont ON coun.continent_id = cont.id
    ''')

    # Insert data
    continent_ids = {}
    country_ids = {}

    for row in data:
        # Insert continent
        if row['continent'] not in continent_ids:
            cursor.execute('INSERT OR IGNORE INTO continents (name) VALUES (?)', (row['continent'],))
            cursor.execute('SELECT id FROM continents WHERE name = ?', (row['continent'],))
            continent_ids[row['continent']] = cursor.fetchone()[0]

        # Insert country
        country_key = (row['country'], row['continent'])
        if country_key not in country_ids:
            cursor.execute('INSERT OR IGNORE INTO countries (name, continent_id) VALUES (?, ?)',
                         (row['country'], continent_ids[row['continent']]))
            cursor.execute('SELECT id FROM countries WHERE name = ? AND continent_id = ?',
                         (row['country'], continent_ids[row['continent']]))
            country_ids[country_key] = cursor.fetchone()[0]

        # Insert city
        cursor.execute('INSERT INTO cities (name, country_id) VALUES (?, ?)',
                      (row['city'], country_ids[country_key]))
        city_id = cursor.lastrowid

        # Insert temperature data
        cursor.execute('''
            INSERT INTO temperatures (city_id, jan, feb, mar, apr, may, jun, jul, aug, sep, oct, nov, dec_temp, yearly_avg)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (city_id, row['jan'], row['feb'], row['mar'], row['apr'], row['may'], row['jun'],
              row['jul'], row['aug'], row['sep'], row['oct'], row['nov'], row['dec'], row['yearly_avg']))

    conn.commit()

    # Print summary
    cursor.execute('SELECT COUNT(*) FROM cities')
    city_count = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM countries')
    country_count = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM continents')
    continent_count = cursor.fetchone()[0]

    print(f"\nDatabase created successfully: {db_path}")
    print(f"  - {continent_count} continents")
    print(f"  - {country_count} countries")
    print(f"  - {city_count} cities")

    # Show sample data
    print("\nSample data from database:")
    cursor.execute('''
        SELECT continent, country, city, yearly_avg
        FROM city_temperature_view
        ORDER BY yearly_avg DESC
        LIMIT 10
    ''')
    print("\nTop 10 hottest cities:")
    for row in cursor.fetchall():
        print(f"  {row[2]}, {row[1]} ({row[0]}): {row[3]:.1f}°C" if row[3] else f"  {row[2]}, {row[1]} ({row[0]}): N/A")

    cursor.execute('''
        SELECT continent, country, city, yearly_avg
        FROM city_temperature_view
        WHERE yearly_avg IS NOT NULL
        ORDER BY yearly_avg ASC
        LIMIT 10
    ''')
    print("\nTop 10 coldest cities:")
    for row in cursor.fetchall():
        print(f"  {row[2]}, {row[1]} ({row[0]}): {row[3]:.1f}°C")

    conn.close()

def main():
    print("Fetching Wikipedia page...")
    html = fetch_wikipedia_page()

    print("Parsing temperature data...")
    data = extract_tables(html)

    print(f"Found {len(data)} cities with temperature data")

    if data:
        print("Creating SQLite database...")
        create_database(data)
    else:
        print("No data found!")

if __name__ == '__main__':
    main()
