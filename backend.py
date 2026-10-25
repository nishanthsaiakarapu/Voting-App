from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from neo4j import GraphDatabase
from groq import Groq
import math
import os


# ============================================================
# FASTAPI APP
# ============================================================

app = FastAPI(title="Electronic Voting System API")


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# NEO4J DATABASE
# ============================================================

URI = "bolt://localhost:7687"
AUTH = ("neo4j", "nishanth")

driver = GraphDatabase.driver(
    URI,
    auth=AUTH
)


# ============================================================
# GROQ
# ============================================================

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

groq_client = None

if GROQ_API_KEY:
    groq_client = Groq(api_key=GROQ_API_KEY)
    print("Groq API configured successfully.")
else:
    print("WARNING: GROQ_API_KEY is not set.")
    print("Chatbot will not work until GROQ_API_KEY is configured.")


# Current Groq model
GROQ_MODEL = "openai/gpt-oss-120b"


# ============================================================
# DATA MODELS
# ============================================================

class VoterLogin(BaseModel):
    voter_id: int
    password: str


class AdminLogin(BaseModel):
    admin_id: int
    password: str


class ChatRequest(BaseModel):
    voter_id: int
    message: str


# ============================================================
# ROOT / HEALTH CHECK
# ============================================================

@app.get("/")
def root():
    return {
        "success": True,
        "message": "Electronic Voting System API is running"
    }


# ============================================================
# ESP32 VOTE ENDPOINT
# ============================================================

@app.post("/vote")
def record_vote(
    voter_id: int = Query(...),
    party: int = Query(...)
):

    with driver.session() as session:

        # ----------------------------------------------------
        # Check voter
        # ----------------------------------------------------

        voter = session.run(
            """
            MATCH (v:Voter {voter_id: $id})
            RETURN
                v.has_voted AS voted,
                v.name AS name
            """,
            id=voter_id
        ).single()

        if voter is None:
            return {
                "success": False,
                "error": "Voter not found"
            }

        # ----------------------------------------------------
        # Check duplicate vote
        # ----------------------------------------------------

        if voter["voted"]:
            return {
                "success": False,
                "error": "Voter has already voted"
            }

        # ----------------------------------------------------
        # Check party
        # ----------------------------------------------------

        party_result = session.run(
            """
            MATCH (p:Party {party_id: $party_id})
            RETURN p.party_name AS party_name
            """,
            party_id=party
        ).single()

        if party_result is None:
            return {
                "success": False,
                "error": "Invalid party"
            }

        # ----------------------------------------------------
        # Increase party vote count
        # ----------------------------------------------------

        session.run(
            """
            MATCH (p:Party {party_id: $party_id})
            SET p.vote_count = coalesce(p.vote_count, 0) + 1
            """,
            party_id=party
        )

        # ----------------------------------------------------
        # Mark voter as voted
        # ----------------------------------------------------

        session.run(
            """
            MATCH (v:Voter {voter_id: $id})
            SET v.has_voted = true
            """,
            id=voter_id
        )

        return {
            "success": True,
            "message": "Vote recorded successfully",
            "voter_id": voter_id,
            "party": party_result["party_name"]
        }


# ============================================================
# VOTER LOGIN
# ============================================================

@app.post("/voter/login")
def voter_login(data: VoterLogin):

    with driver.session() as session:

        result = session.run(
            """
            MATCH (v:Voter {voter_id: $id})
            RETURN
                v.password AS password,
                v.has_voted AS voted,
                v.name AS name,
                v.polling_station_id AS polling_station_id,
                v.polling_station_name AS polling_station_name
            """,
            id=data.voter_id
        ).single()

        if result is None:
            return {
                "success": False,
                "error": "Invalid voter ID or password."
            }

        if result["password"] != data.password:
            return {
                "success": False,
                "error": "Invalid voter ID or password."
            }

        return {
            "success": True,
            "voter_id": data.voter_id,
            "voted": bool(result["voted"]),
            "name": result["name"],
            "polling_station_id": result["polling_station_id"],
            "polling_station_name": result["polling_station_name"]
        }


# ============================================================
# VOTER STATUS
# ============================================================

