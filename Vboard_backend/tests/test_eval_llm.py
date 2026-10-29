from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from unittest.mock import AsyncMock, patch

import pytest

from app.schemas.actions import Action
from scripts.eval_llm import (
    calculate_spark_cost,
    compute_percentile,
    load_eval_rows,
    normalize_text,
    print_confusion_matrix,
    print_summary_tables,
    run_evaluation,
    save_results_csv,
    score_row,
)


@dataclass
class DummyActionResult:
    action: Optional[Action]
    used_fallback: bool
    fallback_reason: Optional[str]
    elapsed_ms: float
    prompt_tokens: int
    completion_tokens: int
    cached_tokens: int = 0
    reasoning_tokens: int = 0


def test_calculate_spark_cost():
    # Prompt tokens = 1000, completion tokens = 500, cached = 0
    # uncached input: 1000 * 1.25 / 1e6 = 0.00125
    # output: 500 * 4.25 / 1e6 = 0.002125
    # total: 0.003375
    cost = calculate_spark_cost(1000, 500, 0)
    assert pytest.approx(cost, rel=1e-5) == 0.003375

    # With cached tokens: 1000 prompt (800 cached, 200 uncached), 200 completion
    # uncached input: 200 * 1.25 / 1e6 = 0.000250
    # cached input: 800 * 0.15 / 1e6 = 0.000120
    # output: 200 * 4.25 / 1e6 = 0.000850
    # total: 0.001220
    cost_cached = calculate_spark_cost(1000, 200, 800)
    assert pytest.approx(cost_cached, rel=1e-5) == 0.001220

    # Zero tokens
    assert calculate_spark_cost(0, 0, 0) == 0.0


def test_normalize_text():
    raw = "  Hello,   WORLD! It's a test...  "
    norm = normalize_text(raw)
    assert norm == "hello world it's a test"

    # Kannada and punctuation
    kannada_raw = "ನಾಳೆ, ನಾನು ಆಫೀಸ್ಗೆ ಬರುವುದಿಲ್ಲ!"
    kannada_norm = normalize_text(kannada_raw)
    assert "ನಾಳೆ" in kannada_norm
    assert "," not in kannada_norm
    assert "!" not in kannada_norm

    # Empty
    assert normalize_text("") == ""


def test_compute_percentile():
    assert compute_percentile([], 50.0) == 0.0
    assert compute_percentile([42.0], 95.0) == 42.0

    data = [10.0, 20.0, 30.0, 40.0, 50.0]
    assert compute_percentile(data, 50.0) == 30.0
    assert compute_percentile(data, 0.0) == 10.0
    assert compute_percentile(data, 100.0) == 50.0


def test_load_eval_rows_valid(tmp_path: Path):
    csv_file = tmp_path / "valid.csv"
    csv_file.write_text(
        "id,mix,box_text,spoken_text,expected_action,expected_find,"
        "expected_which,expected_text,notes\n"
        '1,English,"","hello world",insert,,last,"Hello world.",test note\n'
        '2,English,"old text","change old to new",replace,old,last,new,replace test\n'
        '3,English,"some text","make it shorter",rewrite,,last,"shorter",rewrite test\n'
        '4,English,"hello","change missing to new",none,,,,expect none\n',
        encoding="utf-8",
    )
    rows = load_eval_rows(csv_file)
    assert len(rows) == 4
    assert rows[0]["id"] == "1"
    assert rows[1]["expected_action"] == "replace"
    assert rows[3]["expected_action"] == "none"


def test_load_eval_rows_missing_columns(tmp_path: Path):
    csv_file = tmp_path / "missing_col.csv"
    csv_file.write_text("id,box_text,spoken_text\n1,a,b\n", encoding="utf-8")
    with pytest.raises(ValueError, match="CSV missing required columns"):
        load_eval_rows(csv_file)


