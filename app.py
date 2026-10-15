import os
import sqlite3
import json
import csv
import io
import re
from datetime import datetime, timedelta
from flask import Flask, jsonify, request, render_template_string, g, Response

app = Flask(__name__)
DB_PATH = os.environ.get("DB_PATH", "fixflow.db")

PRIORITIES = ["Low", "Medium", "High", "Critical"]
STATUSES = ["Open", "In Progress", "Resolved"]
CATEGORIES = [
    "Electrical",
    "HVAC & Cooling",
    "Audio/Visual & IT",
    "Laboratory Equipment",
    "Plumbing & Sanitation",
    "Civil & Structural",
    "General Maintenance"
]

TECHNICIANS = [
    {"name": "R. Ramesh", "role": "Chief Electrician", "dept": "Electrical"},
    {"name": "S. Murugan", "role": "HVAC Specialist", "dept": "HVAC & Cooling"},
    {"name": "P. Karthik", "role": "AV/IT Systems Engineer", "dept": "Audio/Visual & IT"},
    {"name": "Dr. V. Deepa", "role": "Lab Equipment In-charge", "dept": "Laboratory Equipment"},
    {"name": "M. Selvam", "role": "Plumbing Supervisor", "dept": "Plumbing & Sanitation"},
    {"name": "A. Anbarasan", "role": "Civil Works Overseer", "dept": "Civil & Structural"}
]

# ---------- DATABASE HELPERS & MIGRATION ----------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    cur = db.cursor()
    cur.execute(
        """CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            equipment TEXT NOT NULL,
            location TEXT NOT NULL,
            description TEXT NOT NULL,
            priority TEXT NOT NULL DEFAULT 'Medium',
            category TEXT NOT NULL DEFAULT 'General Maintenance',
            status TEXT NOT NULL DEFAULT 'Open',
            reporter_name TEXT NOT NULL DEFAULT 'Campus Member',
            reporter_contact TEXT DEFAULT '',
            assigned_to TEXT DEFAULT 'Unassigned',
            image_data TEXT DEFAULT '',
            safety_alert TEXT DEFAULT '',
            ai_analysis TEXT DEFAULT '',
            resolution_notes TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            resolved_at TEXT DEFAULT ''
        )"""
    )
    # Check if existing schema needs new columns
    cur.execute("PRAGMA table_info(reports)")
    existing_cols = {row[1] for row in cur.fetchall()}
    needed_cols = {
        "category": "TEXT NOT NULL DEFAULT 'General Maintenance'",
        "reporter_name": "TEXT NOT NULL DEFAULT 'Campus Member'",
        "reporter_contact": "TEXT DEFAULT ''",
        "assigned_to": "TEXT DEFAULT 'Unassigned'",
        "image_data": "TEXT DEFAULT ''",
        "safety_alert": "TEXT DEFAULT ''",
        "ai_analysis": "TEXT DEFAULT ''",
        "resolution_notes": "TEXT DEFAULT ''",
        "resolved_at": "TEXT DEFAULT ''"
    }
    for col, col_def in needed_cols.items():
        if col not in existing_cols:
            try:
                cur.execute(f"ALTER TABLE reports ADD COLUMN {col} {col_def}")
            except Exception:
                pass

    db.commit()

    # Pre-seed sample college campus data if table is completely empty
    cur.execute("SELECT COUNT(*) FROM reports")
    if cur.fetchone()[0] == 0:
        seed_campus_data(db)

    db.close()


