#!/usr/bin/env python3
"""Resume editing environment setup script.

Usage:
    python skills/resume-editing/scripts/setup.py --resume <path> [--jd <path>]

Parses the resume (and optional JD), validates accessibility,
and prints a structured summary for the editor.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime


def parse_args():
    parser = argparse.ArgumentParser(description="Setup resume editing environment")
    parser.add_argument("--resume", required=True, help="Path to resume file")
    parser.add_argument("--jd", help="Path to job description file")
    return parser.parse_args()


def validate_path(path: str, label: str) -> str:
    if not os.path.exists(path):
        print(f"ERROR: {label} not found: {path}")
        sys.exit(1)
    ext = os.path.splitext(path)[1].lower()
    if ext not in (".md", ".txt", ".pdf", ".docx", ".tex"):
        print(f"WARNING: Unusual file extension '{ext}' for {label}")
    return path


def extract_sections(content: str):
    """Simple markdown section extraction."""
    sections = {}
    current_section = "preamble"
    sections[current_section] = []

    for line in content.split("\n"):
        header_match = re.match(r"^#{1,3}\s+(.+)", line)
        if header_match:
            current_section = header_match.group(1).strip()
            sections[current_section] = []
        else:
            sections[current_section].append(line)

    return {k: "\n".join(v).strip() for k, v in sections.items() if v}


def count_bullets(content: str) -> int:
    return len(re.findall(r"^\s*[-*+]\s", content, re.MULTILINE))


def count_quantified_bullets(content: str) -> int:
    patterns = [
        r"\d+%",
        r"\d+x\b",
        r"\$\d+",
        r"\d+\s*ms",
        r"\d+\s*s",
        r"\d+\s*min",
        r"\d+K",
        r"\d+M",
    ]
    count = 0
    for bullet in re.findall(r"^\s*[-*+]\s(.+)", content, re.MULTILINE):
        for pat in patterns:
            if re.search(pat, bullet):
                count += 1
                break
    return count


def weak_opener_check(content: str) -> list:
    weak = ["responsible for", "involved in", "participated in", "helped with", "worked on", "tasked with"]
    lines = content.split("\n")
    issues = []
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        for w in weak:
            if re.search(rf"^\s*[-*+]\s+.*?\b{re.escape(w)}\b", stripped, re.IGNORECASE):
                issues.append((i, w, stripped[:100]))
                break
    return issues


def main():
    args = parse_args()

    resume_path = validate_path(args.resume, "Resume")
    jd_path = validate_path(args.jd, "Job description") if args.jd else None

    # Read resume
    with open(resume_path, "r", encoding="utf-8") as f:
        resume_content = f.read()

    sections = extract_sections(resume_content)
    total_bullets = count_bullets(resume_content)
    quantified = count_quantified_bullets(resume_content)
    weak_openers = weak_opener_check(resume_content)

    # Read JD if provided
    jd_content = None
    if jd_path:
        with open(jd_path, "r", encoding="utf-8") as f:
            jd_content = f.read()

    output = {
        "resume": {
            "path": resume_path,
            "chars": len(resume_content),
            "lines": resume_content.count("\n") + 1,
            "sections": list(sections.keys()),
            "total_bullets": total_bullets,
            "quantified_bullets": quantified,
            "quantification_rate": f"{quantified}/{total_bullets} ({round(quantified / total_bullets * 100) if total_bullets else 0}%)",
            "weak_openers": len(weak_openers),
            "suggested_line_length": max(len(l) for l in resume_content.split("\n")) if resume_content else 0,
        },
        "recommendations": [],
    }

    # Auto-recommendations
    if output["resume"]["quantification_rate"]:
        rate = quantified / total_bullets
        if rate < 0.5:
            output["recommendations"].append("Low quantification rate. Add metrics to at least 60% of bullets.")
        elif rate < 0.8:
            output["recommendations"].append("Moderate quantification. Push for 80%+ quantified bullets.")

    if weak_openers:
        output["recommendations"].append(
            f"Found {len(weak_openers)} weak openers (responsible for, involved in, etc.) that need stronger action verbs."
        )

    if jd_content:
        output["jd"] = {
            "path": jd_path,
            "chars": len(jd_content),
            "lines": jd_content.count("\n") + 1,
        }

    print(json.dumps(output, indent=2, ensure_ascii=False))

    # Summary
    print(f"\n{'='*50}")
    print(f"📋 Resume Analysis Summary")
    print(f"{'='*50}")
    print(f"  File:     {resume_path}")
    print(f"  Sections: {', '.join(output['resume']['sections'])}")
    print(f"  Bullets:  {output['resume']['quantified_bullets']}")
    print(f"  Quant:    {output['resume']['quantification_rate']}")
    print(f"  Weak:     {output['resume']['weak_openers']} weak openers")
    if jd_content:
        print(f"  JD:       {jd_path}")
    if output["recommendations"]:
        print(f"\n  Recommendations:")
        for r in output["recommendations"]:
            print(f"    ⚠  {r}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
