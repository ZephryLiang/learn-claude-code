#!/usr/bin/env python3
"""Resume quality validation script.

Usage:
    python skills/resume-editing/scripts/validate.py --resume <path>

Checks the edited resume against a comprehensive quality checklist.
Returns pass/fail per check with actionable messages.
"""

import argparse
import json
import os
import re
import sys


def parse_args():
    parser = argparse.ArgumentParser(description="Validate resume quality")
    parser.add_argument("--resume", required=True, help="Path to the edited resume file")
    parser.add_argument("--verbose", action="store_true", help="Show all checks including passes")
    return parser.parse_args()


def check(condition: bool, label: str, tip: str = "") -> dict:
    return {
        "pass": condition,
        "label": label,
        "tip": tip if not condition else "",
    }


def main():
    args = parse_args()

    if not os.path.exists(args.resume):
        print(json.dumps({"error": f"File not found: {args.resume}"}))
        sys.exit(1)

    with open(args.resume, "r", encoding="utf-8") as f:
        content = f.read()

    lines = content.split("\n")
    results = []

    # --- Structure checks ---
    results.append(check(
        "Responsible for" not in content.lower(),
        "No 'responsible for' weak openers",
        'Replace "Responsible for X" with a strong verb: "Built", "Designed", "Led", "Implemented"',
    ))
    results.append(check(
        "Involved in" not in content.lower(),
        "No 'involved in' weak openers",
        'Replace "Involved in X" with direct contribution language',
    ))
    results.append(check(
        "Worked on" not in content.lower(),
        "No 'worked on' weak openers",
        'Replace "Worked on X" with a specific action verb',
    ))
    results.append(check(
        "I " not in content and "My " not in content,
        "No first-person pronouns",
        "Resumes use implied first-person. Remove 'I', 'my', 'we'.",
    ))

    # --- Contact info ---
    has_email = bool(re.search(r"[\w.]+@[\w.]+\.\w+", content))
    has_phone = bool(re.search(r"[\d\-\(\)\s+]{7,}", content))
    results.append(check(has_email, "Email address present", "Add email contact information"))
    results.append(check(has_phone, "Phone number present", "Add phone contact information"))

    # --- Quantification ---
    bullets = re.findall(r"^\s*[-*+]\s(.+)", content, re.MULTILINE)
    quantified_bullets = [
        b for b in bullets
        if re.search(r"\d+%|\d+x\b|\$\d+|\d+\s*ms|\d+\s*s(ec)?\b|\d+\s*min|\d+K|\d+M|\d+/\d+", b)
    ]
    if bullets:
        rate = len(quantified_bullets) / len(bullets)
        results.append(check(
            rate >= 0.6,
            f"Quantification rate: {len(quantified_bullets)}/{len(bullets)} ({rate:.0%}) — target: ≥60%",
            f"Add metrics to {int(len(bullets) * 0.6 - len(quantified_bullets))} more bullet points (%, $, times, counts, etc.)",
        ))
    else:
        results.append(check(False, "Found bullet points", "No bullet points detected. Bullets are essential for scannability."))

    # --- Length checks ---
    results.append(check(
        len(lines) <= 100,
        f"Resume length: {len(lines)} lines (reasonable)",
        "Consider condensing. Target: 50-80 lines for 1 page, max 120 for 2 pages.",
    ))

    # Find overly long lines (potential formatting issues)
    long_lines = [i for i, l in enumerate(lines, 1) if len(l) > 120 and l.strip().startswith(("-", "*", "+"))]
    results.append(check(
        len(long_lines) == 0,
        "No bullet wraps to 3+ lines",
        f"Lines {long_lines} are too long. Keep bullets to 1-2 lines max.",
    ))

    # --- Section header checks ---
    required_sections = ["experience", "skills", "education"]
    found_sections = {
        s: bool(re.search(rf"^#{{1,3}}\s*{re.escape(s)}", content, re.IGNORECASE | re.MULTILINE))
        for s in required_sections
    }
    for section, present in found_sections.items():
        results.append(check(
            present,
            f"Required section: {section.capitalize()}",
            f"Add a '{section.capitalize()}' section heading",
        ))

    # --- Keywords from context ---
    weak_verbs = ["is", "was", "were", "has", "have", "had"]
    for wv in weak_verbs:
        # Check in bullet context specifically
        for bullet in bullets:
            if re.search(rf"\b{re.escape(wv)}\b", bullet, re.IGNORECASE):
                # Often valid in past tense context, just flag
                pass

    # --- ATS-specific checks ---
    results.append(check(
        not re.search(r"<table", content, re.IGNORECASE),
        "No HTML tables (ATS safe)",
        "Remove tables — most ATS parsers cannot read them.",
    ))

    # Check for dates in bullets (employment dates should be present)
    date_in_bullets = any(
        re.search(r"(19|20)\d{2}\s*[-–—to]+\s*(19|20)\d{2}", l)
        for l in lines[:30]  # Check first 30 lines for dates near top
    )
    results.append(check(
        date_in_bullets,
        "Date ranges present for experience",
        "Add date ranges for each position (YYYY—YYYY or YYYY.MM—YYYY.MM)",
    ))

    # --- Summary ---
    passes = sum(1 for r in results if r["pass"])
    total = len(results)

    print(f"\n{'=' * 55}")
    print(f"  Resume Quality Validation Results")
    print(f"{'=' * 55}")
    print(f"  {passes}/{total} checks passed ({passes / total:.0%})\n")

    if args.verbose:
        for r in results:
            status = "✅" if r["pass"] else "❌"
            print(f"  {status}  {r['label']}")
            if not r["pass"] and r["tip"]:
                print(f"       Tip: {r['tip']}")
    else:
        failures = [r for r in results if not r["pass"]]
        if failures:
            print("  Failed checks:")
            for f in failures:
                print(f"    ❌  {f['label']}")
                if f["tip"]:
                    print(f"         Tip: {f['tip']}")
        else:
            print("  ✅ All checks passed!")

    print(f"{'=' * 55}")

    # Return exit code
    return 0 if all(r["pass"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
