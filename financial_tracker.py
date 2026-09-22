#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════╗
║  LIFEFLY — FINANCIAL MARKER & ANALYTICS ENGINE                       ║
║  UAV Medical Delivery Cost Tracking & Reporting                      ║
║  Priority-Based Intra-Hospital Network                               ║
╚══════════════════════════════════════════════════════════════════════╝

Tracks:
  - Per-mission cost breakdown (flight, fuel, insurance, platform)
  - Priority-based cost multipliers
  - Revenue projections and operational analytics
  - Real-time cost dashboard synced with Firebase
"""

import json
import time
import datetime
import math
import requests
import sys

# ═══════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════

FIREBASE_URL = "https://lifefly-default-rtdb.firebaseio.com"
MISSIONS_URL = f"{FIREBASE_URL}/missions.json"
FINANCIAL_URL = f"{FIREBASE_URL}/financial_log.json"
ANALYTICS_URL = f"{FIREBASE_URL}/financial_analytics.json"

# Cost Model Parameters (INR - Indian Rupees)
COST_MODEL = {
    # Base cost per km by payload category
    "payload_rates": {
        "blood":            {"rate_per_km": 45.00, "handling_fee": 200.00, "category": "Critical Bio"},
        "defibrillator":    {"rate_per_km": 62.00, "handling_fee": 350.00, "category": "Equipment"},
        "anti-venom":       {"rate_per_km": 55.00, "handling_fee": 280.00, "category": "Critical Pharma"},
        "insulin":          {"rate_per_km": 30.00, "handling_fee": 120.00, "category": "Pharma"},
        "surgical":         {"rate_per_km": 38.00, "handling_fee": 180.00, "category": "Equipment"},
        "oxygen":           {"rate_per_km": 42.00, "handling_fee": 250.00, "category": "Equipment"},
        "lab sample":       {"rate_per_km": 18.00, "handling_fee": 80.00,  "category": "Diagnostics"},
        "medication":       {"rate_per_km": 15.00, "handling_fee": 60.00,  "category": "Pharma"},
        "ppe":              {"rate_per_km": 12.00, "handling_fee": 40.00,  "category": "Supplies"},
        "records":          {"rate_per_km": 10.00, "handling_fee": 30.00,  "category": "Documents"},
        "default":          {"rate_per_km": 20.00, "handling_fee": 100.00, "category": "General"},
    },
    
    # Priority surcharge multipliers
    "priority_multipliers": {
        1: {"multiplier": 2.50, "label": "P1-CRITICAL",  "surcharge_flat": 500.00},
        2: {"multiplier": 1.80, "label": "P2-URGENT",    "surcharge_flat": 200.00},
        3: {"multiplier": 1.00, "label": "P3-STANDARD",  "surcharge_flat": 0.00},
        4: {"multiplier": 0.70, "label": "P4-LOW",       "surcharge_flat": 0.00},
    },
    
    # Fixed operational costs
    "operational_costs": {
        "fuel_per_km": 8.50,           # Battery degradation cost per km
        "insurance_pct": 0.05,          # 5% of flight cost
        "platform_fee": 150.00,         # Fixed per-mission platform fee
        "maintenance_per_flight": 75.00, # Avg maintenance allocation
        "pilot_ops_per_hour": 500.00,   # Remote pilot operations cost
        "depreciation_per_flight": 120.00, # UAV depreciation per flight
    },
    
    # Revenue model
    "revenue_margins": {
        "hospital_contract_markup": 0.35,  # 35% markup for hospital contracts
        "emergency_premium": 0.50,          # 50% premium for emergency calls
        "government_subsidy_pct": 0.15,     # 15% government healthcare subsidy
    }
}

RESET  = "\033[0m"
CYAN   = "\033[1;96m"
GREEN  = "\033[1;92m"
RED    = "\033[1;91m"
YELLOW = "\033[1;93m"
WHITE  = "\033[1;97m"
DIM    = "\033[2m"
BOLD   = "\033[1m"
MAGENTA = "\033[1;95m"


# ═══════════════════════════════════════════════════════════════
# DISTANCE CALCULATOR
# ═══════════════════════════════════════════════════════════════

def haversine_km(lat1, lon1, lat2, lon2):
    """Calculate distance in km between two GPS coordinates."""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat/2)**2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon/2)**2)
    return R * 2 * math.asin(math.sqrt(a))


# ═══════════════════════════════════════════════════════════════
# FINANCIAL CALCULATOR
# ═══════════════════════════════════════════════════════════════

class FinancialEngine:
    """Complete financial cost/revenue calculation engine."""
    
    def __init__(self, cost_model=COST_MODEL):
        self.model = cost_model
    
    def identify_payload_category(self, payload_text):
        """Identify payload rate category from description."""
        payload_lower = payload_text.lower()
        for key, info in self.model["payload_rates"].items():
            if key in payload_lower:
                return key, info
        return "default", self.model["payload_rates"]["default"]
    
    def calculate_mission_cost(self, distance_km, priority, payload_text, flight_time_min=None):
        """
        Calculate complete cost breakdown for a delivery mission.
        
        Returns a detailed financial record with all cost components.
        """
        # Identify payload category
        category_key, payload_info = self.identify_payload_category(payload_text)
        
        # Get priority info
        pri_info = self.model["priority_multipliers"].get(priority, self.model["priority_multipliers"][3])
        ops = self.model["operational_costs"]
        
        # Estimate flight time if not provided
        if flight_time_min is None:
            speed_kmh = 48  # Average UAV speed
            flight_time_min = (distance_km / speed_kmh) * 60
        
        flight_time_hours = flight_time_min / 60
        
        # ── COST BREAKDOWN ──
        
        # 1. Distance-based flight cost
        base_flight_cost = distance_km * payload_info["rate_per_km"]
        
        # 2. Apply priority multiplier
        prioritized_flight_cost = base_flight_cost * pri_info["multiplier"]
        
        # 3. Priority flat surcharge
        priority_surcharge = pri_info["surcharge_flat"]
        
        # 4. Handling fee (for special payload)
        handling_fee = payload_info["handling_fee"]
        
        # 5. Fuel / Battery cost
        fuel_cost = distance_km * ops["fuel_per_km"]
        
        # 6. Insurance (percentage of flight cost)
        insurance_cost = prioritized_flight_cost * ops["insurance_pct"]
        
        # 7. Platform fee
        platform_fee = ops["platform_fee"]
        
        # 8. Maintenance allocation
        maintenance = ops["maintenance_per_flight"]
        
        # 9. Pilot operations cost
        pilot_cost = flight_time_hours * ops["pilot_ops_per_hour"]
        
        # 10. Depreciation
        depreciation = ops["depreciation_per_flight"]
        
        # ── TOTAL COST ──
        total_cost = (
            prioritized_flight_cost +
            priority_surcharge +
            handling_fee +
            fuel_cost +
            insurance_cost +
            platform_fee +
            maintenance +
            pilot_cost +
            depreciation
        )
        
        # ── REVENUE CALCULATION ──
        rev = self.model["revenue_margins"]
        
        gross_revenue = total_cost * (1 + rev["hospital_contract_markup"])
        if priority <= 2:
            gross_revenue *= (1 + rev["emergency_premium"])
        
        government_subsidy = gross_revenue * rev["government_subsidy_pct"]
        net_revenue = gross_revenue - government_subsidy
        profit = net_revenue - total_cost
        profit_margin = (profit / net_revenue * 100) if net_revenue > 0 else 0
        
        return {
            # Cost breakdown
            "base_flight_cost": round(base_flight_cost, 2),
            "priority_multiplier": pri_info["multiplier"],
            "prioritized_flight_cost": round(prioritized_flight_cost, 2),
            "priority_surcharge": round(priority_surcharge, 2),
            "handling_fee": round(handling_fee, 2),
            "fuel_cost": round(fuel_cost, 2),
            "insurance_cost": round(insurance_cost, 2),
            "platform_fee": round(platform_fee, 2),
            "maintenance": round(maintenance, 2),
            "pilot_cost": round(pilot_cost, 2),
            "depreciation": round(depreciation, 2),
            "total_cost": round(total_cost, 2),
            
            # Revenue
            "gross_revenue": round(gross_revenue, 2),
            "government_subsidy": round(government_subsidy, 2),
            "net_revenue": round(net_revenue, 2),
            "profit": round(profit, 2),
            "profit_margin_pct": round(profit_margin, 1),
            
            # Meta
            "currency": "INR",
            "distance_km": round(distance_km, 2),
            "flight_time_min": round(flight_time_min, 1),
            "payload_category": payload_info["category"],
            "payload_rate_key": category_key,
            "priority_label": pri_info["label"],
            "cost_per_km": round(payload_info["rate_per_km"] * pri_info["multiplier"], 2),
        }
    
    def generate_invoice(self, mission_data, cost_data):
        """Generate a text invoice for a mission."""
        invoice = f"""
{'═' * 60}
  LIFEFLY UAV MEDICAL DELIVERY — INVOICE
{'═' * 60}

  Invoice Date:   {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
  Mission ID:     {mission_data.get('request_id', 'N/A')}
  Priority:       {cost_data['priority_label']}

─────────────────────────────────────────
  CLIENT DETAILS
─────────────────────────────────────────
  Hospital Branch: {mission_data.get('branch_name', 'N/A')}
  Destination GPS: [{mission_data.get('latitude', 0):.6f}, {mission_data.get('longitude', 0):.6f}]
  Payload:         {mission_data.get('request_details', 'N/A')}
  Category:        {cost_data['payload_category']}

─────────────────────────────────────────
  COST BREAKDOWN                    (INR)
─────────────────────────────────────────
  Base Flight Cost:          ₹{cost_data['base_flight_cost']:>10,.2f}
  Priority Multiplier:          ×{cost_data['priority_multiplier']}
  Prioritized Flight:       ₹{cost_data['prioritized_flight_cost']:>10,.2f}
  Priority Surcharge:       ₹{cost_data['priority_surcharge']:>10,.2f}
  Handling Fee:              ₹{cost_data['handling_fee']:>10,.2f}
  Fuel/Battery:              ₹{cost_data['fuel_cost']:>10,.2f}
  Insurance (5%):            ₹{cost_data['insurance_cost']:>10,.2f}
  Platform Fee:              ₹{cost_data['platform_fee']:>10,.2f}
  Maintenance:               ₹{cost_data['maintenance']:>10,.2f}
  Pilot Ops:                 ₹{cost_data['pilot_cost']:>10,.2f}
  UAV Depreciation:          ₹{cost_data['depreciation']:>10,.2f}
                             ─────────────
  TOTAL COST:                ₹{cost_data['total_cost']:>10,.2f}

─────────────────────────────────────────
  REVENUE
─────────────────────────────────────────
  Gross Revenue:             ₹{cost_data['gross_revenue']:>10,.2f}
  Govt. Subsidy (-15%):     -₹{cost_data['government_subsidy']:>10,.2f}
  Net Revenue:               ₹{cost_data['net_revenue']:>10,.2f}
  Profit:                    ₹{cost_data['profit']:>10,.2f}
  Profit Margin:                 {cost_data['profit_margin_pct']}%

─────────────────────────────────────────
  FLIGHT DETAILS
─────────────────────────────────────────
  Distance:        {cost_data['distance_km']:.2f} km
  Est. Flight Time: {cost_data['flight_time_min']:.1f} min
  Cost per km:     ₹{cost_data['cost_per_km']:.2f}

{'═' * 60}
  Payment Terms: Net 30 | GSTIN: XXAAACL1234F1Z5
  LifeFly UAV Services Pvt. Ltd.
{'═' * 60}
"""
        return invoice


# ═══════════════════════════════════════════════════════════════
# ANALYTICS ENGINE
# ═══════════════════════════════════════════════════════════════

class AnalyticsEngine:
    """Generate financial analytics and reports."""
    
    def __init__(self):
        self.engine = FinancialEngine()
    
    def fetch_all_financial_records(self):
        """Fetch all financial records from Firebase."""
        try:
            response = requests.get(FINANCIAL_URL, timeout=10)
            if response.status_code == 200 and response.json():
                return response.json()
        except:
            pass
        return {}
    
    def fetch_all_missions(self):
        """Fetch all missions from Firebase."""
        try:
            response = requests.get(MISSIONS_URL, timeout=10)
            if response.status_code == 200 and response.json():
                return response.json()
        except:
            pass
        return {}
    
    def generate_daily_report(self):
        """Generate comprehensive daily financial report."""
        records = self.fetch_all_financial_records()
        missions = self.fetch_all_missions()
        
        if not records and not missions:
            return "No data available for report."
        
        # Metrics
        total_missions = 0
        total_cost = 0
        total_revenue = 0
        total_profit = 0
        total_distance = 0
        
        priority_breakdown = {1: {"count": 0, "cost": 0, "revenue": 0},
                             2: {"count": 0, "cost": 0, "revenue": 0},
                             3: {"count": 0, "cost": 0, "revenue": 0},
                             4: {"count": 0, "cost": 0, "revenue": 0}}
        
        category_breakdown = {}
        branch_breakdown = {}
        hourly_volume = {h: 0 for h in range(24)}
        
        data_source = records if records else {}
        
        for key, rec in data_source.items():
            total_missions += 1
            cost = float(rec.get("total_cost", 0))
            revenue = float(rec.get("net_revenue", rec.get("gross_revenue", cost * 1.35)))
            profit = revenue - cost
            dist = float(rec.get("distance_km", 0))
            
            total_cost += cost
            total_revenue += revenue
            total_profit += profit
            total_distance += dist
            
            # Priority breakdown
            pri_label = str(rec.get("priority", "P3-STANDARD"))
            try:
                pri_num = int(pri_label[1]) if pri_label.startswith("P") else int(pri_label)
            except (ValueError, IndexError):
                pri_num = 3
            
            if pri_num in priority_breakdown:
                priority_breakdown[pri_num]["count"] += 1
                priority_breakdown[pri_num]["cost"] += cost
                priority_breakdown[pri_num]["revenue"] += revenue
            
            # Category
            cat = rec.get("payload_category", rec.get("category", "General"))
            if cat not in category_breakdown:
                category_breakdown[cat] = {"count": 0, "revenue": 0}
            category_breakdown[cat]["count"] += 1
            category_breakdown[cat]["revenue"] += revenue
            
            # Branch
            branch = rec.get("branch", "Unknown")
            if branch not in branch_breakdown:
                branch_breakdown[branch] = {"count": 0, "revenue": 0}
            branch_breakdown[branch]["count"] += 1
            branch_breakdown[branch]["revenue"] += revenue
            
            # Hourly
            ts = rec.get("timestamp", "")
            if ts:
                try:
                    hour = int(ts[11:13])
                    hourly_volume[hour] += 1
                except:
                    pass
        
        avg_cost = total_cost / max(total_missions, 1)
        avg_distance = total_distance / max(total_missions, 1)
        profit_margin = (total_profit / max(total_revenue, 1)) * 100
        
        # Build report
        report = f"""
{CYAN}{'═' * 65}
  LIFEFLY FINANCIAL ANALYTICS REPORT
  Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'═' * 65}{RESET}

