"""Checks on the generated Power BI project that do not need Power BI Desktop."""
import json
import re

import pytest

from src import build_powerbi_project as pbi
from src.paths import POWERBI_DIR


@pytest.fixture(scope="module")
def measures():
    return pbi.parse_measures()


def test_every_measure_in_the_dax_file_is_parsed(measures):
    text = (POWERBI_DIR / "measures.dax").read_text(encoding="utf-8")
    declared = re.findall(r"^\s*MEASURE\s+'_Measures'\[(.+?)\]", text, flags=re.M)
    assert [m["name"] for m in measures] == declared
    assert len(set(declared)) == len(declared)
    assert all(m["expression"] for m in measures)


def test_measures_only_reference_measures_that_exist(measures):
    names = {m["name"] for m in measures}
    for m in measures:
        body = "\n".join(m["expression"])
        body = re.sub(r'"[^"]*"', "", body)                  # drop string literals
        body = re.sub(r"[A-Za-z_]+\[[^\]]+\]", "", body)      # drop table[column]
        for ref in re.findall(r"\[([^\]@][^\]]*)\]", body):
            assert ref in names or ref == "Value", f"{m['name']} refers to unknown [{ref}]"


def test_no_dax_variable_uses_a_reserved_word(measures):
    # "cells" parses as a keyword in the Power BI engine and breaks the measure.
    reserved = {"cells", "measure", "table", "column", "define", "evaluate", "order", "return"}
    for m in measures:
        for var in re.findall(r"\bVAR\s+(\w+)", "\n".join(m["expression"])):
            assert var.lower() not in reserved, f"{m['name']} uses VAR {var}"


def test_every_formatted_measure_exists(measures):
    names = {m["name"] for m in measures}
    assert set(pbi.FORMAT_OF) <= names


def test_visuals_only_use_fields_that_exist(measures):
    names = {m["name"] for m in measures}
    columns = {(table, col[0]) for table, cols in pbi.TABLES.items() for col in cols}

    def walk(node):
        if isinstance(node, dict):
            if "Measure" in node and "Property" in node["Measure"]:
                assert node["Measure"]["Property"] in names, node["Measure"]["Property"]
            if "Column" in node and "Property" in node["Column"]:
                entity = node["Column"]["Expression"]["SourceRef"]["Entity"]
                assert (entity, node["Column"]["Property"]) in columns
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    seen = set()
    for _, _, builder in pbi.PAGES:
        for name, payload in builder():
            assert name not in seen, f"duplicate visual name {name}"
            seen.add(name)
            json.dumps(payload)  # must be serialisable
            walk(payload)
            pos = payload["position"]
            assert 0 <= pos["x"] and pos["x"] + pos["width"] <= 1280, f"{name} is off the canvas"
            assert 0 <= pos["y"] and pos["y"] + pos["height"] <= 720, f"{name} is off the canvas"