@app.get("/voter/{voter_id}/status")
def voter_status(voter_id: int):

    with driver.session() as session:

        result = session.run(
            """
            MATCH (v:Voter {voter_id: $id})
            RETURN
                v.voter_id AS voter_id,
                v.has_voted AS voted,
                v.name AS name,
                v.polling_station_id AS polling_station_id,
                v.polling_station_name AS polling_station_name
            """,
            id=voter_id
        ).single()

        if result is None:
            return {
                "success": False,
                "error": "Voter not found"
            }

        return {
            "success": True,
            "voter_id": result["voter_id"],
            "voted": bool(result["voted"]),
            "name": result["name"],
            "polling_station_id": result["polling_station_id"],
            "polling_station_name": result["polling_station_name"]
        }


# ============================================================
# VOTER ELECTION ASSISTANT / CHATBOT
# ============================================================

@app.post("/voter/chat")
def voter_chat(data: ChatRequest):

    # --------------------------------------------------------
    # Check whether Groq is configured
    # --------------------------------------------------------

    if groq_client is None:
        return {
            "success": False,
            "error": "Groq API key is not configured."
        }

    # --------------------------------------------------------
    # Get voter information from Neo4j
    # --------------------------------------------------------

    with driver.session() as session:

        result = session.run(
            """
            MATCH (v:Voter {voter_id: $id})
            RETURN
                v.voter_id AS voter_id,
                v.name AS name,
                v.has_voted AS voted,
                v.polling_station_id AS polling_station_id,
                v.polling_station_name AS polling_station_name
            """,
            id=data.voter_id
        ).single()

    if result is None:
        return {
            "success": False,
            "error": "Voter not found"
        }

    # --------------------------------------------------------
    # Convert voting status into readable text
    # --------------------------------------------------------

    if result["voted"]:
        voting_status = "Voted"
    else:
        voting_status = "Not Voted"

    # --------------------------------------------------------
    # Information given to Groq
    # --------------------------------------------------------

    voter_information = f"""
Voter ID: {result["voter_id"]}
Name: {result["name"]}
Voting Status: {voting_status}
Polling Station ID: {result["polling_station_id"]}
Polling Station Name: {result["polling_station_name"]}
"""

    # --------------------------------------------------------
    # System instructions
    # --------------------------------------------------------

    system_prompt = f"""
You are an Election Assistant for an Electronic Voting System.

The user is already authenticated.

You must answer questions ONLY using the voter information
provided below.

VOTER INFORMATION:
{voter_information}

You can answer questions such as:

- What is my voter ID?
- What is my name?
- Have I voted?
- Did I vote?
- What is my polling station?
- Where is my polling station?
- What is my polling station ID?

RULES:

1. Never invent information.
2. Never reveal information about another voter.
3. Only answer using this authenticated voter's information.
4. If information is unavailable, clearly say it is unavailable.
5. Keep answers short and simple.
6. Do not give political opinions.
7. Do not recommend any party or candidate.
8. Do not make up a polling station location.
"""

    # --------------------------------------------------------
    # Call Groq
    # --------------------------------------------------------

    try:

        response = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": data.message
                }
            ],
            temperature=0.2,
            max_tokens=200
        )

        answer = response.choices[0].message.content

        return {
            "success": True,
            "answer": answer
        }

    except Exception as e:

        print("Groq error:", str(e))

        return {
            "success": False,
            "error": "Unable to process chatbot request."
        }


# ============================================================
# ADMIN LOGIN
# ============================================================

@app.post("/admin/login")
def admin_login(data: AdminLogin):

    with driver.session() as session:

        result = session.run(
            """
            MATCH (a:Admin {admin_id: $id})
            RETURN a.password AS password
            """,
            id=data.admin_id
        ).single()

        if result is None:
            return {
                "success": False,
                "error": "Invalid officer ID or password."
            }

        if result["password"] != data.password:
            return {
                "success": False,
                "error": "Invalid officer ID or password."
            }

        return {
            "success": True
        }


# ============================================================
# ADMIN RESULTS
# ============================================================