{WHITE}  ┌─────────────────────────────────────────────────┐
  │  KEY METRICS                                      │
  ├─────────────────────────────────────────────────┤
  │  Total Missions:        {total_missions:>10}               │
  │  Total Distance:        {total_distance:>10.1f} km           │
  │  Avg Distance/Mission:  {avg_distance:>10.1f} km           │
  │  Total Cost:            ₹{total_cost:>12,.2f}          │
  │  Total Revenue:         ₹{total_revenue:>12,.2f}          │
  │  Total Profit:          ₹{total_profit:>12,.2f}          │
  │  Profit Margin:             {profit_margin:>6.1f}%            │
  │  Avg Cost/Mission:      ₹{avg_cost:>12,.2f}          │
  └─────────────────────────────────────────────────┘{RESET}

{CYAN}  PRIORITY BREAKDOWN{RESET}
  {'─' * 60}"""

        pri_labels = {1: "P1-CRITICAL", 2: "P2-URGENT", 3: "P3-STANDARD", 4: "P4-LOW"}
        pri_colors = {1: RED, 2: YELLOW, 3: GREEN, 4: CYAN}
        
        for pri in [1, 2, 3, 4]:
            data = priority_breakdown[pri]
            bar = '█' * min(int(data["count"] / max(total_missions, 1) * 40), 40)
            report += f"""
  {pri_colors[pri]}{pri_labels[pri]:<16}{RESET} | {data['count']:>4} missions | ₹{data['cost']:>10,.2f} cost | ₹{data['revenue']:>10,.2f} rev | {bar}"""
        
        report += f"""

