from __future__ import annotations

import json
from pathlib import Path

from railwaystation import BackwardConstructionAlgorithm, DataProvider


BASE_DIR = Path(__file__).resolve().parents[1]
CSHARP_ARTIFACT_DIR = BASE_DIR / "RailwayStation_V2.Console" / "bin" / "Debug" / "net10.0"
DATA_DIR = CSHARP_ARTIFACT_DIR / "Data"
RESULT_DIR = CSHARP_ARTIFACT_DIR / "Result"

SAMPLE_NAMES = [
    "2025-09-04-noon",
    "2025-09-08-noon",
    "2025-09-08-afternoon",
    "2025-09-09-noon",
    "2025-11-04-noon",
    "2025-11-04-afternoon",
    "2025-11-05-noon",
    "2025-11-05-afternoon",
    "2025-11-06-noon",
    "2025-11-06-afternoon",
    "2025-11-07-noon",
    "2025-11-10-noon",
    "2025-11-10-afternoon",
    "2025-11-11-noon",
    "2025-12-08-noon",
    "2025-12-08-afternoon",
    "2025-12-09-noon",
    "2025-12-09-afternoon",
]


def build_python_operation_signatures(sample_name: str) -> list[dict[str, object]]:
    distance_matrix, track_line_capacity = DataProvider.get_map_info(str(DATA_DIR / "map.xlsx"))
    track_lines = DataProvider.init_track_lines(track_line_capacity)
    cars = DataProvider.init_cars(track_lines, str(DATA_DIR / f"{sample_name}.xlsx"))
    operations = BackwardConstructionAlgorithm(track_lines, cars, distance_matrix).run()
    return [
        {
            "line": op.line_name,
            "action": op.action.value,
            "cars": [car.no for car in op.move_cars],
        }
        for op in operations
    ]


def build_csharp_operation_signatures(sample_name: str) -> list[dict[str, object]]:
    result_path = RESULT_DIR / f"ResultJson_{sample_name}.json"
    operations = json.loads(result_path.read_text())
    return [
        {
            "line": op["LineName"],
            "action": op["Action"],
            "cars": [car["No"] for car in op["MoveCars"]],
        }
        for op in operations
    ]


def compare_sample(sample_name: str) -> None:
    py_ops = build_python_operation_signatures(sample_name)
    cs_ops = build_csharp_operation_signatures(sample_name)
    assert len(py_ops) == len(cs_ops), f"{sample_name}: operation count mismatch {len(py_ops)} != {len(cs_ops)}"
    for index, (py_op, cs_op) in enumerate(zip(py_ops, cs_ops), start=1):
        assert py_op == cs_op, f"{sample_name}: operation #{index} mismatch\npy={py_op}\ncs={cs_op}"


def test_all_bundled_samples_match_csharp_artifacts() -> None:
    for sample_name in SAMPLE_NAMES:
        compare_sample(sample_name)
