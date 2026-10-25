import pandas as pd
from neo4j import GraphDatabase

URI = "bolt://localhost:7687"
AUTH = ("neo4j", "nishanth")

driver = GraphDatabase.driver(URI, auth=AUTH)

df = pd.read_csv("voter_accounts.csv")

query = """
MERGE (v:Voter {voter_id: $voter_id})
SET v.password = $password,
    v.name = $name,
    v.has_voted = false,
    v.polling_station_id = $polling_station_id,
    v.polling_station_name = $polling_station_name
"""

with driver.session() as session:
    for _, row in df.iterrows():
        session.run(
            query,
            voter_id=int(row["login_id"]),
            password=str(row["password"]),
            name=str(row["name"]),
            polling_station_id=str(row["polling_station_id"]),
            polling_station_name=str(row["polling_station_name"])
        )

print(f"Imported {len(df)} voter accounts successfully!")

driver.close()