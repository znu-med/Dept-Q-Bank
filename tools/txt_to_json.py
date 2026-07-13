#!/usr/bin/env python3
"""
txt_to_json.py — Dept. Q. Bank converter
=========================================
Turns a plain-text batch of professor guidance questions into JSON that
matches this repo's question schema, and merges it into the correct
data/<MODULE>/<exam_type>/<subject>/<topic>.json file.

This is a LOCAL DEV TOOL ONLY. It is never loaded by the website — it's
just a script you (or Claude) run on your machine to save you from
hand-typing JSON.

--------------------------------------------------------------------
INPUT FORMAT (plain text, not code)
--------------------------------------------------------------------
Questions are separated by one or more blank lines. Each question is:

    <question text, may span multiple lines>
    A) <option>
    B) <option>
    C) <option>
    D) <option>
    Answer: B

Option markers accept "A)", "A.", "A:", or "a)" etc.
Answer line accepts "Answer:", "Ans:", "Correct:" (case-insensitive).

If you (the professor's key) are unsure of the answer but have a guess,
mark it with a trailing "?" — e.g. "Answer: B?" — and the question will
still be included but flagged answerVerified: false in the JSON, with
a small "Unconfirmed answer" badge shown in the app.

If a question has NO answer at all (truly unknown), leave the Answer
line as "Answer: ?" — that question will be SKIPPED from the JSON and
listed at the end so you don't silently publish a guessed answer.

--------------------------------------------------------------------
USAGE
--------------------------------------------------------------------
    python3 tools/txt_to_json.py <input.txt> <target.json> [--professor "Dr. Name"]

Example:
    python3 tools/txt_to_json.py batch1.txt \\
        data/CNS/final_exam/anatomy/brainstem.json \\
        --professor "Dr. Hassan"

- <target.json> is created (as {"questions": []}) if it doesn't exist yet,
  including any missing parent folders.
- New question ids auto-increment from the highest existing id in that file.
- Use --dry-run to preview the JSON without writing anything.
"""

import argparse
import json
import re
import sys
from pathlib import Path

LETTERS = "ABCDEFGH"

OPTION_RE = re.compile(r"^\s*([A-Ha-h])[\)\.\:]\s+(.*\S)\s*$")
ANSWER_RE = re.compile(
    r"^\s*(?:answer|ans|correct)\s*[:\-]\s*([A-Ha-h])\s*(\?)?\s*$",
    re.IGNORECASE,
)


def parse_blocks(raw_text):
    """Split the raw text into question blocks separated by blank lines."""
    lines = raw_text.replace("\r\n", "\n").split("\n")
    blocks, current = [], []
    for line in lines:
        if line.strip() == "":
            if current:
                blocks.append(current)
                current = []
        else:
            current.append(line)
    if current:
        blocks.append(current)
    return blocks


def parse_question_block(block, block_num):
    """
    Parse one block of lines into a question dict, or return
    (None, reason) if it can't be parsed / has no confirmed answer.
    """
    question_lines = []
    options = []
    answer_letter = None
    answer_uncertain = False

    for line in block:
        opt_match = OPTION_RE.match(line)
        ans_match = ANSWER_RE.match(line)
        if ans_match:
            answer_letter = ans_match.group(1).upper()
            answer_uncertain = bool(ans_match.group(2))
        elif opt_match:
            options.append(opt_match.group(2).strip())
        else:
            if not options:  # still in the question text
                question_lines.append(line.strip())

    question_text = " ".join(l for l in question_lines if l).strip()

    if not question_text:
        return None, f"Block {block_num}: couldn't find question text — skipped."
    if len(options) < 2:
        return None, f"Block {block_num}: fewer than 2 options found — skipped. ({question_text[:60]}...)"
    if answer_letter is None or answer_letter == "?":
        return None, f"Block {block_num}: no answer given — skipped, needs manual answer. ({question_text[:60]}...)"

    answer_index = LETTERS.index(answer_letter)
    if answer_index >= len(options):
        return None, f"Block {block_num}: answer '{answer_letter}' has no matching option — skipped."

    q = {
        "question": question_text,
        "options": options,
        "answer": answer_index,
        "explanation": "",
    }
    if answer_uncertain:
        q["answerVerified"] = False
    return q, None


def infer_meta(path: Path):
    """
    Infer {module, examType, subject, subSubject} from a path shaped like
    data/<MODULE>/<exam_type>/<subject>/<topic>.json
    Falls back gracefully if the path doesn't have that many parts.
    """
    parts = path.parts
    try:
        data_idx = parts.index("data")
    except ValueError:
        data_idx = None

    if data_idx is not None and len(parts) >= data_idx + 5:
        module, exam_type, subject = parts[data_idx + 1: data_idx + 4]
        sub_subject = path.stem
        return {"module": module, "examType": exam_type, "subject": subject, "subSubject": sub_subject}
    return None


def load_or_init_target(path: Path):
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        if "questions" not in data:
            data["questions"] = []
    else:
        meta = infer_meta(path)
        data = {"meta": meta, "questions": []} if meta else {"questions": []}
    return data


def next_id(existing_questions):
    if not existing_questions:
        return 1
    return max((q.get("id", 0) for q in existing_questions), default=0) + 1


def main():
    ap = argparse.ArgumentParser(description="Convert a professor guidance-question .txt batch into repo-compatible JSON.")
    ap.add_argument("input_txt", help="Path to the plain-text question batch")
    ap.add_argument("target_json", help="Path to the data/.../topic.json file this batch belongs to")
    ap.add_argument("--professor", default=None, help="Professor name to attribute this batch to")
    ap.add_argument("--dry-run", action="store_true", help="Print the resulting JSON instead of writing it")
    args = ap.parse_args()

    in_path = Path(args.input_txt)
    out_path = Path(args.target_json)

    if not in_path.exists():
        print(f"Input file not found: {in_path}", file=sys.stderr)
        sys.exit(1)

    raw_text = in_path.read_text(encoding="utf-8")
    blocks = parse_blocks(raw_text)

    if not blocks:
        print("No question blocks found in input file (is it empty?).", file=sys.stderr)
        sys.exit(1)

    parsed, warnings = [], []
    for i, block in enumerate(blocks, start=1):
        q, warning = parse_question_block(block, i)
        if q:
            if args.professor:
                q["professor"] = args.professor
            parsed.append(q)
        else:
            warnings.append(warning)

    if not parsed:
        print("No questions could be parsed. Nothing to write.", file=sys.stderr)
        for w in warnings:
            print(f"  ⚠ {w}", file=sys.stderr)
        sys.exit(1)

    data = load_or_init_target(out_path)
    existing = data["questions"]
    next_i = next_id(existing)
    for q in parsed:
        q_ordered = {"id": next_i}
        q_ordered.update(q)
        existing.append(q_ordered)
        next_i += 1

    if isinstance(data.get("meta"), dict):
        data["meta"]["totalQuestions"] = len(existing)

    output_text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"

    if args.dry_run:
        print(output_text)
    else:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output_text, encoding="utf-8")
        print(f"✅ Added {len(parsed)} question(s) to {out_path}")

    if warnings:
        print(f"\n⚠ {len(warnings)} block(s) skipped — review and add manually:", file=sys.stderr)
        for w in warnings:
            print(f"  - {w}", file=sys.stderr)


if __name__ == "__main__":
    main()
