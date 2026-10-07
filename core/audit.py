# ============================================================
# DULB ENGINEERING QA POC - DRAWING DEFECT & COMPLIANCE AUDIT
# ============================================================

import datetime


def generate_audit_report(
    results,
    evidence_store,
    old_data,
    new_data,
    old_filename="Old_Drawing.pdf",
    new_filename="New_Drawing.pdf",
):
    """
    Analyzes verification results, geometric deltas, and consultant markups
    to generate an exhaustive Drawing Defect Audit Report.
    """
    total = max(len(results), 1)
    resolved = sum(1 for r in results if r["Status"] == "Resolved")
    partial = sum(1 for r in results if r["Status"] == "Partially Resolved")
    not_resolved = sum(1 for r in results if r["Status"] == "Not Resolved")
    cannot_verify = sum(1 for r in results if r["Status"] == "Cannot Verify")

    # Compliance Score calculation
    compliance_score = round(((resolved + (0.5 * partial)) / total) * 100, 1)

    if compliance_score == 100.0:
        verdict = "PASS - CLEARED FOR RESUBMISSION"
        verdict_badge = "[PASSED]"
        risk_level = "LOW RISK"
    elif compliance_score >= 70.0:
        verdict = "CONDITIONAL PASS - RECTIFY PUNCH LIST BEFORE RESUBMISSION"
        verdict_badge = "[CONDITIONAL]"
        risk_level = "MEDIUM RISK"
    else:
        verdict = "AUDIT FAILED - REJECTED FOR RESUBMISSION DUE TO DEFICIENCIES"
        verdict_badge = "[FAILED]"
        risk_level = "HIGH RISK"

    findings = []
    cad_action_punchlist = []

    for r in results:
        cid = r["Comment ID"]
        status = r["Status"]
        comment_text = r["Consultant Comment"]
        ev = evidence_store.get(cid, {})
        comp = ev.get("comparison", {})
        similarity = comp.get("visual_similarity")
        old_vecs = comp.get("old_vectors", 0)
        new_vecs = comp.get("new_vectors", 0)

        finding = {
            "comment_id": cid,
            "page": r["Page"],
            "category": r.get("Category") or "General Drafting",
            "affected_item": r.get("Affected Item") or "Drawing Element",
            "status": status,
            "severity": "",
            "deficiency_summary": "",
            "root_cause": "",
            "auditor_action": "",
            "visual_similarity": round(similarity, 3) if similarity is not None else None,
            "vector_delta": new_vecs - old_vecs,
        }

        if status == "Not Resolved":
            finding["severity"] = "CRITICAL (Blocking)"
            finding["deficiency_summary"] = (
                f"Consultant requirement was completely unfulfilled in the new revision. "
                f"Expected: '{r.get('Required Rectification') or comment_text}'."
            )
            finding["root_cause"] = r.get("Reason") or "Draftsman failed to update linework/text."
            finding["auditor_action"] = (
                f"CAD Drafting must immediately update drawing at Page {r['Page']}: "
                f"Rectify '{r.get('Affected Item') or 'element'}' according to IFC standard."
            )
            findings.append(finding)
            cad_action_punchlist.append({
                "item_id": cid,
                "priority": "P1 - Critical",
                "page": r["Page"],
                "target": r.get("Affected Item") or "Element",
                "action": finding["auditor_action"],
            })

        elif status == "Partially Resolved":
            finding["severity"] = "MAJOR (High Risk)"
            finding["deficiency_summary"] = (
                f"Partial modification detected, but consultant requirement is incomplete. "
                f"Missing specifications or compliance tags."
            )
            finding["root_cause"] = r.get("Reason") or "Change initiated but missing annotations/tags."
            finding["auditor_action"] = (
                f"Complete remaining rectification on Page {r['Page']}: "
                f"Verify tag, sizing, and details for '{r.get('Affected Item')}'."
            )
            findings.append(finding)
            cad_action_punchlist.append({
                "item_id": cid,
                "priority": "P2 - Major",
                "page": r["Page"],
                "target": r.get("Affected Item") or "Element",
                "action": finding["auditor_action"],
            })

        elif status == "Cannot Verify":
            finding["severity"] = "VERIFICATION GAP (Medium Risk)"
            finding["deficiency_summary"] = (
                f"Insufficient unambiguous evidence in revised drawing. "
                f"Consultant note may reference an external schedule, detail, or unextracted layer."
            )
            finding["root_cause"] = r.get("Reason") or "Evidence ambiguous or requires physical engineer inspection."
            finding["auditor_action"] = (
                f"Lead Engineer must perform manual inspection of Page {r['Page']} "
                f"against consultant comments and referenced details."
            )
            findings.append(finding)
            cad_action_punchlist.append({
                "item_id": cid,
                "priority": "P3 - Verification",
                "page": r["Page"],
                "target": r.get("Affected Item") or "Element",
                "action": finding["auditor_action"],
            })

    # Drawing-level geometry and discrepancy audit
    cad_discrepancies = []
    max_pages = max(old_data["page_count"], new_data["page_count"])
    for p in range(1, max_pages + 1):
        old_p = next((page for page in old_data["pages"] if page["page"] == p), None)
        new_p = next((page for page in new_data["pages"] if page["page"] == p), None)
        v_old = len(old_p["vectors"]) if old_p else 0
        v_new = len(new_p["vectors"]) if new_p else 0
        t_old = len(old_p["text"]["plain_text"]) if old_p else 0
        t_new = len(new_p["text"]["plain_text"]) if new_p else 0

        p_comments = [r for r in results if r["Page"] == p]
        if p_comments and v_old == v_new and t_old == t_new:
            cad_discrepancies.append({
                "page": p,
                "type": "Zero Revision Delta Warning",
                "detail": f"Page {p} has {len(p_comments)} consultant comment(s), but vector and character counts are identical between revisions.",
            })

    audit_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Generate formal markdown report text
    markdown_lines = [
        "# ============================================================",
        "# DULB ENGINEERING DRAWING QUALITY & DEFECT AUDIT REPORT",
        "# ============================================================",
        f"**Audit Timestamp:** {audit_timestamp}",
        f"**Old Revision File:** `{old_filename}`",
        f"**New Revision File:** `{new_filename}`",
        f"**Audited Comments Count:** {total}",
        f"**Audit Verdict:** {verdict_badge} — **{verdict}**",
        f"**Compliance Score:** {compliance_score}% ({risk_level})",
        "",
        "## 1. Executive Summary & Defect Breakdown",
        f"- **✅ Fully Resolved:** {resolved} ({round((resolved/total)*100, 1)}%)",
        f"- **❌ Not Resolved (Critical):** {not_resolved} ({round((not_resolved/total)*100, 1)}%)",
        f"- **🟠 Partially Resolved (Major):** {partial} ({round((partial/total)*100, 1)}%)",
        f"- **⚪ Cannot Verify (Gaps):** {cannot_verify} ({round((cannot_verify/total)*100, 1)}%)",
        "",
        "## 2. Drawing Non-Compliances & Defect Findings",
    ]

    if not findings:
        markdown_lines.append("No active defects detected. All audited consultant comments appear resolved.")
    else:
        for idx, f in enumerate(findings, 1):
            markdown_lines.extend([
                f"### Finding {idx}: [{f['severity']}] {f['comment_id']} (Page {f['page']})",
                f"- **Affected Item:** {f['affected_item']} (Category: {f['category']})",
                f"- **Deficiency Summary:** {f['deficiency_summary']}",
                f"- **Root Cause:** {f['root_cause']}",
                f"- **Required Action:** {f['auditor_action']}",
                "",
            ])

    if cad_discrepancies:
        markdown_lines.extend([
            "## 3. CAD Geometry & Drawing Discrepancies",
        ])
        for cd in cad_discrepancies:
            markdown_lines.append(f"- **Page {cd['page']} [{cd['type']}]:** {cd['detail']}")
        markdown_lines.append("")

    markdown_lines.extend([
        "## 4. CAD Drafting Correction Punch-List",
        "The CAD drafting team must complete the following punch-list items prior to client/consultant resubmission:",
    ])

    if not cad_action_punchlist:
        markdown_lines.append("No punch-list actions required.")
    else:
        for p in cad_action_punchlist:
            markdown_lines.append(f"- [ ] **[{p['priority']}] Page {p['page']} ({p['target']}):** {p['action']}")

    markdown_lines.extend([
        "",
        "---",
        "**Auditor Disclaimer:**",
        "This audit report is generated by the DULB Engineering QA System using spatial drawing extraction and AI verification. Final authority and legal stamping responsibility remains with the Professional Engineer of Record.",
    ])

    audit_text = "\n".join(markdown_lines)

    return {
        "timestamp": audit_timestamp,
        "compliance_score": compliance_score,
        "verdict": verdict,
        "verdict_badge": verdict_badge,
        "risk_level": risk_level,
        "counts": {
            "total": total,
            "resolved": resolved,
            "not_resolved": not_resolved,
            "partial": partial,
            "cannot_verify": cannot_verify,
            "critical_defects": not_resolved,
            "major_deficiencies": partial,
            "verification_gaps": cannot_verify,
        },
        "findings": findings,
        "punchlist": cad_action_punchlist,
        "cad_discrepancies": cad_discrepancies,
        "report_markdown": audit_text,
    }
