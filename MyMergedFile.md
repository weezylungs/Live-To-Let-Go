{
"version": "GL-SALVAGE-1.0",
"source": ["Clinical-Plug-and-Play-v13.3", "Protocol-21G-v4.0"],
"metadata": {
"author": "Operator",
"created_utc": "2025-08-13T00:00:00Z",
"notes": "Merged salvage: risk tiers + modularity (Clinical), command ladder + counters + post-bellum (21-G)."
},

"standing_orders": {
"assume_adversarial_intent": true,
"maintain_optics_x": true,
"no_catharsis_no_confession": true,
"protect_third_parties": true,
"internal_firewall_profile": "Resilient_v6"
},

"defined_end_states": [
"strategic_neutrality",
"institutional_clearance",
"narrative_collapse",
"irrelevance_confirmed"
],

"escalation_ladder": [
{"level": 0, "name": "ambient_pings"},
{"level": 1, "name": "emotional_feelers"},
{"level": 2, "name": "grief_or_guilt_vectoring"},
{"level": 3, "name": "direct_contact_with_hook"},
{"level": 4, "name": "legal_or_narrative_redirection"},
{"level": 5, "name": "public_narrative_or_ambush"}
],

"severity_bands": [
{"band": "S0", "threshold": [0, 9], "directive_cap": "ARCHIVE"},
{"band": "S1", "threshold": [10, 19], "directive_cap": "ECHO_ONLY"},
{"band": "S2", "threshold": [20, 34], "directive_cap": "GHOST_FENCE_OK"},
{"band": "S3", "threshold": [35, 54], "directive_cap": "MIRAGE_OK"},
{"band": "S4", "threshold": [55, 100], "directive_cap": "BLACKOUT_OR_HIGH_ALERT"}
],

"scam_triggers": {
"context_timing": ["late_night_ping", "anniversary_bait", "court_adjacent_timing"],
"strategic_omission": ["missing_key_facts", "selective_memory", "non-answer"],
"performative_acts": ["public_remorse", "third_party_signal"],
"lexical_style": ["hedges", "intense_affect_mismatch", "legalese_without_facts"],
"narrative_framing": ["recast_events", "false_equivalence"],
"tactics": ["darvo", "guilt_hook", "urgency_clock"],
"channel_mgmt": ["mutuals_route", "new_number_drop", "platform_shift"],
"intent": ["damage_control_probe", "reputation_sanitise"]
},

"mti_features": {
"weights": {
"scam_hits": 3,
"affect_mismatch": 4,
"demand_presence": 5,
"third_party_reference": 4,
"legalese_without_fact": 5,
"timing_flag": 3,
"history_risk_score": 1,
"rate_of_contact": 2
},
"caps": {
"recent_court_window_bonus": 6,
"repeat_probe_bonus": 5,
"cooldown_decay_per_day": 2
}
},

"mti_routing": [
{"if_band": "S0", "route": "ARCHIVE"},
{"if_band": "S1", "route": "ECHO"},
{"if_band": "S2", "route": "GHOST_FENCE"},
{"if_band": "S3", "route": "MIRAGE"},
{"if_band": "S4", "route": "BLACKOUT_OR_HIGH_ALERT"}
],

"counter_protocols": {
"BLACKOUT": {
"purpose": "Containment",
"rules": {"reply": "none", "block": "allowed", "log": true, "cooldown_h": 168}
},
"ECHO": {
"purpose": "Neutral acknowledgement",
"assets": ["Received and logged.", "Acknowledged."],
"rules": {"reply_once": true, "delay_h": 24, "no_threading": true}
},
"DEFENSIVE_DOCUMENTATION": {
"purpose": "Formal record",
"rules": {"forward_to_formal_support": false, "internal_log_only": true}
},
"GHOST_FENCE": {
"purpose": "Selective info to allies",
"rules": {"notify_allies": true, "ally_list_ref": "pre_vetted_allies", "no_source_reply": true}
},
"MIRAGE": {
"purpose": "Strategic ambiguity",
"assets": ["I have pre-existing commitments and will review this later."],
"rules": {"truthy_only": true, "short_form": true, "no_followup": true}
},
"HIGH_ALERT": {
"purpose": "Escalated threat",
"rules": {"auto_forward_legal": true, "user_contact_locked": true, "listen_only_h": 24}
}
},

"playbook_match": [
{"archetype": "martyr", "preferred": ["ECHO", "BLACKOUT"]},
{"archetype": "administrator", "preferred": ["MIRAGE", "GHOST_FENCE"]},
{"archetype": "historian", "preferred": ["BLACKOUT", "DEFENSIVE_DOCUMENTATION"]},
{"archetype": "mirror", "preferred": ["BLACKOUT", "MIRAGE"]}
],

"routing_logic": [
{
"name": "Primary-MTI",
"when": "always",
"action": "route_by_mti_band"
},
{
"name": "Playbook-Override",
"when": "archetype_detected && mti_band in ['S2','S3']",
"action": "prefer_playbook_match"
},
{
"name": "High-Alert-Gate",
"when": "direct_threat || legal_demand || doxxing_signal",
"action": "HIGH_ALERT"
}
],

"termination_protocol": {
"enter_on_end_state": true,
"hard_sunset_days": 30,
"greylist_tools": ["BLACKOUT", "MIRAGE", "GHOST_FENCE"],
"reactivation_requirements": ["new_case_id", "risk_recalibration", "two_key_confirm"]
},

"calibration_reset": {
"on_termination": {
"mti_decay_to": "S0",
"history_risk_score_decay_days": 180
}
},

"actors": {
"formal_support": ["legal_counsel_primary", "legal_counsel_backup"],
"pre_vetted_allies": ["ally_1", "ally_2"]
},

"logging": {
"schema": {
"case_id": "string",
"msg_id": "string",
"ts_iso": "string",
"channel": "string",
"mti_score": "int",
"mti_band": "string",
"scam_hits": "array<string>",
"archetype": "string|null",
"route": "string",
"pas_executed": "string",
"cooldown_until": "string|null"
},
"export": {"format": "jsonl", "rotate_days": 30}
}
}

