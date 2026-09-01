#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════╗
║  LIFEFLY — AUTOMATIC PRIORITY DETECTION ENGINE                       ║
║  Intelligent Medical Payload Classification System                   ║
╚══════════════════════════════════════════════════════════════════════╝

Automatically assigns priority levels based on medical payload keywords:
  P1-CRITICAL:  Life-threatening — Immediate dispatch
  P2-URGENT:    Time-sensitive — Within 10 minutes
  P3-STANDARD:  Routine — Scheduled delivery
  P4-LOW:       Non-urgent — Batch delivery
"""

import re

# ═══════════════════════════════════════════════════════════════
# MEDICAL PAYLOAD CLASSIFICATION DATABASE
# ═══════════════════════════════════════════════════════════════

CRITICAL_KEYWORDS = [
    # Organs & Transplants
    'lung', 'lungs', 'kidney', 'kidneys', 'heart', 'liver', 'organ',
    'transplant', 'donor', 'recipient',

    # Blood Products
    'blood', 'blood pack', 'blood packet', 'plasma', 'platelets',
    'transfusion', 'o-negative', 'o-positive', 'ab-negative', 'rh-negative',

    # Critical Emergency Equipment
    'defibrillator', 'aed', 'ventilator', 'respirator',
    'crash cart', 'emergency kit',

    # Life-Saving Medications
    'anti-venom', 'antivenom', 'venom', 'snake bite',
    'epinephrine', 'epipen', 'adrenaline',
    'naloxone', 'narcan',
    'atropine', 'adenosine',

    # Critical Trauma
    'trauma', 'gunshot', 'stab', 'hemorrhage', 'bleeding',
    'stroke', 'cardiac arrest', 'heart attack', 'myocardial',
    'anaphylaxis', 'allergic shock',
    'sepsis', 'septic shock',

    # Emergency Surgeries
    'emergency surgery', 'urgent surgery', 'operation',
    'amputation', 'cesarean', 'c-section',
]

URGENT_KEYWORDS = [
    # Time-Sensitive Medications
    'insulin', 'diabetic', 'diabetes', 'glucose',
    'antibiotic', 'antibiotics',
    'chemotherapy', 'chemo',
    'dialysis',

    # Surgical & Procedure Equipment
    'surgical', 'surgery', 'scalpel', 'suture', 'instruments',
    'sterile kit', 'surgical kit',

    # Critical Supplies
    'oxygen', 'oxygen cylinder', 'o2',
    'iv', 'iv fluid', 'saline', 'ringer',
    'catheter', 'tube', 'intubation',

    # Urgent Diagnostics
    'biopsy', 'urgent test', 'stat test',
    'culture', 'specimen',

    # Urgent Conditions
    'burn', 'burns', 'fracture', 'broken bone',
    'seizure', 'convulsion',
    'asthma', 'respiratory',
]

STANDARD_KEYWORDS = [
    # Routine Lab & Diagnostics
    'lab', 'laboratory', 'sample', 'samples',
    'pathology', 'test', 'screening',
    'blood work', 'urine', 'culture',

    # Regular Medications
    'medication', 'medicine', 'prescription', 'refill',
    'pills', 'tablets', 'capsules',
    'antihistamine', 'painkiller', 'analgesic',

    # Routine Supplies
    'bandage', 'bandages', 'dressing', 'gauze',
    'syringe', 'syringes', 'needle', 'needles',
    'gloves', 'mask', 'masks',

    # Scheduled Procedures
    'scheduled', 'routine', 'checkup', 'follow-up',
    'vaccination', 'vaccine', 'immunization',
]

LOW_PRIORITY_KEYWORDS = [
    # Administrative
    'record', 'records', 'paperwork', 'document', 'documents',
    'file', 'files', 'report', 'reports',
    'form', 'forms', 'consent',

    # Non-Critical Supplies
    'ppe', 'personal protective equipment',
    'supplies', 'general supplies', 'stock',
    'stationary', 'office',

    # Bulk Deliveries
    'bulk', 'batch', 'inventory',
    'non-urgent', 'low priority',
]


# ═══════════════════════════════════════════════════════════════
# PRIORITY DETECTION ENGINE
# ═══════════════════════════════════════════════════════════════

def detect_priority(payload_text: str) -> dict:
    """
    Automatically detect priority level from payload description.

    Args:
        payload_text: Medical payload description text

    Returns:
        dict with priority (1-4), label, confidence, matched_keywords
    """
    if not payload_text:
        return {
            'priority': 3,
            'label': 'P3-STANDARD',
            'confidence': 'low',
            'matched_keywords': [],
            'reason': 'No payload description provided'
        }

    # Normalize text
    text_lower = payload_text.lower()
    text_lower = re.sub(r'[^\w\s-]', ' ', text_lower)

    # Check for explicit priority markers first
    explicit_patterns = {
        1: [r'\bp1\b', r'critical', r'emergency', r'urgent', r'immediate', r'stat', r'code\s*red'],
        2: [r'\bp2\b', r'high\s*priority', r'expedited', r'asap'],
        4: [r'\bp4\b', r'low\s*priority', r'non-urgent', r'routine']
    }

    for pri, patterns in explicit_patterns.items():
        for pattern in patterns:
            if re.search(pattern, text_lower):
                label_map = {1: 'P1-CRITICAL', 2: 'P2-URGENT', 3: 'P3-STANDARD', 4: 'P4-LOW'}
                return {
                    'priority': pri,
                    'label': label_map[pri],
                    'confidence': 'explicit',
                    'matched_keywords': [pattern],
                    'reason': f'Explicit priority marker found: "{pattern}"'
                }

    # Keyword matching with scoring
    matched_critical = []
    matched_urgent = []
    matched_standard = []
    matched_low = []

    for keyword in CRITICAL_KEYWORDS:
        if keyword in text_lower:
            matched_critical.append(keyword)

    for keyword in URGENT_KEYWORDS:
        if keyword in text_lower:
            matched_urgent.append(keyword)

    for keyword in STANDARD_KEYWORDS:
        if keyword in text_lower:
            matched_standard.append(keyword)

    for keyword in LOW_PRIORITY_KEYWORDS:
        if keyword in text_lower:
            matched_low.append(keyword)

    # Priority decision logic
    if matched_critical:
        return {
            'priority': 1,
            'label': 'P1-CRITICAL',
            'confidence': 'high',
            'matched_keywords': matched_critical,
            'reason': f'Critical medical keywords detected: {", ".join(matched_critical[:3])}'
        }

    if matched_urgent:
        return {
            'priority': 2,
            'label': 'P2-URGENT',
            'confidence': 'high',
            'matched_keywords': matched_urgent,
            'reason': f'Urgent medical keywords detected: {", ".join(matched_urgent[:3])}'
        }

    if matched_low and not matched_standard:
        return {
            'priority': 4,
            'label': 'P4-LOW',
            'confidence': 'medium',
            'matched_keywords': matched_low,
            'reason': f'Low-priority keywords detected: {", ".join(matched_low[:3])}'
        }

    if matched_standard:
        return {
            'priority': 3,
            'label': 'P3-STANDARD',
            'confidence': 'medium',
            'matched_keywords': matched_standard,
            'reason': f'Standard medical keywords detected: {", ".join(matched_standard[:3])}'
        }

    # Default to P3 if no keywords match
    return {
        'priority': 3,
        'label': 'P3-STANDARD',
        'confidence': 'default',
        'matched_keywords': [],
        'reason': 'No specific keywords matched — assigned default priority'
    }


def get_priority_description(priority: int) -> str:
    """Get human-readable description of priority level."""
    descriptions = {
        1: "⚡ P1-CRITICAL — Life-threatening, immediate dispatch required",
        2: "🔥 P2-URGENT — Time-sensitive, within 10 minutes",
        3: "📦 P3-STANDARD — Routine scheduled delivery",
        4: "📋 P4-LOW — Non-urgent batch delivery"
    }
    return descriptions.get(priority, descriptions[3])


# ═══════════════════════════════════════════════════════════════
# TESTING & DEMONSTRATION
# ═══════════════════════════════════════════════════════════════

def test_priority_detector():
    """Test the priority detection system with various payloads."""

    test_cases = [
        "Blood Pack O-Negative Emergency for trauma patient",
        "Kidney transplant organ transport - urgent",
        "Lung tissue for emergency transplant surgery",
        "Defibrillator unit for cardiac emergency",
        "Anti-venom serum for snake bite victim",
        "Insulin emergency kit for diabetic patient",
        "Surgical instruments for scheduled operation",
        "Oxygen cylinder for respiratory patient",
        "Lab samples for pathology testing",
        "Medication refill pack - routine",
        "PPE supply bundle for ward restocking",
        "Medical records for patient transfer",
        "Blood work samples for routine screening",
        "Emergency crash cart equipment",
        "Epinephrine for anaphylaxis treatment",
    ]

    print("\n" + "=" * 80)
    print("  LIFEFLY AUTOMATIC PRIORITY DETECTION - TEST SUITE")
    print("=" * 80 + "\n")

    for i, payload in enumerate(test_cases, 1):
        result = detect_priority(payload)

        # Color coding
        colors = {1: '\033[1;91m', 2: '\033[1;93m', 3: '\033[1;92m', 4: '\033[1;94m'}
        color = colors.get(result['priority'], '\033[0m')
        reset = '\033[0m'

        print(f"Test #{i}:")
        print(f"  Payload: \033[97m{payload}\033[0m")
        print(f"  Result:  {color}{result['label']}{reset} (confidence: {result['confidence']})")
        print(f"  Reason:  \033[90m{result['reason']}\033[0m")
        if result['matched_keywords']:
            print(f"  Keywords: \033[36m{', '.join(result['matched_keywords'][:5])}\033[0m")
        print()


if __name__ == "__main__":
    test_priority_detector()