{CYAN}  TOP BRANCHES BY REVENUE{RESET}
  {'─' * 60}"""
        
        sorted_branches = sorted(branch_breakdown.items(), key=lambda x: x[1]["revenue"], reverse=True)[:8]
        for branch, data in sorted_branches:
            report += f"""
  {WHITE}{branch[:30]:<32}{RESET} | {data['count']:>3} missions | ₹{data['revenue']:>10,.2f}"""
        
        report += f"""

{CYAN}  PAYLOAD CATEGORY REVENUE{RESET}
  {'─' * 60}"""
        
        sorted_categories = sorted(category_breakdown.items(), key=lambda x: x[1]["revenue"], reverse=True)
        for cat, data in sorted_categories:
            report += f"""
  {WHITE}{cat[:25]:<28}{RESET} | {data['count']:>3} deliveries | ₹{data['revenue']:>10,.2f}"""
        
        report += f"""

{CYAN}  HOURLY VOLUME (24H){RESET}
  {'─' * 60}"""
        
        max_vol = max(hourly_volume.values()) if hourly_volume.values() else 1
        for hour in range(24):
            vol = hourly_volume[hour]
            bar = '▓' * int(vol / max(max_vol, 1) * 30)
            if vol > 0:
                report += f"""
  {hour:02d}:00 | {vol:>3} | {GREEN}{bar}{RESET}"""
        
        report += f"""

