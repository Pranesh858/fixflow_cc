# FixFlow — Smart Fault Reporting & Resolution System
> **Coding Club GCT — AI Web Development Hackathon**  
> *Category: AI Web Application | Duration: 60 Mins | Team Size: 1–2 Participants*

FixFlow is a comprehensive, AI-powered equipment fault reporting and maintenance management platform engineered for colleges, universities, offices, and industrial environments. It solves the chaos of informal, untracked breakdown messages by centralizing the complete maintenance lifecycle into a single high-aesthetic command center.

---

## 🌟 Key Features & Hackathon Highlights

### 1. 🗂️ Kanban Board with Drag & Drop (`Open` ➔ `In Progress` ➔ `Resolved`)
- **Interactive Drag & Drop**: Native HTML5 draggable fault cards with glowing drop zones and hover states.
- **Instant Status Sync**: Dropping a card into a column immediately updates the SQLite database via `PATCH /api/reports/<id>`, plays an audio chime, and raises a toast notification.
- Supports quick switch to Feed/List view for standard inspection.

### 2. 📊 Interactive Analytics Charts (Chart.js)
- **Status Doughnut Chart**: Visualizes breakdown between Open (Rose), In Progress (Amber), and Resolved (Emerald) with a live resolution rate indicator.
- **Issues Per Location Bar Chart**: Highlights campus fault hotspots (e.g. Chemistry Lab, Central Library, CSE Lab, Seminar Hall) to aid proactive preventative maintenance.

### 3. 🔔 Toast Notifications & Relative Timestamps
- **Floating Toast System**: Real-time glassmorphism alerts for report creation, drag-and-drop moves, resolution logs, data seeding, and errors.
- **Dynamic Relative Timestamps**: Displays intuitive times (*"Just now"*, *"5m ago"*, *"2h ago"*, *"Yesterday"*) with complete hover timestamp tooltips.

### 4. 👥 Reporter vs Maintenance Role Toggle
- **Student & Staff Reporter Portal**: Simplified fault submission interface with voice dictation, fast templates, and a 3-step visual tracker (*1. Submitted ➔ 2. In Repair ➔ 3. Resolved*).
- **Maintenance Command Center**: Full operational dashboard with drag-and-drop Kanban, analytics charts, technician assignment, and AI diagnostic copilot.

### 5. 🤖 Keyword-Based AI Priority Suggestion
- **Real-Time Keyword Radar**: Scans fault descriptions on every keystroke for hazard and urgency signals:
  - *Critical triggers*: `spark`, `smoke`, `fire`, `shock`, `explosion`, `burst`, `acid`, `gas leak`
  - *High triggers*: `leak`, `server`, `overheating`, `exam`, `seminar`, `blackout`, `jammed`
  - *Medium/Low triggers*: `noise`, `rattle`, `flicker`, `loose`, `scratch`, `squeak`
- **Dynamic Tag Badges**: Surfaces extracted keywords visually and auto-recommends priority with safety advisory warnings.

---

## 🚀 How to Run Locally

### Prerequisites
- Python 3.10+ (Tested on Python 3.12 & 3.14)
- Flask 3.0+

### Setup & Launch
```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run FixFlow server
python app.py
```

The application will start at:
👉 **`http://127.0.0.1:5000`**

---

## 📡 REST API Reference

| Endpoint | Method | Description |
| :--- | :---: | :--- |
| `/` | `GET` | Main Web Application UI (HTML/Tailwind/Lucide) |
| `/api/reports` | `GET` | List all fault reports (supports `status`, `priority`, `category`, `q`, `sort`) |
| `/api/reports` | `POST` | Submit a new fault report with auto AI triage |
| `/api/reports/<id>` | `PATCH` | Update status, assigned technician, or resolution notes |
| `/api/reports/<id>` | `DELETE` | Delete/archive a fault report |
| `/api/summary` | `GET` | Get real-time metric counts, category stats, and resolution rate |
| `/api/ai/triage` | `POST` | Real-time NLP triage preview for form inputs |
| `/api/ai/diagnose/<id>` | `GET` | Technician AI Diagnostic Copilot troubleshooting checklist |
| `/api/seed` | `POST` | Reload clean GCT Campus sample dataset |
| `/api/export` | `GET` | Export maintenance records to CSV |

---

## 🎨 Design Philosophy
- **Aesthetic**: Deep midnight slate glassmorphism with vibrant glowing status indicators.
- **Typography**: Google Fonts (*Outfit* and *Plus Jakarta Sans*).
- **Sound**: Subtle zero-dependency Web Audio API chimes for confirmations and urgent warnings.
