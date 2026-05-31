from __future__ import annotations

import argparse
import copy
import json
from collections import Counter
from pathlib import Path
from typing import Any


def load_operations(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_for_compare(operations: list[dict[str, Any]], apply_csharp_export_postprocess: bool) -> list[dict[str, Any]]:
    normalized = copy.deepcopy(operations)
    if not apply_csharp_export_postprocess:
        return normalized
    for op in normalized:
        op["TrainCars"].reverse()
        if op["Action"] == "Put":
            op["MoveCars"].reverse()
    return normalized


def move_car_nos(operation: dict[str, Any]) -> list[str]:
    return [car["No"] for car in operation["MoveCars"]]


def op_signature(operation: dict[str, Any]) -> tuple[str, str, tuple[str, ...]]:
    return operation["LineName"], operation["Action"], tuple(move_car_nos(operation))


def op_signature_set(operation: dict[str, Any]) -> tuple[str, str, tuple[tuple[str, int], ...]]:
    counter = Counter(move_car_nos(operation))
    return operation["LineName"], operation["Action"], tuple(sorted(counter.items()))


def classify_diffs(py_ops: list[dict[str, Any]], cs_ops: list[dict[str, Any]]) -> dict[str, Any]:
    min_len = min(len(py_ops), len(cs_ops))
    summary = Counter()
    details: list[dict[str, Any]] = []
    first_diff_index: int | None = None

    for index in range(min_len):
        py_op = py_ops[index]
        cs_op = cs_ops[index]
        py_sig = op_signature(py_op)
        cs_sig = op_signature(cs_op)
        if py_sig == cs_sig:
            summary["exact"] += 1
            continue

        if first_diff_index is None:
            first_diff_index = index + 1

        py_set_sig = op_signature_set(py_op)
        cs_set_sig = op_signature_set(cs_op)

        if py_op["LineName"] == cs_op["LineName"] and py_op["Action"] == cs_op["Action"] and py_set_sig == cs_set_sig:
            diff_type = "same_line_action_same_cars_diff_order"
        elif py_op["LineName"] == cs_op["LineName"] and py_op["Action"] == cs_op["Action"]:
            diff_type = "same_line_action_diff_cars"
        else:
            diff_type = "different_step_identity"
        summary[diff_type] += 1
        details.append(
            {
                "index": index + 1,
                "type": diff_type,
                "python": {
                    "line": py_op["LineName"],
                    "action": py_op["Action"],
                    "cars": move_car_nos(py_op),
                },
                "csharp": {
                    "line": cs_op["LineName"],
                    "action": cs_op["Action"],
                    "cars": move_car_nos(cs_op),
                },
            }
        )

    return {
        "python_len": len(py_ops),
        "csharp_len": len(cs_ops),
        "first_diff_index": first_diff_index,
        "summary": dict(summary),
        "details": details,
    }


def build_usage_summary(operations: list[dict[str, Any]]) -> dict[str, Any]:
    line_action_counter = Counter((op["LineName"], op["Action"]) for op in operations)
    moved_refs = [car["No"] for op in operations for car in op["MoveCars"]]
    return {
        "operation_count": len(operations),
        "unique_move_cars": len(set(moved_refs)),
        "total_move_refs": len(moved_refs),
        "top_line_actions": [
            {"line": line, "action": action, "count": count}
            for (line, action), count in line_action_counter.most_common(20)
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare Python result JSON and C# result JSON.")
    parser.add_argument("--python-result", required=True, type=Path)
    parser.add_argument("--csharp-result", required=True, type=Path)
    parser.add_argument("--apply-csharp-export-postprocess", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    py_ops = load_operations(args.python_result)
    cs_ops = load_operations(args.csharp_result)
    py_ops = normalize_for_compare(py_ops, args.apply_csharp_export_postprocess)

    report = {
        "python_result": str(args.python_result),
        "csharp_result": str(args.csharp_result),
        "apply_csharp_export_postprocess": args.apply_csharp_export_postprocess,
        "diff": classify_diffs(py_ops, cs_ops),
        "python_usage": build_usage_summary(py_ops),
        "csharp_usage": build_usage_summary(cs_ops),
    }

    output_text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(output_text, encoding="utf-8")
    print(output_text)


if __name__ == "__main__":
    main()
