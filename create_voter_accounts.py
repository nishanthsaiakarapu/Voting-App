import pandas as pd
import random
import string

# Your Parigi dataset
df = pd.read_csv(r"C:\Users\shrim\Downloads\VotingApp\Notebooks\pargi_voters_natural_full_uploaded.csv")

# Take 5 voters from every polling station
sample = df.groupby("polling_station_id", group_keys=False).head(5).copy()

# Create keypad-friendly numeric login IDs
sample["login_id"] = range(100001, 100001 + len(sample))

# Simple passwords for demo
sample["password"] = "pass" + sample["login_id"].astype(str)

# Initially nobody has voted
sample["has_voted"] = False

# Save accounts
sample[
    [
        "login_id",
        "password",
        "name",
        "voterid",
        "polling_station_id",
        "polling_station_name",
        "constituency_name",
        "distance_from_assigned_polling_booth_km",
        "has_voted"
    ]
].to_csv("voter_accounts.csv", index=False)

print("Accounts created:", len(sample))
print("Polling stations:", sample["polling_station_id"].nunique())
print("\nFirst 10 accounts:")
print(sample[["login_id", "password", "name", "polling_station_id"]].head(10))