@app.get("/admin/results")
def admin_results():
    # Aggregate turnout only. Party results are intentionally not exposed.
    with driver.session() as session:
        totals = session.run(
            """
            MATCH (v:Voter)
            RETURN count(v) AS total,
                   count(CASE WHEN v.has_voted = true THEN 1 END) AS cast
            """
        ).single()

    total_voters = totals["total"]
    total_cast = totals["cast"]
    return {
        "success": True,
        "total_voters": total_voters,
        "total_cast": total_cast,
        "total_not_cast": total_voters - total_cast
    }


# ============================================================
# POST-ELECTION NON-VOTER ACCESSIBILITY ANALYSIS
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
NONVOTER_AREA_FILE = os.path.join(BASE_DIR, "nonvoter_area_analysis.csv")
CONSTITUENCY_FILE = os.path.join(BASE_DIR, "constituency_nonvoter_analysis.csv")
BUILDINGS_FILE = os.path.join(BASE_DIR, "candidate_polling_buildings.csv")


def read_csv_rows(path):
    import csv
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


@app.get("/admin/analysis/summary")
def analysis_summary():
    rows = read_csv_rows(NONVOTER_AREA_FILE)
    constituency = read_csv_rows(CONSTITUENCY_FILE)
    if not rows or not constituency:
        return {"success": False, "error": "Non-voter analysis CSV files are missing."}

    c = constituency[0]
    return {
        "success": True,
        "constituency": c["constituency"],
        "constituency_number": int(float(c["constituency_number"])),
        "registered_voters": int(float(c["registered_voters"])),
        "voted_voters": int(float(c["voted_voters"])),
        "not_voted_voters": int(float(c["not_voted_voters"])),
        "turnout_pct": round(float(c["turnout_pct"]), 2),
        "avg_nonvoter_distance_km": round(float(c["avg_nonvoter_distance_km"]), 2),
        "areas_analyzed": int(float(c["areas_analyzed"])),
        "high_priority_areas": int(float(c["high_priority_areas"]))
    }


@app.get("/admin/analysis/nonvoter-areas")
def nonvoter_areas():
    rows = read_csv_rows(NONVOTER_AREA_FILE)
    if not rows:
        return {"success": False, "error": "nonvoter_area_analysis.csv is missing."}
    for r in rows:
        for k in ["non_voters", "current_booths"]:
            r[k] = int(float(r[k]))
        for k in ["avg_distance_km", "max_distance_km", "nonvoters_4km_pct", "avg_age", "priority_score"]:
            r[k] = round(float(r[k]), 2)
    return {"success": True, "areas": rows}


@app.get("/admin/analysis/nonvoter-area/{area}")
def nonvoter_area(area: str):
    rows = read_csv_rows(NONVOTER_AREA_FILE)
    row = next((r for r in rows if r["area"] == area), None)
    if row is None:
        return {"success": False, "error": "Area not found."}
    for k in ["non_voters", "current_booths"]:
        row[k] = int(float(row[k]))
    for k in ["avg_distance_km", "max_distance_km", "nonvoters_4km_pct", "avg_age", "priority_score"]:
        row[k] = round(float(row[k]), 2)
    return {"success": True, "area": row}

