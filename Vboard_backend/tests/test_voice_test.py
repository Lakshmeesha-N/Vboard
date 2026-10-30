from scripts.voice_test import apply_action


def test_insert_into_empty_box():
    action = {"action": "insert", "text": "Hello world.", "find": "", "which": "last"}
    res = apply_action("", action)
    assert res == "Hello world."


def test_insert_into_non_empty_box_adds_space():
    action = {"action": "insert", "text": "How are you?", "find": "", "which": "last"}
    res = apply_action("Hello.", action)
    assert res == "Hello. How are you?"


def test_insert_into_box_ending_with_space_or_newline_does_not_duplicate_space():
    action = {"action": "insert", "text": "Next sentence.", "find": "", "which": "last"}
    assert apply_action("Hello. ", action) == "Hello. Next sentence."
    assert apply_action("Hello.\n", action) == "Hello.\nNext sentence."


def test_replace_first_occurrence():
    box = "apple banana apple cherry apple"
    action = {"action": "replace", "find": "apple", "text": "orange", "which": "first"}
    res = apply_action(box, action)
    assert res == "orange banana apple cherry apple"


def test_replace_last_occurrence():
    box = "apple banana apple cherry apple"
    action = {"action": "replace", "find": "apple", "text": "orange", "which": "last"}
    res = apply_action(box, action)
    assert res == "apple banana apple cherry orange"


def test_replace_all_occurrences():
    box = "apple banana apple cherry apple"
    action = {"action": "replace", "find": "apple", "text": "orange", "which": "all"}
    res = apply_action(box, action)
    assert res == "orange banana orange cherry orange"


def test_replace_numeric_position():
    box = "apple banana apple cherry apple"
    # Replace second occurrence (1-based index)
    action = {"action": "replace", "find": "apple", "text": "orange", "which": "2"}
    res = apply_action(box, action)
    assert res == "apple banana orange cherry apple"

    # Numeric out of bounds leaves box unchanged
    action_oob = {"action": "replace", "find": "apple", "text": "orange", "which": "5"}
    assert apply_action(box, action_oob) == box


def test_replace_case_insensitive_fallback():
    box = "Say Hello World"
    action = {
        "action": "replace",
        "find": "hello world",
        "text": "Greetings",
        "which": "last",
    }
    res = apply_action(box, action)
    assert res == "Say Greetings"


def test_replace_missing_find_leaves_box_unchanged():
    box = "The quick brown fox"
    action = {"action": "replace", "find": "elephant", "text": "tiger", "which": "last"}
    assert apply_action(box, action) == box


def test_rewrite_replaces_entire_box():
    box = "Drafting an informal message here..."
    action = {
        "action": "rewrite",
        "text": "Formal message content.",
        "find": "",
        "which": "last",
    }
    res = apply_action(box, action)
    assert res == "Formal message content."


def test_null_or_none_action_leaves_box_unchanged():
    box = "Existing content in the box"
    assert apply_action(box, None) == box
    assert apply_action(box, {}) == box
    assert apply_action(box, {"action": None}) == box


def test_undo_stack_simulation():
    box = ""
    undo_stack = []

    # Action 1: Insert
    undo_stack.append(box)
    box = apply_action(
        box, {"action": "insert", "text": "First", "find": "", "which": "last"}
    )
    assert box == "First"

    # Action 2: Insert
    undo_stack.append(box)
    box = apply_action(
        box, {"action": "insert", "text": "Second", "find": "", "which": "last"}
    )
    assert box == "First Second"

    # Action 3: Replace
    undo_stack.append(box)
    box = apply_action(
        box,
        {"action": "replace", "find": "Second", "text": "2nd", "which": "last"},
    )
    assert box == "First 2nd"

    # Undo Action 3
    box = undo_stack.pop()
    assert box == "First Second"

    # Undo Action 2
    box = undo_stack.pop()
    assert box == "First"

    # Undo Action 1
    box = undo_stack.pop()
    assert box == ""

    # Clear simulation
    undo_stack.clear()
    assert len(undo_stack) == 0
