"""
Supplement Protocol Engine — Evidence-based supplement recommendations by phase.

Every supplement has an evidence grade:
  A = Strong RCT evidence, ISSN/IOC position stand
  B = Moderate evidence, multiple studies
  C = Preliminary evidence, traditional use
"""
from __future__ import annotations


SUPPLEMENT_PROTOCOLS: dict[str, list[dict]] = {
    "all_phases": [
        {
            "name": "Creatine Monohydrate",
            "dose": "5g/day",
            "timing": "Any time (with meal)",
            "evidence": "A",
            "rationale": "Increases phosphocreatine stores, improves strength and power output by 5-10%. "
                         "Saturates in ~28 days at 5g/day. No loading phase needed.",
        },
        {
            "name": "Vitamin D3",
            "dose": "2000-5000 IU/day",
            "timing": "With a fat-containing meal",
            "evidence": "A",
            "rationale": "Most athletes are deficient. Supports testosterone, bone density, immune function. "
                         "Test serum 25(OH)D levels — target 40-60 ng/mL.",
        },
        {
            "name": "Omega-3 (EPA/DHA)",
            "dose": "2-3g combined EPA+DHA/day",
            "timing": "With meals (split AM/PM)",
            "evidence": "A",
            "rationale": "Anti-inflammatory, supports joint health, may improve muscle protein synthesis. "
                         "Use triglyceride form, not ethyl ester.",
        },
        {
            "name": "Magnesium Glycinate",
            "dose": "200-400mg elemental Mg",
            "timing": "Before bed",
            "evidence": "B",
            "rationale": "Supports sleep quality, muscle relaxation, and recovery. "
                         "Glycinate form has superior bioavailability and minimal GI distress.",
        },
        {
            "name": "Zinc",
            "dose": "15-30mg/day",
            "timing": "With dinner (away from calcium)",
            "evidence": "B",
            "rationale": "Supports testosterone production and immune function. "
                         "Common deficiency in athletes who sweat heavily.",
        },
    ],
    "bulk": [
        {
            "name": "Ashwagandha KSM-66",
            "dose": "600mg/day",
            "timing": "Morning with breakfast",
            "evidence": "B",
            "rationale": "Adaptogen that may support testosterone (+15% in studies), reduce cortisol, "
                         "and improve recovery. Most benefit in a caloric surplus.",
        },
    ],
    "lean_bulk": [
        {
            "name": "Ashwagandha KSM-66",
            "dose": "600mg/day",
            "timing": "Morning with breakfast",
            "evidence": "B",
            "rationale": "Same as bulk phase — adaptogenic support during controlled surplus.",
        },
    ],
    "cut": [
        {
            "name": "Caffeine",
            "dose": "3-6 mg/kg body weight",
            "timing": "30-60 min pre-workout",
            "evidence": "A",
            "rationale": "Ergogenic aid: improves strength, endurance, and fat oxidation during deficit. "
                         "Cycle off 2 weeks before peak week to resensitize.",
        },
        {
            "name": "EAAs (Essential Amino Acids)",
            "dose": "10-15g",
            "timing": "Intra-workout (sip throughout session)",
            "evidence": "B",
            "rationale": "Provides anti-catabolic amino acid signal during training in a deficit. "
                         "More effective than BCAAs alone. Contains leucine threshold.",
        },
        {
            "name": "L-Carnitine L-Tartrate",
            "dose": "2g/day",
            "timing": "With highest carb meal",
            "evidence": "B",
            "rationale": "Supports fatty acid transport into mitochondria. Requires insulin for uptake "
                         "— take with carbs. May reduce muscle damage markers.",
        },
    ],
    "peak": [
        {
            "name": "Glycerol (GlycerPump)",
            "dose": "1-1.5 g/kg with 500mL water",
            "timing": "Night before show + morning of show",
            "evidence": "B",
            "rationale": "Hyperhydration agent — pulls water intracellularly for muscle fullness "
                         "while reducing subcutaneous water. Use AFTER water restriction begins.",
        },
        {
            "name": "Dandelion Root Extract",
            "dose": "500mg",
            "timing": "Show morning (6 hours before stage)",
            "evidence": "C",
            "rationale": "Mild natural diuretic. Traditional use in bodybuilding. "
                         "Evidence is weak but risk is low. Do NOT use prescription diuretics.",
        },
    ],
    "restoration": [
        {
            "name": "Digestive Enzymes",
            "dose": "With each meal",
            "timing": "Beginning of meal",
            "evidence": "B",
            "rationale": "Post-show GI system may be compromised from extended restriction. "
                         "Enzymes support nutrient absorption during reverse diet.",
        },
    ],
}


def get_supplement_protocol(phase: str) -> list[dict]:
    """Return the recommended supplement stack for the given phase.

    Always includes 'all_phases' base stack plus phase-specific additions.
    """
    phase_key = phase.strip().lower()
    base = list(SUPPLEMENT_PROTOCOLS.get("all_phases", []))
    phase_specific = SUPPLEMENT_PROTOCOLS.get(phase_key, [])
    return base + phase_specific


def get_all_protocols() -> dict[str, list[dict]]:
    """Return the full protocol map for UI display."""
    return dict(SUPPLEMENT_PROTOCOLS)