@app.get("/admin/analysis/nonvoter-area/{area}/buildings")
def nonvoter_area_buildings(
    area: str,
    max_distance_km: float = 1.5,
    conversion_rate_pct: float = 60.0
):
    areas = read_csv_rows(NONVOTER_AREA_FILE)
    constituency = read_csv_rows(CONSTITUENCY_FILE)
    buildings = read_csv_rows(BUILDINGS_FILE)

    row = next(
        (r for r in areas if str(r.get("area", "")).strip() == area.strip()),
        None
    )

    if row is None:
        return {"success": False, "error": "Area not found."}

    if not constituency:
        return {
            "success": False,
            "error": "Constituency analysis is missing."
        }

    if not buildings:
        return {
            "success": False,
            "error": "candidate_polling_buildings.csv is missing or empty."
        }

    max_distance_km = max(
        0.1,
        min(float(max_distance_km), 20.0)
    )

    conversion_rate_pct = max(
        0.0,
        min(float(conversion_rate_pct), 100.0)
    )

    def clean(value):
        return str(value or "").strip().lower()

    def get_distance(building):
        value = building.get("estimated_new_distance_km")

        if value in (None, ""):
            value = building.get(
                "estimated_distance_from_nonvoters_km"
            )

        try:
            return float(value)
        except:
            return 999.0

    # Only available buildings
    available = [
        b for b in buildings
        if clean(
            b.get("available_for_demo", "Yes")
        ) in ("yes", "true", "1", "")
    ]

    area_name = clean(row.get("area"))
    current_booth = clean(row.get("current_booth"))

    # ---------------------------------------------------------
    # 1. Exact area match
    # ---------------------------------------------------------
    matching = [
        b for b in available
        if clean(b.get("area")) == area_name
    ]

    # ---------------------------------------------------------
    # 2. Booth match
    # ---------------------------------------------------------
    if not matching and current_booth:
        matching = [
            b for b in available
            if clean(b.get("current_booth")) == current_booth
        ]

    # ---------------------------------------------------------
    # 3. Different building group for each area
    # ---------------------------------------------------------
    if not matching:

        groups = {}

        for b in available:
            booth = str(
                b.get("current_booth", "")
            ).strip()

            if booth:
                groups.setdefault(booth, []).append(b)

        group_keys = sorted(groups.keys())

        if group_keys:
            bucket = sum(
                (i + 1) * ord(ch)
                for i, ch in enumerate(area_name)
            )

            selected_booth = group_keys[
                bucket % len(group_keys)
            ]

            matching = groups[selected_booth]

    # ---------------------------------------------------------
    # Distance filter
    # ---------------------------------------------------------
    matching = [
        b for b in matching
        if get_distance(b) <= max_distance_km
    ]

    # If threshold removes everything, show nearest building
    if not matching:

        fallback = [
            b for b in available
            if clean(b.get("area")) == area_name
        ]

        if not fallback:
            fallback = available

        if fallback:
            matching = [
                min(fallback, key=get_distance)
            ]

    # ---------------------------------------------------------
    # Turnout calculation
    # ---------------------------------------------------------
    registered = int(
        float(constituency[0]["registered_voters"])
    )

    voted = int(
        float(constituency[0]["voted_voters"])
    )

    current_turnout = float(
        constituency[0]["turnout_pct"]
    )

    old_distance = float(
        row["avg_distance_km"]
    )

    non_voters = int(
        float(row["non_voters"])
    )

    candidates = []

    for building in matching:

        new_distance = get_distance(building)

        if old_distance > 0:
            reduction_ratio = max(
                0.0,
                min(
                    1.0,
                    (old_distance - new_distance)
                    / old_distance
                )
            )
        else:
            reduction_ratio = 0.0

        raw_gain = (
            non_voters
            * reduction_ratio
            * (conversion_rate_pct / 100.0)
        )

        try:
            capacity = int(
                float(building.get("capacity", 0))
            )
        except:
            capacity = 0

        if capacity > 0:
            estimated_gain = min(
                raw_gain,
                capacity
            )
        else:
            estimated_gain = raw_gain

        new_voted = min(
            registered,
            voted + estimated_gain
        )

        new_turnout = (
            new_voted / registered
        ) * 100.0

        candidates.append({
            "building_id":
                building.get("building_id", ""),

            "building_name":
                building.get(
                    "building_name",
                    "Candidate Building"
                ),

            "new_distance_km":
                round(new_distance, 2),

            "capacity":
                capacity,

            "distance_reduction_km":
                round(
                    max(
                        0.0,
                        old_distance - new_distance
                    ),
                    2
                ),

            "estimated_additional_voters":
                int(round(estimated_gain)),

            "estimated_new_turnout_pct":
                round(new_turnout, 2),

            "turnout_increase_pct":
                round(
                    new_turnout - current_turnout,
                    2
                ),

            "assumption_conversion_rate_pct":
                round(
                    conversion_rate_pct,
                    1
                )
        })

    candidates.sort(
        key=lambda x: (
            -x["turnout_increase_pct"],
            x["new_distance_km"]
        )
    )

    return {
        "success": True,
        "area": row["area"],
        "non_voters": non_voters,
        "old_avg_distance_km":
            round(old_distance, 2),
        "current_turnout_pct":
            round(current_turnout, 2),
        "max_distance_km":
            round(max_distance_km, 2),
        "conversion_rate_pct":
            round(conversion_rate_pct, 1),
        "candidates": candidates
    }