{'═' * 65}
  © LifeFly UAV Services | GSTIN: XXAAACL1234F1Z5
{'═' * 65}
"""
        return report
    
    def push_analytics_to_firebase(self):
        """Calculate and push aggregated analytics to Firebase."""
        records = self.fetch_all_financial_records()
        
        if not records:
            return
        
        total_missions = len(records)
        total_cost = sum(float(r.get("total_cost", 0)) for r in records.values())
        total_distance = sum(float(r.get("distance_km", 0)) for r in records.values())
        
        analytics = {
            "total_missions": total_missions,
            "total_cost_inr": round(total_cost, 2),
            "total_distance_km": round(total_distance, 2),
            "avg_cost_per_mission": round(total_cost / max(total_missions, 1), 2),
            "avg_distance_km": round(total_distance / max(total_missions, 1), 2),
            "estimated_revenue": round(total_cost * 1.35, 2),
            "last_updated": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        
        try:
            requests.put(ANALYTICS_URL, json=analytics, timeout=10)
            print(f"{GREEN}[✓] Analytics pushed to Firebase{RESET}")
        except Exception as e:
            print(f"{RED}[!] Failed to push analytics: {e}{RESET}")


# ═══════════════════════════════════════════════════════════════
# PROCESS ALL EXISTING MISSIONS
# ═══════════════════════════════════════════════════════════════

def process_existing_missions():
    """Recalculate financials for all existing missions."""
    engine = FinancialEngine()
    
    try:
        response = requests.get(MISSIONS_URL, timeout=10)
        if response.status_code != 200 or not response.json():
            print(f"{DIM}No missions to process.{RESET}")
            return
        
        missions = response.json()
        base_lat, base_lng = 17.397210, 78.489888
        
        print(f"\n{CYAN}Processing {len(missions)} missions...{RESET}\n")
        
        for key, mission in missions.items():
            lat = float(mission.get("latitude", base_lat))
            lng = float(mission.get("longitude", base_lng))
            distance = haversine_km(base_lat, base_lng, lat, lng)
            priority = int(mission.get("priority", 3))
            payload = mission.get("request_details", "General medical supplies")
            
            cost_data = engine.calculate_mission_cost(distance, priority, payload)
            
            # Update mission with financial data
            url = f"{FIREBASE_URL}/missions/{key}.json"
            try:
                requests.patch(url, json={"financial": cost_data}, timeout=5)
            except:
                pass
            
            # Push individual financial record
            financial_record = {
                "mission_id": mission.get("request_id", key),
                "timestamp": mission.get("timestamp", datetime.datetime.now(datetime.timezone.utc).isoformat()),
                "priority": f"P{priority}-{['', 'CRITICAL', 'URGENT', 'STANDARD', 'LOW'][min(priority, 4)]}",
                **cost_data,
                "branch": mission.get("branch_name", "Unknown")
            }
            
            try:
                requests.post(FINANCIAL_URL, json=financial_record, timeout=5)
            except:
                pass
            
            print(f"  {GREEN}✓{RESET} {mission.get('request_id', key)}: "
                  f"₹{cost_data['total_cost']:,.2f} | "
                  f"{cost_data['distance_km']:.1f}km | "
                  f"{cost_data['priority_label']}")
        
        print(f"\n{GREEN}[✓] All missions processed{RESET}")
        
    except Exception as e:
        print(f"{RED}Error: {e}{RESET}")


# ═══════════════════════════════════════════════════════════════
# INTERACTIVE CLI
# ═══════════════════════════════════════════════════════════════

def main():
    print(f"""
{CYAN}╔══════════════════════════════════════════════════════════════╗
║  LIFEFLY FINANCIAL MARKER ENGINE                             ║
║  UAV Medical Delivery — Cost & Revenue Analytics             ║
╚══════════════════════════════════════════════════════════════╝{RESET}
    """)
    
    engine = FinancialEngine()
    analytics = AnalyticsEngine()
    
    while True:
        print(f"""
{CYAN}Commands:{RESET}
  {GREEN}1{RESET} — Calculate cost for a mission
  {GREEN}2{RESET} — Generate full financial report
  {GREEN}3{RESET} — Process all existing missions
  {GREEN}4{RESET} — Push analytics to Firebase
  {GREEN}5{RESET} — Generate sample invoice
  {GREEN}0{RESET} — Exit
        """)
        
        cmd = input(f"{CYAN}Financial ▸ {RESET}").strip()
        
        if cmd == "1":
            try:
                dist = float(input(f"  Distance (km): "))
                pri = int(input(f"  Priority (1-4): "))
                payload = input(f"  Payload description: ")
                cost = engine.calculate_mission_cost(dist, pri, payload)
                
                print(f"\n{GREEN}{'─' * 50}")
                print(f"  Cost Breakdown:{RESET}")
                for k, v in cost.items():
                    if isinstance(v, (int, float)):
                        print(f"    {k:<30} ₹{v:>10,.2f}" if "pct" not in k and "multiplier" not in k 
                              else f"    {k:<30}   {v}")
                    else:
                        print(f"    {k:<30}   {v}")
                print(f"{GREEN}{'─' * 50}{RESET}")
            except ValueError:
                print(f"{RED}Invalid input{RESET}")
        
        elif cmd == "2":
            report = analytics.generate_daily_report()
            print(report)
        
        elif cmd == "3":
            process_existing_missions()
        
        elif cmd == "4":
            analytics.push_analytics_to_firebase()
        
        elif cmd == "5":
            sample_mission = {
                "request_id": "UAV-SAMPLE",
                "branch_name": "Apollo Main Campus",
                "latitude": 17.4122,
                "longitude": 78.4343,
                "request_details": "Blood Pack O-Negative Emergency"
            }
            dist = haversine_km(17.397210, 78.489888, 17.4122, 78.4343)
            cost = engine.calculate_mission_cost(dist, 1, sample_mission["request_details"])
            invoice = engine.generate_invoice(sample_mission, cost)
            print(invoice)
        
        elif cmd == "0":
            print(f"{RED}Exiting...{RESET}")
            break
        
        else:
            print(f"{DIM}Unknown command{RESET}")


if __name__ == "__main__":
    main()