def test_load_eval_rows_invalid_action(tmp_path: Path):
    csv_file = tmp_path / "invalid_action.csv"
    csv_file.write_text(
        "id,mix,box_text,spoken_text,expected_action,expected_find,"
        "expected_which,expected_text,notes\n"
        '1,English,"","hello",delete,,last,"Hello",bad action\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="invalid expected_action"):
        load_eval_rows(csv_file)


def test_load_eval_rows_replace_missing_which(tmp_path: Path):
    csv_file = tmp_path / "replace_missing_which.csv"
    csv_file.write_text(
        "id,mix,box_text,spoken_text,expected_action,expected_find,"
        "expected_which,expected_text,notes\n"
        '1,English,"box","change Ravi to Raj",replace,Ravi,,Raj,missing which\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="replace action requires expected_which"):
        load_eval_rows(csv_file)


def test_score_row_insert():
    row = {
        "id": "1",
        "mix": "English",
        "expected_action": "insert",
        "expected_find": "",
        "expected_which": "last",
        "expected_text": "Hello world.",
        "notes": "",
    }
    res = DummyActionResult(
        action=Action(action="insert", text="Hello world.", find="", which="last"),
        used_fallback=False,
        fallback_reason=None,
        elapsed_ms=120.0,
        prompt_tokens=50,
        completion_tokens=20,
    )
    score = score_row(row, res)
    assert score["pass"] is True
    assert score["action_ok"] is True
    assert score["text_cer"] == 0.0
    assert score["review_flag"] == ""


def test_score_row_replace_matching_and_mismatch():
    row = {
        "id": "5",
        "mix": "English",
        "expected_action": "replace",
        "expected_find": "Ravi",
        "expected_which": "first",
        "expected_text": "Raj",
        "notes": "",
    }
    # Exact match on find and which
    res_pass = DummyActionResult(
        action=Action(action="replace", text="Raj", find="Ravi", which="first"),
        used_fallback=False,
        fallback_reason=None,
        elapsed_ms=150.0,
        prompt_tokens=60,
        completion_tokens=25,
    )
    score_p = score_row(row, res_pass)
    assert score_p["pass"] is True
    assert score_p["find_ok"] is True
    assert score_p["which_ok"] is True

    # Which mismatch
    res_which_fail = DummyActionResult(
        action=Action(action="replace", text="Raj", find="Ravi", which="last"),
        used_fallback=False,
        fallback_reason=None,
        elapsed_ms=150.0,
        prompt_tokens=60,
        completion_tokens=25,
    )
    score_wf = score_row(row, res_which_fail)
    assert score_wf["pass"] is False
    assert score_wf["find_ok"] is True
    assert score_wf["which_ok"] is False

    # Find mismatch
    res_find_fail = DummyActionResult(
        action=Action(action="replace", text="Raj", find="Suresh", which="first"),
        used_fallback=False,
        fallback_reason=None,
        elapsed_ms=150.0,
        prompt_tokens=60,
        completion_tokens=25,
    )
    score_ff = score_row(row, res_find_fail)
    assert score_ff["pass"] is False
    assert score_ff["find_ok"] is False
    assert score_ff["which_ok"] is True


def test_score_row_none_handling():
    row = {
        "id": "9",
        "mix": "English",
        "expected_action": "none",
        "expected_find": "",
        "expected_which": "",
        "expected_text": "",
        "notes": "",
    }
    # Pass case: action is None and fallback_reason is find_not_found
    res_none_pass = DummyActionResult(
        action=None,
        used_fallback=True,
        fallback_reason="find_not_found",
        elapsed_ms=110.0,
        prompt_tokens=40,
        completion_tokens=15,
    )
    score_pass = score_row(row, res_none_pass)
    assert score_pass["pass"] is True
    assert score_pass["action_ok"] is True

    # Fail case: action returned an insert
    res_none_fail = DummyActionResult(
        action=Action(action="insert", text="Raj", find="", which="last"),
        used_fallback=False,
        fallback_reason=None,
        elapsed_ms=110.0,
        prompt_tokens=40,
        completion_tokens=15,
    )
    score_fail = score_row(row, res_none_fail)
    assert score_fail["pass"] is False
    assert score_fail["action_ok"] is False


def test_score_row_cer_flag():
    row = {
        "id": "10",
        "mix": "English",
        "expected_action": "rewrite",
        "expected_find": "",
        "expected_which": "last",
        "expected_text": "I am not coming to the office tomorrow.",
        "notes": "",
    }
    # Completely different text -> CER > 0.2
    res_diff = DummyActionResult(
        action=Action(
            action="rewrite",
            text="Unrelated text completely different sentence.",
            find="",
            which="last",
        ),
        used_fallback=False,
        fallback_reason=None,
        elapsed_ms=200.0,
        prompt_tokens=100,
        completion_tokens=30,
    )
    score = score_row(row, res_diff)
    assert score["pass"] is True  # action_ok decides pass for rewrite
    assert score["text_cer"] > 0.2
    assert score["review_flag"] == "review text"


def test_save_results_csv(tmp_path: Path):
    scores = [
        {
            "id": "1",
            "run": 1,
            "mix": "English",
            "expected_action": "insert",
            "got_action": "insert",
            "expected_find": "",
            "got_find": "",
            "expected_which": "last",
            "got_which": "last",
            "action_ok": True,
            "find_ok": None,
            "which_ok": None,
            "text_cer": 0.0,
            "review_flag": "",
            "pass": True,
            "used_fallback": False,
            "fallback_reason": "",
            "elapsed_ms": 100.0,
            "prompt_tokens": 50,
            "completion_tokens": 20,
            "cached_tokens": 0,
            "reasoning_tokens": 0,
            "cost_usd": 0.0001,
            "notes": "test",
        }
    ]
    out_path = save_results_csv(scores, tmp_path)
    assert out_path.exists()
    content = out_path.read_text(encoding="utf-8")
    assert "expected_action" in content
    assert "cost_usd" in content
    assert "insert" in content


def test_print_tables_and_confusion_matrix(capsys):
    scores = [
        {
            "id": "1",
            "mix": "English",
            "expected_action": "insert",
            "got_action": "insert",
            "pass": True,
            "action_ok": True,
            "used_fallback": False,
            "fallback_reason": "",
            "elapsed_ms": 100.0,
            "prompt_tokens": 50,
            "completion_tokens": 20,
            "cached_tokens": 0,
            "reasoning_tokens": 0,
            "cost_usd": 0.0001,
        },
        {
            "id": "2",
            "mix": "Kannada",
            "expected_action": "replace",
            "got_action": "replace",
            "pass": True,
            "action_ok": True,
            "used_fallback": True,
            "fallback_reason": "find_not_found",
            "elapsed_ms": 150.0,
            "prompt_tokens": 60,
            "completion_tokens": 25,
            "cached_tokens": 0,
            "reasoning_tokens": 0,
            "cost_usd": 0.00015,
        },
    ]
    print_confusion_matrix(scores)
    print_summary_tables(scores)
    captured = capsys.readouterr().out
    assert "EVAL-LLM SUMMARY" in captured
    assert "Pass Rate:            2/2 (100.0%)" in captured
    assert "Action Confusion Matrix" in captured
    assert "English" in captured
    assert "Kannada" in captured


@pytest.mark.asyncio
async def test_run_evaluation_mocked(tmp_path: Path):
    csv_file = tmp_path / "test.csv"
    csv_file.write_text(
        "id,mix,box_text,spoken_text,expected_action,expected_find,"
        "expected_which,expected_text,notes\n"
        '1,English,"","hello",insert,,last,"Hello.",dictation\n'
        '2,Kanglish,"hello Ravi","change Ravi to Raj",replace,Ravi,last,Raj,command\n',
        encoding="utf-8",
    )

    mock_process = AsyncMock(
        side_effect=[
            # Warm-up call
            DummyActionResult(None, False, "empty_speech", 50.0, 0, 0),
            # Row 1
            DummyActionResult(
                Action(action="insert", text="Hello.", find="", which="last"),
                False,
                None,
                110.0,
                55,
                15,
            ),
            # Row 2
            DummyActionResult(
                Action(action="replace", text="Raj", find="Ravi", which="last"),
                False,
                None,
                140.0,
                65,
                20,
            ),
        ]
    )

    with (
        patch("scripts.eval_llm.process", mock_process),
        patch("scripts.eval_llm.init_llm_client", new_callable=AsyncMock) as mock_init,
        patch(
            "scripts.eval_llm.close_llm_client", new_callable=AsyncMock
        ) as mock_close,
        patch("scripts.eval_llm.settings.META_API_KEY", "dummy-key"),
    ):
        results = await run_evaluation(
            csv_path=csv_file,
            runs=1,
            results_dir=tmp_path / "results",
        )

        assert len(results) == 2
        assert results[0]["pass"] is True
        assert results[1]["pass"] is True
        assert mock_init.call_count == 1
        assert mock_close.call_count == 1
        # 1 warm-up + 2 rows = 3 calls
        assert mock_process.call_count == 3