def seed_campus_data(db):
    now = datetime.now()
    samples = [
        {
            "equipment": "Fume Hood Exhaust Motor",
            "location": "Chemistry Block, Lab 204",
            "description": "Exhaust fan motor emitting high-pitched screech and smoke smell while acid experiment is active.",
            "priority": "Critical",
            "category": "Laboratory Equipment",
            "status": "In Progress",
            "reporter_name": "Dr. S. Meenakshi (Faculty)",
            "reporter_contact": "ext. 4412",
            "assigned_to": "Dr. V. Deepa",
            "safety_alert": "⚠️ ACUTE TOXICITY HAZARD: Chemical vapors accumulating. Evacuate Lab 204 immediately until motor is serviced.",
            "ai_analysis": json.dumps({
                "urgency_score": 96,
                "confidence": 98,
                "safety_risk": "Hazardous vapor & fire risk",
                "suggested_technician": "Lab Equipment Specialist",
                "estimated_time": "1 - 2 Hours"
            }),
            "resolution_notes": "",
            "created_at": (now - timedelta(minutes=45)).strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": (now - timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S"),
            "resolved_at": ""
        },
        {
            "equipment": "4K Laser Projector & Audio Rack",
            "location": "ECE Seminar Hall, Ground Floor",
            "description": "HDMI port connection loose, projector lamp flickers every 2 minutes. International guest lecture scheduled at 3 PM.",
            "priority": "High",
            "category": "Audio/Visual & IT",
            "status": "Open",
            "reporter_name": "Arun Kumar (Student Sec.)",
            "reporter_contact": "98402 11234",
            "assigned_to": "P. Karthik",
            "safety_alert": "",
            "ai_analysis": json.dumps({
                "urgency_score": 84,
                "confidence": 92,
                "safety_risk": "High event disruption",
                "suggested_technician": "AV/IT Systems Engineer",
                "estimated_time": "30 - 45 Mins"
            }),
            "resolution_notes": "",
            "created_at": (now - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": (now - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S"),
            "resolved_at": ""
        },
        {
            "equipment": "Main Distribution Switchboard",
            "location": "Central Library, 2nd Floor Reading Hall",
            "description": "Visible electrical sparks and burning plastic smell coming from MCB circuit 4 behind circulation counter.",
            "priority": "Critical",
            "category": "Electrical",
            "status": "Open",
            "reporter_name": "Librarian J. Sundaram",
            "reporter_contact": "lib@gct.ac.in",
            "assigned_to": "R. Ramesh",
            "safety_alert": "⚡ ELECTRICAL FIRE HAZARD: Isolate main feeder B-04 immediately. Do NOT use water-based extinguishers.",
            "ai_analysis": json.dumps({
                "urgency_score": 99,
                "confidence": 99,
                "safety_risk": "Electrical fire & shock hazard",
                "suggested_technician": "Chief Electrician",
                "estimated_time": "45 Mins"
            }),
            "resolution_notes": "",
            "created_at": (now - timedelta(minutes=20)).strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": (now - timedelta(minutes=20)).strftime("%Y-%m-%d %H:%M:%S"),
            "resolved_at": ""
        },
        {
            "equipment": "Split Air Conditioner 2.0 Ton",
            "location": "CSE Department, AI & Cloud Computing Lab",
            "description": "Continuous water dripping directly over Server Rack #2. Temperature in server room rising past 28°C.",
            "priority": "High",
            "category": "HVAC & Cooling",
            "status": "In Progress",
            "reporter_name": "K. Harini (System Admin)",
            "reporter_contact": "sysadmin@gct.ac.in",
            "assigned_to": "S. Murugan",
            "safety_alert": "⚠️ SERVER WATER INGRESS: Relocate rack electronics or install temporary drip tarp immediately.",
            "ai_analysis": json.dumps({
                "urgency_score": 88,
                "confidence": 94,
                "safety_risk": "Server equipment damage & short circuit",
                "suggested_technician": "HVAC Specialist",
                "estimated_time": "1 - 2 Hours"
            }),
            "resolution_notes": "Drain pipe unclogged; testing condensation pump now.",
            "created_at": (now - timedelta(hours=3, minutes=10)).strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": (now - timedelta(minutes=40)).strftime("%Y-%m-%d %H:%M:%S"),
            "resolved_at": ""
        },
        {
            "equipment": "Hydraulic Pressure Test Bench",
            "location": "Mechanical Engineering, Fluid Mechanics Lab",
            "description": "High pressure oil gauge diaphragm ruptured during student fluid flow experiment. Oil pooling on shop floor.",
            "priority": "Medium",
            "category": "Laboratory Equipment",
            "status": "Open",
            "reporter_name": "R. Vignesh (Lab Tech)",
            "reporter_contact": "ext. 3301",
            "assigned_to": "Unassigned",
            "safety_alert": "⚠️ SLIPPERY FLOOR: Apply sawdust or absorbent granules to prevent slip & fall injuries.",
            "ai_analysis": json.dumps({
                "urgency_score": 68,
                "confidence": 89,
                "safety_risk": "Slip hazard & machine downtime",
                "suggested_technician": "Instrumentation Engineer",
                "estimated_time": "2 - 3 Hours"
            }),
            "resolution_notes": "",
            "created_at": (now - timedelta(hours=5)).strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": (now - timedelta(hours=5)).strftime("%Y-%m-%d %H:%M:%S"),
            "resolved_at": ""
        },
        {
            "equipment": "RO Purifier & Water Dispenser",
            "location": "Hostel Block B, 1st Floor Common Area",
            "description": "Main dispense tap broken off, continuous clean drinking water overflow into hallway.",
            "priority": "Medium",
            "category": "Plumbing & Sanitation",
            "status": "Resolved",
            "reporter_name": "P. Divya (Hostel Warden)",
            "reporter_contact": "94431 88721",
            "assigned_to": "M. Selvam",
            "safety_alert": "",
            "ai_analysis": json.dumps({
                "urgency_score": 62,
                "confidence": 91,
                "safety_risk": "Water wastage & localized flooding",
                "suggested_technician": "Plumbing Supervisor",
                "estimated_time": "45 Mins"
            }),
            "resolution_notes": "Replaced brass dispense valve and fitted high-durability push-lever. Water flow restored and leak test passed.",
            "created_at": (now - timedelta(hours=14)).strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": (now - timedelta(hours=11)).strftime("%Y-%m-%d %H:%M:%S"),
            "resolved_at": (now - timedelta(hours=11)).strftime("%Y-%m-%d %H:%M:%S")
        },
        {
            "equipment": "Acoustic Ceiling Fan (Regulator Fault)",
            "location": "Main Academic Block, Lecture Hall LH-12",
            "description": "Fan operates at excessive speed only; wall speed regulator knob jammed and sparking occasionally.",
            "priority": "Low",
            "category": "Electrical",
            "status": "Resolved",
            "reporter_name": "Prof. T. Rajan",
            "reporter_contact": "rajan@gct.ac.in",
            "assigned_to": "R. Ramesh",
            "safety_alert": "",
            "ai_analysis": json.dumps({
                "urgency_score": 42,
                "confidence": 95,
                "safety_risk": "Minor noise distraction",
                "suggested_technician": "Campus Electrician",
                "estimated_time": "30 Mins"
            }),
            "resolution_notes": "Replaced stepped electronic regulator unit and tightened mounting screws. All 5 speed steps verified.",
            "created_at": (now - timedelta(days=1, hours=2)).strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": (now - timedelta(hours=18)).strftime("%Y-%m-%d %H:%M:%S"),
            "resolved_at": (now - timedelta(hours=18)).strftime("%Y-%m-%d %H:%M:%S")
        }
    ]

    for s in samples:
        db.execute(
            """INSERT INTO reports (
                equipment, location, description, priority, category, status,
                reporter_name, reporter_contact, assigned_to, image_data,
                safety_alert, ai_analysis, resolution_notes, created_at, updated_at, resolved_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                s["equipment"], s["location"], s["description"], s["priority"], s["category"], s["status"],
                s["reporter_name"], s["reporter_contact"], s["assigned_to"], "",
                s["safety_alert"], s["ai_analysis"], s["resolution_notes"], s["created_at"], s["updated_at"], s["resolved_at"]
            )
        )
    db.commit()


init_db()


# ---------- AI TRIAGE & KEYWORD-BASED PRIORITY NLP ENGINE ----------
CRITICAL_KEYWORDS = [
    "spark", "sparks", "fire", "smoke", "shock", "shocks", "burn", "burning",
    "explosion", "gas leak", "acid", "toxic", "poison", "high voltage",
    "collapse", "short circuit", "electrocute", "flame", "burst"
]

HIGH_KEYWORDS = [
    "leak", "leaking", "dripping", "server", "overheating", "exam", "guest lecture",
    "seminar", "fume hood", "jammed", "blackout", "no power", "flooding",
    "unusable", "shaking", "vibrat", "rupture"
]

MEDIUM_KEYWORDS = [
    "noise", "noisy", "slow", "blinking", "loose", "rattle", "dim", "stuck", "flicker", "flickering"
]

LOW_KEYWORDS = [
    "scratch", "paint", "squeak", "squeaky", "minor", "dirty", "cosmetic", "knob", "stain"
]


def ai_triage_fault(equipment: str, location: str, description: str):
    """
    Intelligent Keyword-Based & Semantic NLP Triage Engine.
    Detects critical keywords, hazard patterns, department classification,
    and returns matched keyword tokens with confidence ratings.
    """
    text = f"{equipment} {location} {description}".lower()

    # Extract exact matched keywords
    matched_crit = [k for k in CRITICAL_KEYWORDS if re.search(r'\b' + re.escape(k), text)]
    matched_high = [k for k in HIGH_KEYWORDS if re.search(r'\b' + re.escape(k), text)]
    matched_med = [k for k in MEDIUM_KEYWORDS if re.search(r'\b' + re.escape(k), text)]
    matched_low = [k for k in LOW_KEYWORDS if re.search(r'\b' + re.escape(k), text)]

    # Category matching scores
    cat_scores = {c: 0 for c in CATEGORIES}
    if any(k in text for k in ["fan", "light", "mcb", "fuse", "wire", "switch", "board", "power", "socket", "plug", "spark", "current", "voltage", "breaker", "generator"]):
        cat_scores["Electrical"] += 3
    if any(k in text for k in ["ac", "air condition", "cooling", "chiller", "compressor", "vent", "duct", "exhaust fan", "thermostat"]):
        cat_scores["HVAC & Cooling"] += 3
    if any(k in text for k in ["projector", "screen", "mic", "microphone", "speaker", "audio", "hdmi", "display", "tv", "monitor", "pc", "computer", "wifi", "router", "lan", "cable", "smartboard"]):
        cat_scores["Audio/Visual & IT"] += 3
    if any(k in text for k in ["lab", "microscope", "fume hood", "spectro", "autoclave", "centrifuge", "furnace", "burner", "lathe", "cnc", "test bench", "hydraulic", "oscilloscope", "chemical"]):
        cat_scores["Laboratory Equipment"] += 3
    if any(k in text for k in ["tap", "pipe", "water", "leak", "flush", "sink", "restroom", "toilet", "drain", "sewage", "purifier", "ro ", "dispenser", "pump"]):
        cat_scores["Plumbing & Sanitation"] += 3
    if any(k in text for k in ["door", "window", "lock", "bench", "desk", "chair", "wall", "ceiling", "tile", "crack", "roof", "railing", "stairs"]):
        cat_scores["Civil & Structural"] += 3

    best_cat = max(cat_scores, key=cat_scores.get)
    if cat_scores[best_cat] == 0:
        best_cat = "General Maintenance"

    # Priority determination based on matched keyword triggers
    safety_alert = ""
    keyword_reason = ""

    if matched_crit:
        priority = "Critical"
        urgency_score = 95
        confidence = 98
        keyword_reason = f"Critical hazard keyword(s) detected: [{', '.join(matched_crit)}]. High risk to personnel and equipment."
        if any(k in ["spark", "sparks", "shock", "shocks", "short circuit"] for k in matched_crit):
            safety_alert = "⚡ HIGH ELECTRICAL HAZARD: Immediately isolate circuit breaker and avoid touching enclosure."
        elif any(k in ["fire", "smoke", "flame", "burn", "burning"] for k in matched_crit):
            safety_alert = "🔥 FIRE EMERGENCE RISK: Activate alarm, isolate flammable materials, keep CO2 extinguisher ready."
        elif any(k in ["acid", "gas leak", "toxic", "poison"] for k in matched_crit):
            safety_alert = "⚠️ TOXIC FUMES: Evacuate room immediately and alert department safety coordinator."
        else:
            safety_alert = "⚠️ ACUTE HAZARD: Cordon off area immediately until technician dispatch."
    elif matched_high:
        priority = "High"
        urgency_score = 80
        confidence = 92
        keyword_reason = f"High priority keyword(s) detected: [{', '.join(matched_high)}]. Potential academic or critical infrastructure disruption."
        if "leak" in matched_high or "leaking" in matched_high:
            if any(k in text for k in ["server", "pc", "switch", "electronics"]):
                safety_alert = "⚠️ WATER INGRESS RISK: Power off susceptible electronics immediately to prevent permanent damage."
    elif matched_med:
        priority = "Medium"
        urgency_score = 55
        confidence = 88
        keyword_reason = f"Standard operational wear keyword(s) detected: [{', '.join(matched_med)}]."
    elif matched_low:
        priority = "Low"
        urgency_score = 30
        confidence = 85
        keyword_reason = f"Minor/cosmetic keyword(s) detected: [{', '.join(matched_low)}]."
    else:
        priority = "Medium"
        urgency_score = 50
        confidence = 75
        keyword_reason = "Standard baseline priority assigned. No severe hazard keywords detected."

    # Tech assignment mapping
    tech_map = {
        "Electrical": ("R. Ramesh", "Chief Electrician"),
        "HVAC & Cooling": ("S. Murugan", "HVAC Specialist"),
        "Audio/Visual & IT": ("P. Karthik", "AV/IT Systems Engineer"),
        "Laboratory Equipment": ("Dr. V. Deepa", "Lab Equipment In-charge"),
        "Plumbing & Sanitation": ("M. Selvam", "Plumbing Supervisor"),
        "Civil & Structural": ("A. Anbarasan", "Civil Works Overseer"),
        "General Maintenance": ("Duty Supervisor", "Campus Maintenance Team")
    }
    sug_tech, sug_role = tech_map.get(best_cat, ("Duty Supervisor", "Campus Maintenance Team"))

    time_map = {
        "Critical": "30 - 60 Minutes (Urgent Dispatch)",
        "High": "1 - 2 Hours",
        "Medium": "2 - 4 Hours",
        "Low": "Same Day (Within 24 Hours)"
    }

    return {
        "priority": priority,
        "category": best_cat,
        "safety_alert": safety_alert,
        "urgency_score": urgency_score,
        "confidence": confidence,
        "suggested_technician": sug_tech,
        "suggested_role": sug_role,
        "estimated_time": time_map.get(priority, "2 Hours"),
        "matched_keywords": {
            "critical": matched_crit,
            "high": matched_high,
            "medium": matched_med,
            "low": matched_low
        },
        "keyword_reason": keyword_reason
    }


def ai_generate_diagnostic_plan(report):
    """
    AI Diagnostic Copilot: Generates root causes, tools needed, and technician checklist.
    """
    cat = report["category"]
    pri = report["priority"]

    if cat == "Electrical":
        root_causes = [
            "Overloaded sub-circuit or worn-out insulation on phase conductor",
            "Faulty contactor/relay causing arcing under inductive load",
            "Loose terminal block screw generating high contact resistance"
        ]
        tools = ["Digital Multimeter / Clamp Meter", "Insulated Screwdrivers (1000V rated)", "Thermal Imager or IR Thermometer", "Replacement MCB / Fuse Link"]
        steps = [
            "De-energize circuit at upstream breaker and lockout/tagout (LOTO)",
            "Measure insulation resistance with Megger between Phase-Neutral and Phase-Earth",
            "Inspect wiring for signs of carbonization, overheating, or melting",
            "Tighten all terminal connections to specified torque and test load under monitoring"
        ]
    elif cat == "HVAC & Cooling":
        root_causes = [
            "Blocked condensate drain trap causing tray overflow",
            "Low refrigerant charge (R32/R410A) leading to evaporator coil icing",
            "Clogged air filters causing restricted airflow and blower motor strain"
        ]
        tools = ["Manifold Gauge Set", "Condensate Drain Vacuum / Nitrogen Purge", "Electronic Leak Detector", "Filter Cleaning Wash Kit"]
        steps = [
            "Inspect and flush condensate pan and primary drainage tubing",
            "Check temperature differential across evaporator (target 8°C - 12°C delta)",
            "Verify compressor running amps against nameplate full load amps (FLA)",
            "Replace/clean intake mesh and run 20-minute stability cycle"
        ]
    elif cat == "Audio/Visual & IT":
        root_causes = [
            "Degraded HDMI signal booster or bent connector pins in wall faceplate",
            "Projector thermal shutdown due to clogged exhaust air intake",
            "Resolution/EDID handshake mismatch between laptop source and scaler"
        ]
        tools = ["HDMI Cable Tester & 4K Generator", "Can of Compressed Air / Microfiber cloth", "Universal Remote & Firmware USB", "Replacement High-Speed 18Gbps HDMI Cable"]
        steps = [
            "Blow out intake dust filter and reset lamp/laser hour counter if prompted",
            "Swap source cable with certified high-bandwidth shielded cable",
            "Verify display source handshake at 1080p 60Hz and 4K 60Hz",
            "Test auxiliary audio output jack for grounding hum or impedance mismatch"
        ]
    elif cat == "Laboratory Equipment":
        root_causes = [
            "Mechanical bearing wear or uncalibrated rotational balance",
            "Heater element failure or faulty thermocouple probe sensor",
            "Contamination or chemical deposit restricting exhaust flow"
        ]
        tools = ["Calibration Standard Weights / Reference Meter", "Bearing Puller & Food-grade Synthetic Lubricant", "Oscilloscope / Signal Probe", "Anti-static ESD Mat & Wristband"]
        steps = [
            "Isolate specimen chamber and check for foreign material or chemical crystallization",
            "Verify sensor continuity and zero-point calibration curve",
            "Check motor drive belt tension and rotational shaft run-out",
            "Run automated self-test diagnostics and document log before releasing to faculty"
        ]
    elif cat == "Plumbing & Sanitation":
        root_causes = [
            "Perished rubber diaphragm washer or ceramic disc cartridge crack",
            "High municipal water surge pressure exceeding valve rating",
            "Sediment particulate accumulation in shut-off ball valve"
        ]
        tools = ["Adjustable Pipe Wrench & Basin Wrench", "PTFE Thread Sealant Tape", "Assorted Nitrile O-rings & Washers", "Hex Key Set"]
        steps = [
            "Shut off angle stop isolation valve under the fixture",
            "Disassemble valve cartridge and inspect seating for calcium deposits",
            "Apply fresh PTFE tape clockwise on male threads and replace worn O-ring",
            "Slowly open water supply, bleed air pockets, and test under full static pressure"
        ]
    else:
        root_causes = [
            "Mechanical fatigue or loosened fastening hardware from daily vibration",
            "Alignment misalignment of sliding/hinged parts",
            "Material wear requiring structural reinforcement"
        ]
        tools = ["Cordless Drill & Impact Driver", "Fastener Assortment (M4 - M8)", "Level & Measuring Tape", "Structural Adhesive / Epoxy"]
        steps = [
            "Inspect frame and anchors for stress cracks or displacement",
            "Re-align pivoting joints and replace compromised fasteners with heavy-duty anchors",
            "Apply lubrication on moving surfaces and perform 10-cycle operational check"
        ]

    return {
        "equipment": report["equipment"],
        "location": report["location"],
        "category": cat,
        "priority": pri,
        "root_causes": root_causes,
        "required_tools": tools,
        "troubleshooting_steps": steps,
        "disclaimer": "AI Diagnostic Copilot recommendations must be validated in accordance with college safety protocols."
    }


# ---------- REST API ENDPOINTS ----------
@app.get("/api/reports")
def list_reports():
    status = request.args.get("status")
    priority = request.args.get("priority")
    category = request.args.get("category")
    q = request.args.get("q", "").strip()
    sort_by = request.args.get("sort", "smart")

    sql = "SELECT * FROM reports WHERE 1=1"
    params = []

    if status in STATUSES:
        sql += " AND status = ?"
        params.append(status)
    if priority in PRIORITIES:
        sql += " AND priority = ?"
        params.append(priority)
    if category in CATEGORIES:
        sql += " AND category = ?"
        params.append(category)
    if q:
        sql += " AND (equipment LIKE ? OR location LIKE ? OR description LIKE ? OR reporter_name LIKE ? OR assigned_to LIKE ?)"
        params += [f"%{q}%"] * 5

    if sort_by == "newest":
        sql += " ORDER BY id DESC"
    elif sort_by == "oldest":
        sql += " ORDER BY id ASC"
    else:
        sql += """ ORDER BY
            CASE status WHEN 'Resolved' THEN 1 ELSE 0 END,
            CASE priority 
                WHEN 'Critical' THEN 0 
                WHEN 'High' THEN 1
                WHEN 'Medium' THEN 2 
                ELSE 3 
            END,
            id DESC"""

    rows = get_db().execute(sql, params).fetchall()
    return jsonify([dict(r) for r in rows])


@app.get("/api/reports/<int:report_id>")
def get_report(report_id):
    row = get_db().execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
    if not row:
        return jsonify(error="Report not found"), 404
    return jsonify(dict(row))


@app.post("/api/reports")
def create_report():
    data = request.get_json(silent=True) or {}
    equipment = (data.get("equipment") or "").strip()
    location = (data.get("location") or "").strip()
    description = (data.get("description") or "").strip()
    priority = data.get("priority")
    category = data.get("category")
    reporter_name = (data.get("reporter_name") or "Campus Member").strip()
    reporter_contact = (data.get("reporter_contact") or "").strip()
    image_data = data.get("image_data") or ""

    if not (equipment and location and description):
        return jsonify(error="Equipment name, location, and description are required."), 400

    # Execute Keyword-based AI Triage
    ai_result = ai_triage_fault(equipment, location, description)

    if not priority or priority not in PRIORITIES:
        priority = ai_result["priority"]
    if not category or category not in CATEGORIES:
        category = ai_result["category"]

    safety_alert = ai_result["safety_alert"]
    suggested_tech = ai_result["suggested_technician"]
    ai_analysis_str = json.dumps(ai_result)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db = get_db()
    cur = db.execute(
        """INSERT INTO reports (
            equipment, location, description, priority, category, status,
            reporter_name, reporter_contact, assigned_to, image_data,
            safety_alert, ai_analysis, resolution_notes, created_at, updated_at, resolved_at
        ) VALUES (?, ?, ?, ?, ?, 'Open', ?, ?, ?, ?, ?, ?, '', ?, ?, '')""",
        (
            equipment, location, description, priority, category,
            reporter_name, reporter_contact, suggested_tech, image_data,
            safety_alert, ai_analysis_str, now, now
        ),
    )
    db.commit()
    new_id = cur.lastrowid
    row = db.execute("SELECT * FROM reports WHERE id = ?", (new_id,)).fetchone()
    return jsonify(dict(row)), 201


@app.patch("/api/reports/<int:report_id>")
def update_report(report_id):
    data = request.get_json(silent=True) or {}
    db = get_db()
    row = db.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
    if not row:
        return jsonify(error="Report not found."), 404

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    updates = []
    params = []

    if "status" in data:
        status = data["status"]
        if status not in STATUSES:
            return jsonify(error="Invalid status."), 400
        updates.append("status = ?")
        params.append(status)
        if status == "Resolved":
            updates.append("resolved_at = ?")
            params.append(now)
        elif row["status"] == "Resolved" and status != "Resolved":
            updates.append("resolved_at = ?")
            params.append("")

    if "assigned_to" in data:
        updates.append("assigned_to = ?")
        params.append(data["assigned_to"].strip() or "Unassigned")

    if "priority" in data and data["priority"] in PRIORITIES:
        updates.append("priority = ?")
        params.append(data["priority"])

    if "category" in data and data["category"] in CATEGORIES:
        updates.append("category = ?")
        params.append(data["category"])

    if "resolution_notes" in data:
        updates.append("resolution_notes = ?")
        params.append(data["resolution_notes"].strip())

    if not updates:
        return jsonify(dict(row))

    updates.append("updated_at = ?")
    params.append(now)
    params.append(report_id)

    db.execute(f"UPDATE reports SET {', '.join(updates)} WHERE id = ?", params)
    db.commit()

    updated = db.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
    return jsonify(dict(updated))


@app.delete("/api/reports/<int:report_id>")
def delete_report(report_id):
    db = get_db()
    cur = db.execute("DELETE FROM reports WHERE id = ?", (report_id,))
    db.commit()
    if cur.rowcount == 0:
        return jsonify(error="Report not found."), 404
    return jsonify(ok=True)


@app.get("/api/summary")
def summary():
    db = get_db()
    rows = db.execute("SELECT status, COUNT(*) AS n FROM reports GROUP BY status").fetchall()
    counts = {s: 0 for s in STATUSES}
    for r in rows:
        counts[r["status"]] = r["n"]

    total = sum(counts.values())
    pending = counts["Open"] + counts["In Progress"]
    resolved = counts["Resolved"]
    resolution_rate = round((resolved / total * 100), 1) if total > 0 else 0

    crit = db.execute(
        "SELECT COUNT(*) FROM reports WHERE priority = 'Critical' AND status != 'Resolved'"
    ).fetchone()[0]

    high_pending = db.execute(
        "SELECT COUNT(*) FROM reports WHERE priority = 'High' AND status != 'Resolved'"
    ).fetchone()[0]

    # Category breakdown
    cat_rows = db.execute("SELECT category, COUNT(*) as n FROM reports GROUP BY category").fetchall()
    cat_breakdown = {r["category"]: r["n"] for r in cat_rows}

    # Location breakdown for Chart.js
    loc_rows = db.execute(
        "SELECT location, COUNT(*) as n FROM reports GROUP BY location ORDER BY n DESC LIMIT 6"
    ).fetchall()
    loc_breakdown = [{"location": r["location"], "count": r["n"]} for r in loc_rows]

    # Priority breakdown
    pri_rows = db.execute(
        "SELECT priority, COUNT(*) as n FROM reports GROUP BY priority"
    ).fetchall()
    pri_breakdown = {r["priority"]: r["n"] for r in pri_rows}

    return jsonify(
        total=total,
        open=counts["Open"],
        in_progress=counts["In Progress"],
        resolved=resolved,
        pending=pending,
        urgent_pending=crit + high_pending,
        critical_count=crit,
        resolution_rate=resolution_rate,
        categories=cat_breakdown,
        locations=loc_breakdown,
        priorities=pri_breakdown,
        technicians=TECHNICIANS
    )


@app.post("/api/ai/triage")
def triage_preview():
    data = request.get_json(silent=True) or {}
    equipment = (data.get("equipment") or "").strip()
    location = (data.get("location") or "").strip()
    description = (data.get("description") or "").strip()

    result = ai_triage_fault(equipment, location, description)
    return jsonify(result)


@app.get("/api/ai/diagnose/<int:report_id>")
def diagnose_report(report_id):
    row = get_db().execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
    if not row:
        return jsonify(error="Report not found."), 404
    plan = ai_generate_diagnostic_plan(dict(row))
    return jsonify(plan)


@app.post("/api/seed")
def seed_endpoint():
    db = get_db()
    db.execute("DELETE FROM reports")
    seed_campus_data(db)
    return jsonify(ok=True, message="Fresh GCT Campus dataset seeded successfully.")


@app.get("/api/export")
def export_csv():
    rows = get_db().execute("SELECT * FROM reports ORDER BY id ASC").fetchall()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ID", "Equipment", "Location", "Category", "Priority", "Status",
        "Reporter", "Contact", "Assigned Technician", "Safety Alert",
        "Resolution Notes", "Created At", "Resolved At"
    ])
    for r in rows:
        writer.writerow([
            r["id"], r["equipment"], r["location"], r["category"], r["priority"], r["status"],
            r["reporter_name"], r["reporter_contact"], r["assigned_to"], r["safety_alert"],
            r["resolution_notes"], r["created_at"], r["resolved_at"]
        ])
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename=FixFlow_Campus_Reports_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"}
    )


# ---------- MODERN HIGH-AESTHETIC FRONTEND ----------
PAGE = """<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>FixFlow — Smart Fault Reporting & Resolution System | GCT Hackathon</title>
  
  <!-- Modern Typography Fonts -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700;800&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
  
  <!-- Tailwind CSS Framework -->
  <script src="https://cdn.tailwindcss.com"></script>
  
  <!-- Chart.js for Status Doughnut & Location Analytics -->
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>

  <!-- Lucide Icons -->
  <script src="https://unpkg.com/lucide@latest"></script>

  <script>
    tailwind.config = {
      darkMode: 'class',
      theme: {
        extend: {
          fontFamily: {
            sans: ['"Plus Jakarta Sans"', 'sans-serif'],
            display: ['"Outfit"', 'sans-serif'],
          },
          colors: {
            brand: {
              400: '#22d3ee',
              500: '#06b6d4',
              600: '#0891b2',
            }
          }
        }
      }
    }
  </script>

  <style>
    body {
      font-family: 'Plus Jakarta Sans', sans-serif;
    }
    .font-display {
      font-family: 'Outfit', sans-serif;
    }
    /* Ambient glow */
    .ambient-glow {
      position: fixed;
      top: -180px;
      left: 15%;
      width: 550px;
      height: 550px;
      background: radial-gradient(circle, rgba(6, 182, 212, 0.12) 0%, rgba(99, 102, 241, 0.05) 50%, transparent 70%);
      pointer-events: none;
      z-index: 0;
    }
    .ambient-glow-2 {
      position: fixed;
      bottom: -150px;
      right: 10%;
      width: 500px;
      height: 500px;
      background: radial-gradient(circle, rgba(244, 63, 94, 0.08) 0%, rgba(245, 158, 11, 0.05) 50%, transparent 70%);
      pointer-events: none;
      z-index: 0;
    }
    /* Pulse animations for urgent items */
    @keyframes pulse-ring {
      0% { transform: scale(0.96); opacity: 0.8; }
      50% { transform: scale(1.06); opacity: 1; }
      100% { transform: scale(0.96); opacity: 0.8; }
    }
    .pulse-danger {
      animation: pulse-ring 2s infinite ease-in-out;
    }
    /* Drag and Drop visual styles */
    .kanban-drop-zone.drag-over {
      background-color: rgba(6, 182, 212, 0.08) !important;
      border-color: rgba(6, 182, 212, 0.6) !important;
      box-shadow: 0 0 25px rgba(6, 182, 212, 0.2);
    }
    .kanban-card.dragging {
      opacity: 0.45;
      transform: scale(0.97);
      cursor: grabbing;
    }
    /* Toast slide animation */
    @keyframes slideInRight {
      from { transform: translateX(110%); opacity: 0; }
      to { transform: translateX(0); opacity: 1; }
    }
    .toast-anim {
      animation: slideInRight 0.3s cubic-bezier(0.16, 1, 0.3, 1) forwards;
    }
    /* Custom scrollbars */
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: rgba(15, 23, 42, 0.5); }
    ::-webkit-scrollbar-thumb { background: rgba(100, 116, 139, 0.5); border-radius: 9999px; }
    ::-webkit-scrollbar-thumb:hover { background: rgba(6, 182, 212, 0.7); }
  </style>
