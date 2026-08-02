from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from neo4j import GraphDatabase
import math

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

URI = "bolt://localhost:7687"
AUTH = ("neo4j", "nishanth")  # CHANGE THIS TO YOUR NEO4J PASSWORD
driver = GraphDatabase.driver(URI, auth=AUTH)


class VoterLogin(BaseModel):
    voter_id: int
    password: str


class AdminLogin(BaseModel):
    admin_id: int
    password: str


# ---------- ESP32 VOTE ENDPOINT ----------
@app.post("/vote")
def record_vote(voter_id: int = Query(...), party: int = Query(...)):
    with driver.session() as session:
        # Check if voter exists and hasn't voted yet
        result = session.run(
            "MATCH (v:Voter {voter_id: $id}) RETURN v.has_voted AS voted, v.name AS name",
            id=voter_id
        ).single()
        
        if result is None:
            return {"success": False, "error": "Voter not found"}
        
        if result["voted"]:
            return {"success": False, "error": "Voter has already voted"}
        
        # Increment party vote count
        session.run(
            """
            MATCH (p:Party {party_id: $party_id})
            SET p.vote_count = p.vote_count + 1
            """,
            party_id=party
        )
        
        # Mark voter as having voted
        session.run(
            "MATCH (v:Voter {voter_id: $id}) SET v.has_voted = true",
            id=voter_id
        )
        
        return {"success": True, "message": "Vote recorded successfully"}


# ---------- VOTER LOGIN ----------
@app.post("/voter/login")
def voter_login(data: VoterLogin):
    with driver.session() as session:
        result = session.run(
            "MATCH (v:Voter {voter_id:$id}) RETURN v.password AS password, v.has_voted AS voted, v.name AS name",
            id=data.voter_id
        ).single()
        if result is None or result["password"] != data.password:
            return {"success": False, "error": "Invalid voter ID or password."}
        return {"success": True, "voted": result["voted"], "name": result["name"]}


# ---------- VOTER STATUS ----------
@app.get("/voter/{voter_id}/status")
def voter_status(voter_id: int):
    with driver.session() as session:
        result = session.run(
            "MATCH (v:Voter {voter_id:$id}) RETURN v.has_voted AS voted, v.name AS name",
            id=voter_id
        ).single()
        if result is None:
            return {"error": "voter not found"}
        return {"voted": result["voted"], "name": result["name"]}


# ---------- ADMIN LOGIN ----------
@app.post("/admin/login")
def admin_login(data: AdminLogin):
    with driver.session() as session:
        result = session.run(
            "MATCH (a:Admin {admin_id:$id}) RETURN a.password AS password",
            id=data.admin_id
        ).single()
        if result is None or result["password"] != data.password:
            return {"success": False, "error": "Invalid officer ID or password."}
        return {"success": True}


# ---------- ADMIN RESULTS ----------
@app.get("/admin/results")
def admin_results():
    with driver.session() as session:
        rows = session.run("""
            MATCH (p:Party)
            RETURN p.party_name AS party, p.vote_count AS votes
        """).data()
        
        totals = session.run("""
            MATCH (v:Voter) 
            RETURN count(v) AS total,
            count(CASE WHEN v.has_voted THEN 1 END) AS cast
        """).single()
        
        return {
            "results": rows,
            "total_voters": totals["total"],
            "total_cast": totals["cast"]
        }


# ---------- ADMIN VOTERS ----------
@app.get("/admin/voters")
def admin_voters():
    with driver.session() as session:
        rows = session.run("""
            MATCH (v:Voter) RETURN v.voter_id AS voter_id, v.has_voted AS voted
            ORDER BY v.voter_id
        """).data()
        return {"voters": rows}


# ---------- ADMIN RESET (NEW - FIXED) ----------
@app.post("/admin/reset")
def admin_reset():
    """
    Reset all votes to default (sets all vote counts to 0 and all voters to not voted)
    """
    with driver.session() as session:
        # Reset all party vote counts to 0
        session.run("""
            MATCH (p:Party)
            SET p.vote_count = 0
        """)
        
        # Reset all voters to not voted
        session.run("""
            MATCH (v:Voter)
            SET v.has_voted = false
        """)
        
        return {"success": True, "message": "All votes reset successfully"}


def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c