@app.get("/admin/analysis/recommendations")
def analysis_recommendations():

    areas = read_csv_rows(NONVOTER_AREA_FILE)
    buildings = read_csv_rows(BUILDINGS_FILE)

    if not areas or not buildings:
        return {
            "success": False,
            "error":
                "Non-voter/building CSV files are missing."
        }

    def clean(value):
        return str(value or "").strip().lower()

    def get_distance(building):

        value = building.get(
            "estimated_new_distance_km"
        )

        if value in (None, ""):
            value = building.get(
                "estimated_distance_from_nonvoters_km"
            )

        try:
            return float(value)
        except:
            return 999.0

    available = [
        b for b in buildings
        if clean(
            b.get("available_for_demo", "Yes")
        ) in ("yes", "true", "1", "")
    ]

    groups = {}

    for b in available:

        booth = str(
            b.get("current_booth", "")
        ).strip()

        if booth:
            groups.setdefault(
                booth,
                []
            ).append(b)

    group_keys = sorted(groups.keys())

    results = []

    for area in areas:

        area_name = clean(
            area.get("area")
        )

        candidates = [
            b for b in available
            if clean(b.get("area"))
            == area_name
        ]

        if not candidates and group_keys:

            bucket = sum(
                (i + 1) * ord(ch)
                for i, ch in enumerate(area_name)
            )

            selected_booth = group_keys[
                bucket % len(group_keys)
            ]

            candidates = groups[
                selected_booth
            ]

        if not candidates:
            continue

        best = min(
            candidates,
            key=get_distance
        )

        results.append({

            "area":
                area["area"],

            "non_voters":
                int(float(area["non_voters"])),

            "avg_distance_km":
                round(
                    float(area["avg_distance_km"]),
                    2
                ),

            "far_4km_pct":
                round(
                    float(
                        area["nonvoters_4km_pct"]
                    ),
                    1
                ),

            "building_name":
                best.get(
                    "building_name",
                    "Candidate Building"
                ),

            "building_id":
                best.get(
                    "building_id",
                    ""
                ),

            "estimated_new_distance_km":
                round(
                    get_distance(best),
                    2
                ),

            "capacity":
                int(
                    float(
                        best.get(
                            "capacity",
                            0
                        )
                    )
                )
        })

    return {
        "success": True,
        "recommendations": results
    }
# ============================================================
# ADMIN VOTERS
# ============================================================

@app.get("/admin/voters")
def admin_voters():

    with driver.session() as session:

        rows = session.run(
            """
            MATCH (v:Voter)
            RETURN
                v.voter_id AS voter_id,
                v.name AS name,
                v.has_voted AS voted,
                v.polling_station_id AS polling_station_id,
                v.polling_station_name AS polling_station_name
            ORDER BY v.voter_id
            """
        ).data()

        return {
            "success": True,
            "voters": rows
        }


# ============================================================
# ADMIN RESET
# ============================================================

@app.post("/admin/reset")
def admin_reset():

    with driver.session() as session:

        # ----------------------------------------------------
        # Reset party vote counts
        # ----------------------------------------------------

        session.run(
            """
            MATCH (p:Party)
            SET p.vote_count = 0
            """
        )

        # ----------------------------------------------------
        # Reset voter status
        # ----------------------------------------------------

        session.run(
            """
            MATCH (v:Voter)
            SET v.has_voted = false
            """
        )

        return {
            "success": True,
            "message": "All votes reset successfully"
        }


# ============================================================
# HAVERSINE DISTANCE
# ============================================================

def haversine(lat1, lon1, lat2, lon2):

    R = 6371.0

    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = (
        math.sin(dlat / 2) ** 2
        +
        math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )

    c = 2 * math.atan2(
        math.sqrt(a),
        math.sqrt(1 - a)
    )

    return R * c


# ============================================================
# SHUTDOWN
# ============================================================

@app.on_event("shutdown")
def shutdown_event():
    driver.close()