</head>

<body class="bg-[#090d16] text-slate-100 min-h-screen selection:bg-cyan-500 selection:text-black relative antialiased transition-colors duration-200">
  <div class="ambient-glow"></div>
  <div class="ambient-glow-2"></div>

  <!-- TOAST NOTIFICATION CONTAINER (TOP-RIGHT) -->
  <div id="toastContainer" class="fixed top-5 right-5 z-50 flex flex-col gap-2.5 max-w-sm pointer-events-none"></div>

  <!-- MAIN APP CONTAINER -->
  <div class="relative z-10 flex flex-col min-h-screen">

    <!-- TOP NAVIGATION BAR -->
    <header class="border-b border-slate-800/80 bg-slate-900/80 backdrop-blur-md sticky top-0 z-40">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 py-3 flex items-center justify-between gap-4">
        
        <!-- Brand Logo & Badge -->
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-cyan-500 via-blue-600 to-indigo-600 p-[1.5px] shadow-lg shadow-cyan-500/20">
            <div class="w-full h-full bg-slate-950 rounded-[10px] flex items-center justify-center">
              <i data-lucide="zap" class="w-5 h-5 text-cyan-400"></i>
            </div>
          </div>
          <div>
            <div class="flex items-center gap-2">
              <h1 class="font-display font-extrabold text-2xl tracking-tight bg-gradient-to-r from-white via-cyan-100 to-cyan-400 bg-clip-text text-transparent">
                Fix<span class="text-cyan-400">Flow</span>
              </h1>
              <span class="px-2 py-0.5 text-[10px] font-bold rounded-full bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 uppercase tracking-widest flex items-center gap-1">
                <i data-lucide="sparkles" class="w-2.5 h-2.5"></i> AI Triage
              </span>
            </div>
            <p class="text-xs text-slate-400 font-medium">Smart Fault Reporting &amp; Resolution System &bull; <span class="text-cyan-300 font-semibold">Coding Club GCT</span></p>
          </div>
        </div>

        <!-- Role Switcher & Action Controls -->
        <div class="flex items-center gap-2 sm:gap-3">
          
          <!-- ROLE TOGGLE: Reporter vs Maintenance Team -->
          <div class="bg-slate-950 p-1 rounded-xl border border-slate-700/80 flex items-center text-xs font-semibold shadow-inner">
            <button id="btnRoleReporter" onclick="setRole('reporter')" class="px-3 py-1.5 rounded-lg text-slate-400 hover:text-white transition flex items-center gap-1.5">
              <i data-lucide="user-edit" class="w-3.5 h-3.5"></i>
              <span>Reporter Portal</span>
            </button>
            <button id="btnRoleMaintenance" onclick="setRole('maintenance')" class="px-3 py-1.5 rounded-lg bg-cyan-500 text-slate-950 font-bold shadow-md transition flex items-center gap-1.5">
              <i data-lucide="shield-alert" class="w-3.5 h-3.5"></i>
              <span>Maintenance Hub</span>
            </button>
          </div>

          <!-- Seed Demo Data Button -->
          <button onclick="seedData()" title="Reload GCT Campus Sample Data" class="px-2.5 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-750 text-xs font-semibold text-cyan-300 border border-slate-700 hover:border-cyan-500/50 transition flex items-center gap-1.5 shadow-sm">
            <i data-lucide="refresh-cw" class="w-3.5 h-3.5"></i>
            <span class="hidden md:inline">Demo Data</span>
          </button>

          <!-- Export CSV Button -->
          <a href="/api/export" onclick="showToast('Exporting Data', 'Downloading maintenance CSV...', 'info')" title="Export Maintenance Logs to CSV" class="px-2.5 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-750 text-xs font-semibold text-slate-200 border border-slate-700 transition flex items-center gap-1.5 shadow-sm">
            <i data-lucide="download" class="w-3.5 h-3.5 text-emerald-400"></i>
            <span class="hidden md:inline">Export</span>
          </a>

        </div>

      </div>
    </header>


    <!-- ============================================ -->
    <!-- VIEW A: MAINTENANCE HUB (ADMIN / TECHNICIANS) -->
    <!-- ============================================ -->
    <div id="maintenanceView" class="space-y-6">

      <!-- 1. KPI SUMMARY STRIP -->
      <section class="max-w-7xl mx-auto px-4 sm:px-6 pt-5 w-full">
        <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3" id="statsGrid">
          <!-- Populated dynamically via loadSummary() -->
        </div>
      </section>

      <!-- 2. ANALYTICS CHARTS SECTION (Status Doughnut + Issues Per Location) -->
      <section class="max-w-7xl mx-auto px-4 sm:px-6 w-full">
        <div class="grid md:grid-cols-12 gap-4">
          
          <!-- Status Doughnut Chart -->
          <div class="md:col-span-5 bg-slate-900/90 rounded-2xl border border-slate-800 p-4 shadow-xl backdrop-blur-md">
            <div class="flex items-center justify-between pb-3 border-b border-slate-800/80 mb-2">
              <div class="flex items-center gap-2">
                <i data-lucide="pie-chart" class="w-4 h-4 text-cyan-400"></i>
                <h3 class="font-display font-bold text-xs uppercase tracking-wider text-slate-200">Incident Resolution Status</h3>
              </div>
              <span id="chartResolutionRate" class="text-xs font-mono font-bold text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/20">--% Rate</span>
            </div>
            <div class="relative h-48 flex items-center justify-center">
              <canvas id="statusDoughnutChart"></canvas>
            </div>
          </div>

          <!-- Issues Per Location Bar Chart -->
          <div class="md:col-span-7 bg-slate-900/90 rounded-2xl border border-slate-800 p-4 shadow-xl backdrop-blur-md">
            <div class="flex items-center justify-between pb-3 border-b border-slate-800/80 mb-2">
              <div class="flex items-center gap-2">
                <i data-lucide="bar-chart-3" class="w-4 h-4 text-cyan-400"></i>
                <h3 class="font-display font-bold text-xs uppercase tracking-wider text-slate-200">Top Fault Hotspots (By Location)</h3>
              </div>
              <span class="text-[11px] text-slate-400">Active Campus Zones</span>
            </div>
            <div class="relative h-48">
              <canvas id="locationBarChart"></canvas>
            </div>
          </div>

        </div>
      </section>

      <!-- 3. KANBAN WORKSPACE WITH DRAG & DROP -->
      <main class="max-w-7xl mx-auto px-4 sm:px-6 pb-8 w-full space-y-4">
        
        <!-- Controls Bar -->
        <div class="bg-slate-900/90 rounded-2xl border border-slate-800 p-3.5 shadow-xl backdrop-blur-md flex flex-wrap gap-2.5 items-center justify-between">
          
          <!-- Search -->
          <div class="relative flex-1 min-w-[200px]">
            <i data-lucide="search" class="w-4 h-4 text-slate-400 absolute left-3 top-2.5"></i>
            <input id="qSearch" placeholder="Search equipment, room, or issue..."
                   class="w-full bg-slate-950 border border-slate-800 rounded-xl pl-9 pr-3 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500">
          </div>

          <!-- Quick Filters -->
          <div class="flex flex-wrap items-center gap-2">
            <select id="filterPriority" class="bg-slate-950 border border-slate-800 rounded-xl px-2.5 py-1.5 text-xs text-slate-300">
              <option value="">All Priorities</option>
              <option value="Critical">🚨 Critical</option>
              <option value="High">⚠️ High</option>
              <option value="Medium">⚡ Medium</option>
              <option value="Low">💤 Low</option>
            </select>

            <select id="filterCategory" class="bg-slate-950 border border-slate-800 rounded-xl px-2.5 py-1.5 text-xs text-slate-300">
              <option value="">All Departments</option>
              <option value="Electrical">Electrical</option>
              <option value="HVAC &amp; Cooling">HVAC</option>
              <option value="Audio/Visual &amp; IT">AV / IT</option>
              <option value="Laboratory Equipment">Lab</option>
              <option value="Plumbing &amp; Sanitation">Plumbing</option>
              <option value="Civil &amp; Structural">Civil</option>
            </select>

            <!-- View Mode Switch: Kanban vs List -->
            <div class="bg-slate-950 p-0.5 rounded-xl border border-slate-800 flex items-center text-xs font-semibold">
              <button id="btnViewKanban" onclick="setViewMode('kanban')" class="px-2.5 py-1 rounded-lg bg-slate-800 text-cyan-400 flex items-center gap-1">
                <i data-lucide="columns-3" class="w-3.5 h-3.5"></i>
                <span>Kanban</span>
              </button>
              <button id="btnViewList" onclick="setViewMode('cards')" class="px-2.5 py-1 rounded-lg text-slate-400 hover:text-white flex items-center gap-1">
                <i data-lucide="list" class="w-3.5 h-3.5"></i>
                <span>List</span>
              </button>
            </div>
          </div>

        </div>

        <!-- KANBAN BOARD CONTAINER (WITH DRAG & DROP) -->
        <div id="kanbanBoardContainer">
          <!-- Injected via renderKanbanBoard() -->
        </div>

      </main>

    </div>


    <!-- ============================================ -->
    <!-- VIEW B: REPORTER PORTAL (STUDENTS & FACULTY) -->
    <!-- ============================================ -->
    <div id="reporterView" class="hidden max-w-7xl mx-auto px-4 sm:px-6 py-6 w-full space-y-6">
      
      <div class="grid lg:grid-cols-12 gap-6 items-start">
        
        <!-- Left Column: Fault Submission Form with Keyword-based AI Suggestion -->
        <div class="lg:col-span-6 bg-slate-900/90 rounded-2xl border border-slate-800 p-5 sm:p-6 shadow-2xl backdrop-blur-md space-y-4">
          
          <div class="flex items-center justify-between pb-3 border-b border-slate-800">
            <div>
              <h2 class="font-display font-bold text-lg text-white flex items-center gap-2">
                <i data-lucide="send" class="w-5 h-5 text-cyan-400"></i>
                <span>Submit Equipment Fault Report</span>
              </h2>
              <p class="text-xs text-slate-400 mt-0.5">Quick campus breakdown logging with real-time AI triage</p>
            </div>
            <span class="text-[10px] font-mono px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 font-bold">STUDENT &amp; STAFF</span>
          </div>

          <!-- Quick Scenario Templates for Testing -->
          <div>
            <p class="text-[11px] font-semibold text-slate-400 mb-1.5 flex items-center gap-1">
              <i data-lucide="zap" class="w-3 h-3 text-amber-400"></i> Fast Fill Templates:
            </p>
            <div class="flex flex-wrap gap-1.5">
              <button type="button" onclick="fillQuickDemo(1)" class="text-[11px] px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white border border-slate-700 transition">
                ⚡ Lab MCB Sparking
              </button>
              <button type="button" onclick="fillQuickDemo(2)" class="text-[11px] px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white border border-slate-700 transition">
                📽️ Seminar Projector Overheat
              </button>
              <button type="button" onclick="fillQuickDemo(3)" class="text-[11px] px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white border border-slate-700 transition">
                ❄️ Server Room AC Leak
              </button>
            </div>
          </div>

          <!-- Form Fields -->
          <form id="reporterForm" class="space-y-3.5">
            
            <div>
              <label class="block text-xs font-semibold text-slate-300 mb-1">Equipment Name <span class="text-rose-400">*</span></label>
              <div class="relative">
                <i data-lucide="cpu" class="w-4 h-4 text-slate-500 absolute left-3 top-2.5"></i>
                <input id="rEquipment" required placeholder="e.g. Ceiling Fan, Epson Projector, Oscilloscope, Tap"
                       class="w-full bg-slate-950 border border-slate-800 rounded-xl pl-9 pr-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500">
              </div>
            </div>

            <div>
              <label class="block text-xs font-semibold text-slate-300 mb-1">Location / Classroom / Lab <span class="text-rose-400">*</span></label>
              <div class="relative">
                <i data-lucide="map-pin" class="w-4 h-4 text-slate-500 absolute left-3 top-2.5"></i>
                <input id="rLocation" required placeholder="e.g. Chemistry Block Lab 204, Library 2nd Floor, LH-14"
                       class="w-full bg-slate-950 border border-slate-800 rounded-xl pl-9 pr-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500">
              </div>
            </div>

            <div>
              <div class="flex items-center justify-between mb-1">
                <label class="text-xs font-semibold text-slate-300">Problem Description <span class="text-rose-400">*</span></label>
                <button type="button" id="btnVoiceInput" onclick="toggleVoiceDictation()" class="text-[11px] text-cyan-400 hover:text-cyan-300 flex items-center gap-1 bg-cyan-500/10 px-2 py-0.5 rounded border border-cyan-500/20">
                  <i data-lucide="mic" class="w-3 h-3"></i>
                  <span id="voiceStatusText">Voice Input</span>
                </button>
              </div>
              <textarea id="rDescription" required rows="3" placeholder="Describe the failure, strange noises, sparks, smoke, or leaks..."
                        class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500"></textarea>
            </div>

            <!-- KEYWORD-BASED AI PRIORITY SUGGESTION RADAR -->
            <div id="keywordAiRadar" class="bg-gradient-to-br from-cyan-950/40 via-slate-900 to-indigo-950/40 border border-cyan-500/30 rounded-xl p-3.5 space-y-2">
              <div class="flex items-center justify-between">
                <span class="text-xs font-bold text-cyan-300 flex items-center gap-1.5">
                  <i data-lucide="sparkles" class="w-3.5 h-3.5 text-cyan-400"></i>
                  AI Keyword Radar &amp; Priority Suggestion
                </span>
                <span id="aiConfidenceBadge" class="text-[10px] font-mono bg-cyan-500/20 text-cyan-300 px-2 py-0.5 rounded-full border border-cyan-500/30">
                  Real-time Active
                </span>
              </div>

              <!-- Matched Keywords Badges -->
              <div class="flex items-center gap-1.5 flex-wrap min-h-[22px]">
                <span class="text-[10px] text-slate-400">Detected Keywords:</span>
                <div id="keywordPillsContainer" class="flex flex-wrap gap-1">
                  <span class="text-[10px] text-slate-500 italic">Type description above to extract signals...</span>
                </div>
              </div>

              <!-- AI Priority & Reason -->
              <div class="grid grid-cols-2 gap-2 text-xs pt-1">
                <div class="bg-slate-950/70 p-2 rounded-lg border border-slate-800">
                  <span class="text-[10px] text-slate-400 block">Suggested Priority</span>
                  <div class="flex items-center gap-1.5 mt-0.5">
                    <span id="rAiSugPriority" class="font-bold text-amber-400 text-sm">Medium</span>
                    <span class="text-[9px] text-emerald-400 bg-emerald-500/10 px-1 rounded">&check; Auto-applied</span>
                  </div>
                </div>
                <div class="bg-slate-950/70 p-2 rounded-lg border border-slate-800">
                  <span class="text-[10px] text-slate-400 block">Assigned Specialist</span>
                  <span id="rAiSugTech" class="font-semibold text-slate-200 mt-0.5 block truncate">Campus Tech</span>
                </div>
              </div>

              <!-- Hazard Alert Box if Detected -->
              <div id="rSafetyAlertBox" class="hidden text-xs bg-rose-950/70 text-rose-200 border border-rose-500/40 rounded-lg p-2 font-medium"></div>
            </div>

            <!-- Override & Contact -->
            <div class="grid grid-cols-2 gap-2.5">
              <div>
                <label class="block text-xs font-semibold text-slate-300 mb-1">Priority Selection</label>
                <select id="rPriority" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-2.5 py-1.5 text-xs text-white">
                  <option value="Low">Low</option>
                  <option value="Medium" selected>Medium</option>
                  <option value="High">High</option>
                  <option value="Critical">Critical</option>
                </select>
              </div>

              <div>
                <label class="block text-xs font-semibold text-slate-300 mb-1">Your Name / ID</label>
                <input id="rReporterName" placeholder="e.g. Arun (Student) / Prof. S. Meena"
                       class="w-full bg-slate-950 border border-slate-800 rounded-xl px-2.5 py-1.5 text-xs text-white placeholder-slate-500">
              </div>
            </div>

            <button type="submit" id="btnReporterSubmit" class="w-full bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-slate-950 font-bold py-2.5 rounded-xl text-xs shadow-lg shadow-cyan-500/20 transition flex items-center justify-center gap-1.5">
              <i data-lucide="check" class="w-4 h-4"></i>
              <span>Submit Fault Report</span>
            </button>

          </form>

        </div>

        <!-- Right Column: My Campus Reports & Status Stepper Timeline -->
        <div class="lg:col-span-6 space-y-4">
          <div class="bg-slate-900/90 rounded-2xl border border-slate-800 p-5 shadow-2xl backdrop-blur-md">
            
            <div class="flex items-center justify-between pb-3 border-b border-slate-800 mb-3">
              <div class="flex items-center gap-2">
                <i data-lucide="activity" class="w-4 h-4 text-cyan-400"></i>
                <h3 class="font-display font-bold text-sm text-white">Campus Live Fault Resolution Tracker</h3>
              </div>
              <span class="text-xs text-slate-400 font-mono">Live Timeline</span>
            </div>

            <p class="text-xs text-slate-400 mb-3">
              Track the resolution lifecycle of reported college equipment from submission through to technician sign-off.
            </p>

            <div id="reporterTrackerList" class="space-y-3 max-h-[600px] overflow-y-auto pr-1">
              <!-- Injected via renderReporterTracker() -->
            </div>

          </div>
        </div>

      </div>

    </div>


    <!-- FOOTER -->
    <footer class="mt-auto border-t border-slate-800/80 bg-slate-950/80 py-4 px-4 text-center text-xs text-slate-500">
      <div class="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-2">
        <p>FixFlow — Engineered for <strong>Coding Club GCT &bull; AI Web Development Hackathon</strong></p>
        <p class="text-slate-400">Drag &amp; Drop Kanban &bull; Status Charts &bull; Keyword AI Triage &bull; Real-time Sync</p>
      </div>
    </footer>

  </div>


  <!-- ============================================ -->
  <!-- MODAL: AI DIAGNOSTIC COPILOT (FOR TECHNICIANS) -->
  <!-- ============================================ -->
  <div id="diagnoseModal" class="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm hidden flex items-center justify-center p-4">
    <div class="bg-slate-900 border border-slate-700 rounded-2xl max-w-xl w-full p-6 shadow-2xl space-y-4 max-h-[90vh] overflow-y-auto">
      <div class="flex items-center justify-between border-b border-slate-800 pb-3">
        <div class="flex items-center gap-2">
          <div class="p-2 rounded-lg bg-cyan-500/10 text-cyan-400 border border-cyan-500/30">
            <i data-lucide="wrench" class="w-5 h-5"></i>
          </div>
          <div>
            <h3 class="font-display font-bold text-base text-white">AI Diagnostic &amp; Resolution Copilot</h3>
            <p class="text-xs text-slate-400" id="diagSubTitle">Automated root-cause analysis &amp; repair checklist</p>
          </div>
        </div>
        <button onclick="closeDiagnoseModal()" class="text-slate-400 hover:text-white p-1 rounded-lg">
          <i data-lucide="x" class="w-5 h-5"></i>
        </button>
      </div>

      <div id="diagContent" class="space-y-4 text-xs">
        <!-- Injected dynamically -->
      </div>

      <div class="pt-2 border-t border-slate-800 flex justify-end">
        <button onclick="closeDiagnoseModal()" class="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-xl text-xs font-semibold">
          Close Copilot
        </button>
      </div>
    </div>
  </div>


  <!-- ============================================ -->
  <!-- MODAL: RESOLUTION LOGGING -->
  <!-- ============================================ -->
  <div id="resolveModal" class="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm hidden flex items-center justify-center p-4">
    <div class="bg-slate-900 border border-slate-700 rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
      <div class="flex items-center justify-between border-b border-slate-800 pb-3">
        <div class="flex items-center gap-2">
          <div class="p-2 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
            <i data-lucide="check-circle-2" class="w-5 h-5"></i>
          </div>
          <div>
            <h3 class="font-display font-bold text-base text-white">Mark Fault as Resolved</h3>
            <p class="text-xs text-slate-400" id="resEquipmentTitle">Equipment Fix Record</p>
          </div>
        </div>
        <button onclick="closeResolveModal()" class="text-slate-400 hover:text-white p-1 rounded-lg">
          <i data-lucide="x" class="w-5 h-5"></i>
        </button>
      </div>

      <div class="space-y-3">
        <input type="hidden" id="resReportId">
        <div>
          <label class="block text-xs font-semibold text-slate-300 mb-1">Assigned Technician</label>
          <select id="resTechnician" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white">
            <!-- Injected dynamically -->
          </select>
        </div>

        <div>
          <label class="block text-xs font-semibold text-slate-300 mb-1">Resolution Summary / Replaced Parts</label>
          <textarea id="resNotes" rows="3" placeholder="e.g. Replaced 16A MCB breaker, tightened terminal contacts, tested normal load."
                    class="w-full bg-slate-950 border border-slate-800 rounded-xl p-3 text-xs text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500"></textarea>
        </div>
      </div>

      <div class="pt-2 border-t border-slate-800 flex justify-end gap-2">
        <button onclick="closeResolveModal()" class="px-4 py-2 bg-slate-800 hover:bg-slate-750 text-slate-300 rounded-xl text-xs font-semibold">
          Cancel
        </button>
        <button onclick="submitResolution()" class="px-4 py-2 bg-emerald-500 hover:bg-emerald-400 text-slate-950 rounded-xl text-xs font-bold flex items-center gap-1.5">
          <i data-lucide="check" class="w-4 h-4"></i>
          <span>Save Resolution</span>
        </button>
      </div>
    </div>
  </div>


  <!-- ============================================ -->
  <!-- JAVASCRIPT LOGIC & APPLICATION ENGINE -->
  <!-- ============================================ -->
  <script>
    // State variables
    let currentRole = 'maintenance'; // 'reporter' or 'maintenance'
    let currentView = 'kanban';      // 'kanban' or 'cards'
    let cachedReports = [];
    let cachedSummary = null;
    let draggedReportId = null;
    let triageTimer = null;
    let statusChartInstance = null;
    let locationChartInstance = null;

    const PRIORITY_BADGES = {
      Critical: "bg-rose-500/10 text-rose-400 border-rose-500/30",
      High: "bg-orange-500/10 text-orange-400 border-orange-500/30",
      Medium: "bg-amber-500/10 text-amber-400 border-amber-500/30",
      Low: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
    };

    const STATUS_BORDER = {
      "Open": "border-l-rose-500",
      "In Progress": "border-l-amber-500",
      "Resolved": "border-l-emerald-500"
    };

    const CATEGORY_ICONS = {
      "Electrical": "zap",
      "HVAC & Cooling": "snowflake",
      "Audio/Visual & IT": "video",
      "Laboratory Equipment": "flask-conical",
      "Plumbing & Sanitation": "droplet",
      "Civil & Structural": "building",
      "General Maintenance": "wrench"
    };

    const esc = s => String(s || '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

    // ==========================================
    // 1. TOAST NOTIFICATION SYSTEM
    // ==========================================
    function showToast(title, message, type = 'success') {
      const container = document.getElementById('toastContainer');
      const toast = document.createElement('div');
      
      const icons = {
        success: 'check-circle',
        warning: 'alert-triangle',
        error: 'x-circle',
        info: 'info'
      };

      const colors = {
        success: 'border-emerald-500/40 bg-slate-900/95 text-emerald-300',
        warning: 'border-amber-500/40 bg-slate-900/95 text-amber-300',
        error: 'border-rose-500/40 bg-slate-900/95 text-rose-300',
        info: 'border-cyan-500/40 bg-slate-900/95 text-cyan-300'
      };

      toast.className = `toast-anim pointer-events-auto flex items-start gap-3 p-3.5 rounded-xl border ${colors[type] || colors.info} shadow-2xl backdrop-blur-md`;
      toast.innerHTML = `
        <div class="mt-0.5"><i data-lucide="${icons[type] || 'info'}" class="w-4 h-4"></i></div>
        <div class="flex-1 pr-1">
          <h5 class="text-xs font-bold text-white leading-tight">${esc(title)}</h5>
          <p class="text-[11px] text-slate-300 mt-0.5">${esc(message)}</p>
        </div>
        <button onclick="this.parentElement.remove()" class="text-slate-400 hover:text-white p-0.5">
          <i data-lucide="x" class="w-3.5 h-3.5"></i>
        </button>
      `;

      container.appendChild(toast);
      lucide.createIcons();

      setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.4s ease';
        setTimeout(() => toast.remove(), 400);
      }, 3500);
    }

    // Audio chime feedback
    function playChime(type) {
      try {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain);
        gain.connect(ctx.destination);
        if (type === 'success') {
          osc.frequency.setValueAtTime(523.25, ctx.currentTime);
          osc.frequency.exponentialRampToValueAtTime(659.25, ctx.currentTime + 0.1);
          gain.gain.setValueAtTime(0.12, ctx.currentTime);
          gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.3);
          osc.start();
          osc.stop(ctx.currentTime + 0.3);
        } else if (type === 'alert') {
          osc.frequency.setValueAtTime(440, ctx.currentTime);
          osc.frequency.setValueAtTime(880, ctx.currentTime + 0.15);
          gain.gain.setValueAtTime(0.15, ctx.currentTime);
          gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.3);
          osc.start();
          osc.stop(ctx.currentTime + 0.3);
        }
      } catch (e) {}
    }

    // ==========================================
    // 2. RELATIVE TIMESTAMP FORMATTER
    // ==========================================
    function formatRelativeTime(dateString) {
      if (!dateString) return '';
      const now = new Date();
      const past = new Date(dateString.replace(' ', 'T'));
      const diffSec = Math.floor((now - past) / 1000);

      if (diffSec < 60) return 'Just now';
      const diffMin = Math.floor(diffSec / 60);
      if (diffMin < 60) return `${diffMin}m ago`;
      const diffHr = Math.floor(diffMin / 60);
      if (diffHr < 24) return `${diffHr}h ago`;
      const diffDays = Math.floor(diffHr / 24);
      if (diffDays === 1) return 'Yesterday';
      if (diffDays < 7) return `${diffDays}d ago`;
      return past.toLocaleDateString();
    }


    // ==========================================
    // 3. KPI SUMMARY & CHARTS (STATUS DOUGHNUT & LOCATION BARS)
    // ==========================================
    async function loadSummary() {
      try {
        const res = await fetch('/api/summary');
        const s = await res.json();
        cachedSummary = s;

        // Render KPI Strip
        const cards = [
          { label: 'Total Incidents', value: s.total, icon: 'layers', color: 'text-cyan-400', border: 'hover:border-cyan-500/50' },
          { label: 'Pending Action', value: s.pending, icon: 'clock', color: 'text-amber-400', border: 'hover:border-amber-500/50' },
          { label: 'Open', value: s.open, icon: 'alert-circle', color: 'text-rose-400', border: 'hover:border-rose-500/50' },
          { label: 'In Progress', value: s.in_progress, icon: 'wrench', color: 'text-yellow-400', border: 'hover:border-yellow-500/50' },
          { label: 'Resolved', value: s.resolved, icon: 'check-circle-2', color: 'text-emerald-400', border: 'hover:border-emerald-500/50' },
          { label: 'Critical Risk', value: s.critical_count, icon: 'flame', color: 'text-rose-500', border: 'hover:border-rose-500/80' },
        ];

        document.getElementById('statsGrid').innerHTML = cards.map(c => `
          <div class="bg-slate-900/80 hover:bg-slate-850 border border-slate-800 ${c.border} rounded-2xl p-4 shadow-lg transition-all duration-200 backdrop-blur-md">
            <div class="flex items-center justify-between mb-2">
              <span class="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">${c.label}</span>
              <div class="p-1.5 rounded-lg bg-slate-950/70 ${c.color}">
                <i data-lucide="${c.icon}" class="w-3.5 h-3.5"></i>
              </div>
            </div>
            <div class="flex items-baseline justify-between">
              <p class="font-display text-2xl font-extrabold ${c.color}">${c.value}</p>
              ${c.label === 'Critical Risk' && c.value > 0 ? `<span class="text-[9px] px-1.5 py-0.2 rounded bg-rose-500/20 text-rose-300 font-mono pulse-danger">URGENT</span>` : ''}
              ${c.label === 'Resolved' ? `<span class="text-[10px] text-slate-400 font-mono">${s.resolution_rate}% rate</span>` : ''}
            </div>
          </div>
        `).join('');

        document.getElementById('chartResolutionRate').textContent = `${s.resolution_rate}% Resolved`;

        // Render Analytics Charts
        renderAnalyticsCharts(s);

        // Store technicians for assignment dropdowns
        window.allTechnicians = s.technicians || [];
        populateTechnicianDropdowns();

        lucide.createIcons();
      } catch (err) {
        console.error('Error fetching summary:', err);
      }
    }

    function renderAnalyticsCharts(s) {
      if (typeof Chart === 'undefined') return;

      // 1. Status Doughnut Chart
      const statusCtx = document.getElementById('statusDoughnutChart');
      if (statusCtx) {
        if (statusChartInstance) statusChartInstance.destroy();
        statusChartInstance = new Chart(statusCtx, {
          type: 'doughnut',
          data: {
            labels: ['Open', 'In Progress', 'Resolved'],
            datasets: [{
              data: [s.open, s.in_progress, s.resolved],
              backgroundColor: ['#f43f5e', '#f59e0b', '#10b981'],
              borderColor: '#090d16',
              borderWidth: 3,
              hoverOffset: 6
            }]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '72%',
            plugins: {
              legend: {
                position: 'right',
                labels: {
                  boxWidth: 10,
                  boxHeight: 10,
                  color: '#94a3b8',
                  font: { family: 'Plus Jakarta Sans', size: 11, weight: 600 }
                }
              }
            }
          }
        });
      }

      // 2. Issues Per Location Bar Chart
      const locCtx = document.getElementById('locationBarChart');
      if (locCtx && s.locations) {
        if (locationChartInstance) locationChartInstance.destroy();
        const labels = s.locations.map(l => l.location.split(',')[0]);
        const counts = s.locations.map(l => l.count);

        locationChartInstance = new Chart(locCtx, {
          type: 'bar',
          data: {
            labels: labels,
            datasets: [{
              label: 'Reported Faults',
              data: counts,
              backgroundColor: '#06b6d4',
              borderRadius: 6,
              hoverBackgroundColor: '#22d3ee'
            }]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
              legend: { display: false }
            },
            scales: {
              x: {
                grid: { display: false },
                ticks: { color: '#64748b', font: { size: 10, family: 'Plus Jakarta Sans' } }
              },
              y: {
                beginAtZero: true,
                grid: { color: 'rgba(51, 65, 85, 0.4)' },
                ticks: { precision: 0, color: '#64748b', font: { size: 10 } }
              }
            }
          }
        });
      }
    }

    function populateTechnicianDropdowns() {
      const sel = document.getElementById('resTechnician');
      if (sel && window.allTechnicians) {
        sel.innerHTML = window.allTechnicians.map(t => 
          `<option value="${esc(t.name)}">${esc(t.name)} — ${esc(t.role)} (${esc(t.dept)})</option>`
        ).join('') + `<option value="Campus Technician">Campus Duty Technician</option>`;
      }
    }


    // ==========================================
    // 4. LOAD & RENDER REPORTS (KANBAN DRAG & DROP)
    // ==========================================
    async function loadReports() {
      const q = document.getElementById('qSearch').value.trim();
      const priority = document.getElementById('filterPriority').value;
      const category = document.getElementById('filterCategory').value;

      const p = new URLSearchParams();
      if (q) p.set('q', q);
      if (priority) p.set('priority', priority);
      if (category) p.set('category', category);

      try {
        const res = await fetch('/api/reports?' + p.toString());
        const rows = await res.json();
        cachedReports = rows;

        if (currentView === 'kanban') {
          renderKanbanBoard(rows);
        } else {
          renderCardList(rows);
        }

        renderReporterTracker(rows);
      } catch (err) {
        console.error('Error loading reports:', err);
      }
    }

    // KANBAN BOARD WITH HTML5 DRAG AND DROP
    function renderKanbanBoard(rows) {
      const container = document.getElementById('kanbanBoardContainer');
      const cols = [
        { status: 'Open', title: 'Open / Needs Triage', color: 'text-rose-400', border: 'border-t-rose-500', dropColor: 'hover:border-rose-500/50' },
        { status: 'In Progress', title: 'In Progress / Assigned', color: 'text-amber-400', border: 'border-t-amber-500', dropColor: 'hover:border-amber-500/50' },
        { status: 'Resolved', title: 'Resolved & Closed', color: 'text-emerald-400', border: 'border-t-emerald-500', dropColor: 'hover:border-emerald-500/50' }
      ];

      container.innerHTML = `
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4 items-start">
          ${cols.map(c => {
            const list = rows.filter(r => r.status === c.status);
            return `
              <div class="bg-slate-900/90 rounded-2xl border border-slate-800 ${c.border} border-t-4 p-4 shadow-xl flex flex-col min-h-[480px] kanban-drop-zone transition-all"
                   ondragover="handleDragOver(event)"
                   ondragleave="handleDragLeave(event)"
                   ondrop="handleDrop(event, '${c.status}')">
                
                <div class="flex items-center justify-between pb-3 border-b border-slate-800/80 mb-3">
                  <h4 class="font-display font-bold text-xs uppercase tracking-wider ${c.color} flex items-center gap-1.5">
                    <span>${c.title}</span>
                  </h4>
                  <span class="text-xs font-mono font-bold px-2 py-0.5 rounded-full bg-slate-950 text-slate-300 border border-slate-800">${list.length}</span>
                </div>

                <div class="space-y-3 flex-1 overflow-y-auto max-h-[620px] pr-1">
                  ${list.length === 0 ? `
                    <div class="text-center py-12 text-slate-500 text-xs border border-dashed border-slate-800/80 rounded-xl">
                      <p>Drag items here to move to <strong>${c.status}</strong></p>
                    </div>
                  ` : list.map(r => `
                    <div id="kcard-${r.id}"
                         draggable="true"
                         ondragstart="handleDragStart(event, ${r.id})"
                         ondragend="handleDragEnd(event)"
                         class="kanban-card bg-slate-950/90 rounded-xl p-3.5 border border-slate-800 hover:border-cyan-500/50 shadow-md cursor-grab active:cursor-grabbing transition-all space-y-2.5">
                      
                      <!-- Header: ID, Priority, Relative Time -->
                      <div class="flex items-center justify-between">
                        <span class="text-[10px] font-mono font-bold text-cyan-400">#FF-${r.id}</span>
                        <div class="flex items-center gap-1.5">
                          <span class="text-[10px] font-bold px-1.5 py-0.2 rounded border ${PRIORITY_BADGES[r.priority]}">${r.priority}</span>
                          <span class="text-[10px] text-slate-400" title="${r.created_at}">${formatRelativeTime(r.created_at)}</span>
                        </div>
                      </div>

                      <!-- Title & Location -->
                      <div>
                        <h5 class="font-bold text-xs text-white leading-snug">${esc(r.equipment)}</h5>
                        <p class="text-[11px] text-slate-400 flex items-center gap-1 mt-0.5">
                          <i data-lucide="map-pin" class="w-2.5 h-2.5 text-cyan-400"></i>
                          <span>${esc(r.location)}</span>
                        </p>
                      </div>

                      <!-- Description -->
                      <p class="text-xs text-slate-300 line-clamp-2 leading-relaxed bg-slate-900/60 p-2 rounded-lg border border-slate-850">
                        ${esc(r.description)}
                      </p>

                      <!-- Safety Alert if present -->
                      ${r.safety_alert ? `
                        <div class="text-[10px] bg-rose-950/60 border border-rose-500/30 rounded p-1.5 text-rose-300">
                          ${esc(r.safety_alert)}
                        </div>
                      ` : ''}

                      <!-- Footer Controls -->
                      <div class="pt-2 border-t border-slate-800/80 flex items-center justify-between text-xs">
                        <span class="text-[10px] text-slate-400">
                          Tech: <strong class="text-cyan-300">${esc(r.assigned_to || 'Unassigned')}</strong>
                        </span>
                        
                        <div class="flex items-center gap-1.5">
                          <button onclick="openDiagnoseModal(${r.id})" class="text-[10px] text-cyan-400 hover:text-cyan-300 font-semibold px-1.5 py-0.5 rounded bg-cyan-950/40 border border-cyan-800/40">
                            AI Copilot
                          </button>
                          ${r.status !== 'Resolved' ? `
                            <button onclick="openResolveModal(${r.id}, '${esc(r.equipment)}')" class="text-[10px] text-emerald-400 hover:text-emerald-300 font-bold px-1.5 py-0.5 rounded bg-emerald-950/40 border border-emerald-800/40">
                              Resolve
                            </button>
                          ` : ''}
                        </div>
                      </div>

                    </div>
                  `).join('')}
                </div>

              </div>
            `;
          }).join('')}
        </div>
      `;

      lucide.createIcons();
    }

    // DRAG AND DROP EVENT HANDLERS
    function handleDragStart(e, id) {
      draggedReportId = id;
      e.dataTransfer.setData('text/plain', id);
      e.dataTransfer.effectAllowed = 'move';
      const el = document.getElementById(`kcard-${id}`);
      if (el) el.classList.add('dragging');
    }

    function handleDragEnd(e) {
      const el = document.getElementById(`kcard-${draggedReportId}`);
      if (el) el.classList.remove('dragging');
      document.querySelectorAll('.kanban-drop-zone').forEach(z => z.classList.remove('drag-over'));
    }

    function handleDragOver(e) {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';
      e.currentTarget.classList.add('drag-over');
    }

    function handleDragLeave(e) {
      e.currentTarget.classList.remove('drag-over');
    }

    async function handleDrop(e, targetStatus) {
      e.preventDefault();
      e.currentTarget.classList.remove('drag-over');
      const id = draggedReportId || e.dataTransfer.getData('text/plain');

      if (!id) return;

      const report = cachedReports.find(r => r.id == id);
      if (report && report.status === targetStatus) return; // No change

      if (targetStatus === 'Resolved') {
        openResolveModal(id, report ? report.equipment : `Report #${id}`);
        return;
      }

      try {
        const res = await fetch(`/api/reports/${id}`, {
          method: 'PATCH',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ status: targetStatus })
        });
        if (res.ok) {
          playChime('success');
          showToast('Status Updated', `Moved report #FF-${id} to "${targetStatus}"`, 'success');
          await Promise.all([loadSummary(), loadReports()]);
        }
      } catch (err) {
        showToast('Error', 'Failed to update status', 'error');
      }
    }

    // Alternative List / Card View
    function renderCardList(rows) {
      const container = document.getElementById('kanbanBoardContainer');
      if (!rows.length) {
        container.innerHTML = `<div class="bg-slate-900 rounded-2xl p-10 text-center text-slate-500">No reports found.</div>`;
        return;
      }

      container.innerHTML = `<div class="space-y-3">` + rows.map(r => `
        <div class="bg-slate-900/90 rounded-2xl border border-slate-800 p-4 shadow-xl border-l-4 ${STATUS_BORDER[r.status] || 'border-l-cyan-500'}">
          <div class="flex items-start justify-between gap-3">
            <div>
              <div class="flex items-center gap-2 mb-1">
                <span class="text-xs font-mono font-bold text-cyan-400">#FF-${r.id}</span>
                <span class="text-[10px] font-bold px-2 py-0.5 rounded border ${PRIORITY_BADGES[r.priority]}">${r.priority}</span>
                <span class="text-[10px] font-bold px-2 py-0.5 rounded bg-slate-800 text-slate-300">${esc(r.status)}</span>
                <span class="text-xs text-slate-500" title="${r.created_at}">${formatRelativeTime(r.created_at)}</span>
              </div>
              <h4 class="font-bold text-white text-base">${esc(r.equipment)}</h4>
              <p class="text-xs text-slate-400 flex items-center gap-1 mt-0.5">
                <i data-lucide="map-pin" class="w-3.5 h-3.5 text-cyan-400"></i> ${esc(r.location)}
              </p>
            </div>
            <button onclick="openDiagnoseModal(${r.id})" class="px-2.5 py-1.5 rounded-xl bg-cyan-950/60 text-cyan-300 border border-cyan-800/60 text-xs font-semibold">
              AI Copilot
            </button>
          </div>
          <p class="text-xs text-slate-300 mt-2 bg-slate-950/40 p-2.5 rounded-xl border border-slate-850">${esc(r.description)}</p>
          <div class="mt-3 pt-2 border-t border-slate-800 flex items-center justify-between text-xs">
            <span class="text-slate-400">Tech: <strong class="text-cyan-300">${esc(r.assigned_to || 'Unassigned')}</strong></span>
            <div class="flex gap-2">
              ${r.status !== 'Resolved' ? `<button onclick="openResolveModal(${r.id}, '${esc(r.equipment)}')" class="px-3 py-1 bg-emerald-500 text-slate-950 font-bold rounded-lg text-xs">Mark Resolved</button>` : ''}
              <button onclick="deleteReport(${r.id})" class="text-slate-500 hover:text-rose-400"><i data-lucide="trash-2" class="w-4 h-4"></i></button>
            </div>
          </div>
        </div>
      `).join('') + `</div>`;
      lucide.createIcons();
    }


    // ==========================================
    // 5. REPORTER PORTAL TRACKER (TIMELINE STEPPER)
    // ==========================================
    function renderReporterTracker(rows) {
      const container = document.getElementById('reporterTrackerList');
      if (!container) return;

      if (!rows.length) {
        container.innerHTML = `<div class="text-center py-8 text-slate-500 text-xs">No active campus reports tracked.</div>`;
        return;
      }

      container.innerHTML = rows.slice(0, 8).map(r => {
        const step = r.status === 'Resolved' ? 3 : r.status === 'In Progress' ? 2 : 1;
        return `
          <div class="bg-slate-950/80 rounded-xl p-3.5 border border-slate-800/90 shadow-sm space-y-3">
            <div class="flex items-center justify-between">
              <div>
                <span class="text-[10px] font-mono text-cyan-400 font-bold">#FF-${r.id}</span>
                <h5 class="font-bold text-xs text-white leading-tight">${esc(r.equipment)}</h5>
                <span class="text-[11px] text-slate-400"><i data-lucide="map-pin" class="w-3 h-3 inline text-cyan-400"></i> ${esc(r.location)}</span>
              </div>
              <div class="text-right">
                <span class="text-[10px] font-bold px-1.5 py-0.5 rounded border ${PRIORITY_BADGES[r.priority]}">${r.priority}</span>
                <p class="text-[10px] text-slate-500 mt-1" title="${r.created_at}">${formatRelativeTime(r.created_at)}</p>
              </div>
            </div>

            <!-- Visual Status Stepper Timeline -->
            <div class="grid grid-cols-3 gap-1 pt-1 text-[10px]">
              <div class="text-center p-1.5 rounded-lg border ${step >= 1 ? 'bg-cyan-500/10 border-cyan-500/40 text-cyan-300 font-bold' : 'bg-slate-900 border-slate-800 text-slate-500'}">
                1. Submitted &check;
              </div>
              <div class="text-center p-1.5 rounded-lg border ${step >= 2 ? 'bg-amber-500/10 border-amber-500/40 text-amber-300 font-bold' : 'bg-slate-900 border-slate-800 text-slate-500'}">
                2. In Repair ${step >= 2 ? '&check;' : ''}
              </div>
              <div class="text-center p-1.5 rounded-lg border ${step === 3 ? 'bg-emerald-500/10 border-emerald-500/40 text-emerald-300 font-bold' : 'bg-slate-900 border-slate-800 text-slate-500'}">
                3. Resolved ${step === 3 ? '&check;' : ''}
              </div>
            </div>

            ${r.status === 'Resolved' && r.resolution_notes ? `
              <p class="text-[11px] text-emerald-300 bg-emerald-950/40 p-2 rounded border border-emerald-800/40">
                <strong>Fix Record:</strong> ${esc(r.resolution_notes)}
              </p>
            ` : ''}
          </div>
        `;
      }).join('');

      lucide.createIcons();
    }


    // ==========================================
    // 6. KEYWORD-BASED AI PRIORITY SUGGESTION
    // ==========================================
    async function triggerKeywordAiTriage() {
      const eq = document.getElementById('rEquipment').value.trim();
      const loc = document.getElementById('rLocation').value.trim();
      const desc = document.getElementById('rDescription').value.trim();

      if (!desc && !eq) return;

      try {
        const res = await fetch('/api/ai/triage', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ equipment: eq, location: loc, description: desc })
        });
        const d = await res.json();

        // Update keyword pill highlights
        const pillsBox = document.getElementById('keywordPillsContainer');
        const kw = d.matched_keywords || {};
        let htmlPills = '';

        if (kw.critical && kw.critical.length) {
          htmlPills += kw.critical.map(k => `<span class="px-2 py-0.5 rounded-md bg-rose-500/20 text-rose-300 border border-rose-500/40 font-mono text-[10px] font-bold">&bull; ${esc(k)} (Critical)</span>`).join('');
        }
        if (kw.high && kw.high.length) {
          htmlPills += kw.high.map(k => `<span class="px-2 py-0.5 rounded-md bg-orange-500/20 text-orange-300 border border-orange-500/40 font-mono text-[10px] font-bold">&bull; ${esc(k)} (High)</span>`).join('');
        }
        if (kw.medium && kw.medium.length) {
          htmlPills += kw.medium.map(k => `<span class="px-2 py-0.5 rounded-md bg-amber-500/20 text-amber-300 border border-amber-500/40 font-mono text-[10px] font-bold">&bull; ${esc(k)}</span>`).join('');
        }
        if (kw.low && kw.low.length) {
          htmlPills += kw.low.map(k => `<span class="px-2 py-0.5 rounded-md bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 font-mono text-[10px] font-bold">&bull; ${esc(k)}</span>`).join('');
        }

        pillsBox.innerHTML = htmlPills || `<span class="text-[10px] text-slate-400">${esc(d.keyword_reason)}</span>`;

        // Update suggested priority
        document.getElementById('rAiSugPriority').textContent = d.priority;
        document.getElementById('rAiSugPriority').className = 'font-bold text-sm ' + (
          d.priority === 'Critical' ? 'text-rose-400' :
          d.priority === 'High' ? 'text-orange-400' :
          d.priority === 'Medium' ? 'text-amber-400' : 'text-emerald-400'
        );
        document.getElementById('rPriority').value = d.priority;
        document.getElementById('rAiSugTech').textContent = d.suggested_technician;

        // Safety warning alert box
        const sBox = document.getElementById('rSafetyAlertBox');
        if (d.safety_alert) {
          sBox.innerHTML = esc(d.safety_alert);
          sBox.classList.remove('hidden');
          playChime('alert');
        } else {
          sBox.classList.add('hidden');
        }

        lucide.createIcons();
      } catch (err) {
        console.error('Triage error:', err);
      }
    }

    // Debounced listeners on description & equipment
    document.getElementById('rEquipment').addEventListener('input', () => {
      clearTimeout(triageTimer);
      triageTimer = setTimeout(triggerKeywordAiTriage, 300);
    });
    document.getElementById('rDescription').addEventListener('input', () => {
      clearTimeout(triageTimer);
      triageTimer = setTimeout(triggerKeywordAiTriage, 300);
    });


    // ==========================================
    // 7. FORM SUBMISSION (REPORTER FORM)
    // ==========================================
    document.getElementById('reporterForm').addEventListener('submit', async function(e) {
      e.preventDefault();
      const btn = document.getElementById('btnReporterSubmit');
      
      const body = {
        equipment: document.getElementById('rEquipment').value.trim(),
        location: document.getElementById('rLocation').value.trim(),
        description: document.getElementById('rDescription').value.trim(),
        priority: document.getElementById('rPriority').value,
        reporter_name: document.getElementById('rReporterName').value.trim() || 'Campus User',
      };

      btn.disabled = true;
      btn.innerHTML = `<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i> Submitting...`;
      lucide.createIcons();

      try {
        const res = await fetch('/api/reports', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify(body)
        });

        const data = await res.json();
        if (res.ok) {
          playChime('success');
          showToast('Report Submitted!', `Fault #${data.id} triaged as ${data.priority} and assigned to ${data.assigned_to}.`, 'success');
          this.reset();
          document.getElementById('rSafetyAlertBox').classList.add('hidden');
          document.getElementById('keywordPillsContainer').innerHTML = `<span class="text-[10px] text-slate-500 italic">Report created! Type new issue above.</span>`;
          await Promise.all([loadSummary(), loadReports()]);
        } else {
          showToast('Submission Failed', data.error || 'Check required fields', 'error');
        }
      } catch (err) {
        showToast('Error', 'Network error during submission', 'error');
      } finally {
        btn.disabled = false;
        btn.innerHTML = `<i data-lucide="check" class="w-4 h-4"></i> <span>Submit Fault Report</span>`;
        lucide.createIcons();
      }
    });


    // ==========================================
    // 8. RESOLUTION & DIAGNOSTIC MODALS
    // ==========================================
    function openResolveModal(id, eqTitle) {
      document.getElementById('resReportId').value = id;
      document.getElementById('resEquipmentTitle').textContent = `Resolution for #${id}: ${eqTitle}`;
      document.getElementById('resNotes').value = '';
      document.getElementById('resolveModal').classList.remove('hidden');
      lucide.createIcons();
    }

    function closeResolveModal() {
      document.getElementById('resolveModal').classList.add('hidden');
    }

    async function submitResolution() {
      const id = document.getElementById('resReportId').value;
      const notes = document.getElementById('resNotes').value.trim();
      const tech = document.getElementById('resTechnician').value;

      try {
        const res = await fetch(`/api/reports/${id}`, {
          method: 'PATCH',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            status: 'Resolved',
            assigned_to: tech,
            resolution_notes: notes || 'Service completed & operational tests passed.'
          })
        });

        if (res.ok) {
          playChime('success');
          showToast('Fault Resolved', `Report #FF-${id} marked as Resolved.`, 'success');
          closeResolveModal();
          await Promise.all([loadSummary(), loadReports()]);
        }
      } catch (err) {
        showToast('Error', 'Failed to resolve fault', 'error');
      }
    }

    async function openDiagnoseModal(reportId) {
      const modal = document.getElementById('diagnoseModal');
      const content = document.getElementById('diagContent');
      modal.classList.remove('hidden');

      content.innerHTML = `
        <div class="py-10 text-center text-slate-400">
          <i data-lucide="loader-2" class="w-8 h-8 animate-spin mx-auto text-cyan-400 mb-2"></i>
          <p>Running AI Root-Cause Diagnostic Copilot...</p>
        </div>
      `;
      lucide.createIcons();

      try {
        const res = await fetch(`/api/ai/diagnose/${reportId}`);
        const plan = await res.json();

        content.innerHTML = `
          <div class="bg-slate-950 p-3 rounded-xl border border-slate-800">
            <span class="text-slate-400 text-[10px] uppercase font-bold tracking-wider">Target Incident</span>
            <h4 class="font-bold text-white text-sm">${esc(plan.equipment)} <span class="text-cyan-400">(${esc(plan.location)})</span></h4>
            <div class="flex gap-2 mt-1">
              <span class="px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-medium">${esc(plan.category)}</span>
              <span class="px-2 py-0.5 rounded border ${PRIORITY_BADGES[plan.priority]}">${esc(plan.priority)} Priority</span>
            </div>
          </div>

          <div>
            <h5 class="font-bold text-slate-200 mb-1.5 flex items-center gap-1.5 text-xs text-amber-400">
              <i data-lucide="target" class="w-4 h-4"></i> Likely Root Causes
            </h5>
            <ul class="space-y-1 list-disc list-inside text-slate-300 bg-slate-950/60 p-3 rounded-xl border border-slate-800/80">
              ${plan.root_causes.map(c => `<li>${esc(c)}</li>`).join('')}
            </ul>
          </div>

          <div>
            <h5 class="font-bold text-slate-200 mb-1.5 flex items-center gap-1.5 text-xs text-cyan-400">
              <i data-lucide="wrench" class="w-4 h-4"></i> Required Tools &amp; Spare Parts
            </h5>
            <div class="flex flex-wrap gap-1.5">
              ${plan.required_tools.map(t => `<span class="px-2.5 py-1 rounded-lg bg-cyan-950/40 text-cyan-200 border border-cyan-800/50">${esc(t)}</span>`).join('')}
            </div>
          </div>

          <div>
            <h5 class="font-bold text-slate-200 mb-1.5 flex items-center gap-1.5 text-xs text-emerald-400">
              <i data-lucide="list-checks" class="w-4 h-4"></i> Step-by-Step Resolution Protocol
            </h5>
            <ol class="space-y-1.5 text-slate-300 bg-slate-950/60 p-3 rounded-xl border border-slate-800/80">
              ${plan.troubleshooting_steps.map((s, idx) => `
                <li class="flex items-start gap-2">
                  <span class="w-4 h-4 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center font-bold text-[10px] mt-0.5">${idx+1}</span>
                  <span>${esc(s)}</span>
                </li>
              `).join('')}
            </ol>
          </div>

          <p class="text-[10px] text-slate-500 italic text-center pt-1">${esc(plan.disclaimer)}</p>
        `;
        lucide.createIcons();
      } catch (err) {
        content.innerHTML = `<div class="text-rose-400 text-center py-4">Failed to load AI diagnostics.</div>`;
      }
    }

    function closeDiagnoseModal() {
      document.getElementById('diagnoseModal').classList.add('hidden');
    }

    async function deleteReport(id) {
      if (!confirm(`Delete report #FF-${id}?`)) return;
      try {
        await fetch(`/api/reports/${id}`, { method: 'DELETE' });
        showToast('Report Deleted', `Report #FF-${id} removed`, 'info');
        await Promise.all([loadSummary(), loadReports()]);
      } catch (err) {
        showToast('Error', 'Failed to delete report', 'error');
      }
    }


    // ==========================================
    // 9. ROLE & VIEW SWITCHERS
    // ==========================================
    function setRole(role) {
      currentRole = role;
      const bRep = document.getElementById('btnRoleReporter');
      const bMaint = document.getElementById('btnRoleMaintenance');
      const maintView = document.getElementById('maintenanceView');
      const repView = document.getElementById('reporterView');

      if (role === 'reporter') {
        bRep.className = 'px-3 py-1.5 rounded-lg bg-cyan-500 text-slate-950 font-bold shadow-md transition flex items-center gap-1.5';
        bMaint.className = 'px-3 py-1.5 rounded-lg text-slate-400 hover:text-white transition flex items-center gap-1.5';
        maintView.classList.add('hidden');
        repView.classList.remove('hidden');
        showToast('Reporter Portal', 'Switched to Student & Staff Fault Submission View', 'info');
      } else {
        bMaint.className = 'px-3 py-1.5 rounded-lg bg-cyan-500 text-slate-950 font-bold shadow-md transition flex items-center gap-1.5';
        bRep.className = 'px-3 py-1.5 rounded-lg text-slate-400 hover:text-white transition flex items-center gap-1.5';
        repView.classList.add('hidden');
        maintView.classList.remove('hidden');
        showToast('Maintenance Hub', 'Switched to Technician Command Center & Kanban View', 'info');
      }
      lucide.createIcons();
    }

    function setViewMode(mode) {
      currentView = mode;
      const bKanban = document.getElementById('btnViewKanban');
      const bList = document.getElementById('btnViewList');

      if (mode === 'kanban') {
        bKanban.className = 'px-2.5 py-1 rounded-lg bg-slate-800 text-cyan-400 flex items-center gap-1';
        bList.className = 'px-2.5 py-1 rounded-lg text-slate-400 hover:text-white flex items-center gap-1';
        renderKanbanBoard(cachedReports);
      } else {
        bList.className = 'px-2.5 py-1 rounded-lg bg-slate-800 text-cyan-400 flex items-center gap-1';
        bKanban.className = 'px-2.5 py-1 rounded-lg text-slate-400 hover:text-white flex items-center gap-1';
        renderCardList(cachedReports);
      }
    }

    function fillQuickDemo(id) {
      if (id === 1) {
        document.getElementById('rEquipment').value = "Main Distribution Switchboard (Lab 102)";
        document.getElementById('rLocation').value = "Electrical Science Block, Ground Floor";
        document.getElementById('rDescription').value = "Intermittent electrical sparks and burnt plastic odor from 3-phase MCB switch. Sub-panel B warm to touch.";
      } else if (id === 2) {
        document.getElementById('rEquipment').value = "Ceiling Mounted 4K Laser Projector";
        document.getElementById('rLocation').value = "Main Audi / ECE Seminar Hall";
        document.getElementById('rDescription').value = "Projector shut down during department seminar. Power LED blinks amber 5 times indicating lamp overheat warning.";
      } else if (id === 3) {
        document.getElementById('rEquipment').value = "Daikin Cassette AC 2.5 Ton";
        document.getElementById('rLocation').value = "CSE Department Server Room, 3rd Floor";
        document.getElementById('rDescription').value = "Water condensation dripping directly on networking switch rack. Server intake temperature reached 29°C.";
      }
      triggerKeywordAiTriage();
    }

    async function seedData() {
      if (!confirm('Reload clean GCT Campus Hackathon sample dataset?')) return;
      try {
        const res = await fetch('/api/seed', { method: 'POST' });
        if (res.ok) {
          playChime('success');
          showToast('Sample Data Seeded', 'Fresh GCT Campus reports loaded', 'success');
          await Promise.all([loadSummary(), loadReports()]);
        }
      } catch (err) {
        showToast('Error', 'Failed to seed data', 'error');
      }
    }

    function toggleVoiceDictation() {
      if (!('webkitSpeechRecognition' in window || 'SpeechRecognition' in window)) {
        showToast('Microphone Unsupported', 'Speech recognition is not supported in this browser.', 'warning');
        return;
      }
      const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
      const rec = new SpeechRec();
      rec.lang = 'en-US';
      rec.start();
      const txt = document.getElementById('voiceStatusText');
      txt.textContent = 'Listening...';
      rec.onresult = function(e) {
        const str = e.results[0][0].transcript;
        const desc = document.getElementById('rDescription');
        desc.value = (desc.value ? desc.value + ' ' : '') + str;
        txt.textContent = 'Voice Input';
        triggerKeywordAiTriage();
      };
      rec.onerror = function() { txt.textContent = 'Voice Input'; };
      rec.onend = function() { txt.textContent = 'Voice Input'; };
    }


    // ==========================================
    // 10. LISTENERS & STARTUP
    // ==========================================
    let searchTimer;
    document.getElementById('qSearch').addEventListener('input', () => {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(loadReports, 250);
    });
    document.getElementById('filterPriority').addEventListener('change', loadReports);
    document.getElementById('filterCategory').addEventListener('change', loadReports);

    async function initApp() {
      await Promise.all([loadSummary(), loadReports()]);
      lucide.createIcons();
    }

    initApp();
    setInterval(async () => {
      await Promise.all([loadSummary(), loadReports()]);
    }, 12000);

  </script>
</body>
</html>"""


@app.get("/")
def index():
    return render_template_string(PAGE)


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=int(os.environ.get("PORT", 5000)))
