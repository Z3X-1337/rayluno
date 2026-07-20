from __future__ import annotations

from common import read, write


def replace_if_present(text: str, old: str, new: str) -> str:
    return text.replace(old, new, 1) if old in text else text


def patch_verified_skills() -> None:
    path = "tests/test_verified_skills.py"
    text = read(path)
    text = replace_if_present(
        text,
        '    assert pending["argument_digest"]\n    assert len(ledger.receipts) == 2\n',
        '    assert pending["argument_digest"]\n    assert len(ledger.receipts) == 1\n',
    )
    text = replace_if_present(
        text,
        '    assert effects.operations[0][0] == "open_url"\n    assert len(ledger.receipts) == 1\n',
        '    assert effects.operations[0][0] == "open_url"\n    assert len(ledger.receipts) == 2\n',
    )
    text = replace_if_present(
        text,
        '    entry = json.loads(path.read_text(encoding="utf-8"))\n'
        '    entry["status"] = "failed"\n'
        '    path.write_text(json.dumps(entry, ensure_ascii=False) + "\\n", encoding="utf-8")\n',
        '    lines = path.read_text(encoding="utf-8").splitlines()\n'
        "    entry = json.loads(lines[-1])\n"
        '    entry["status"] = "failed"\n'
        "    lines[-1] = json.dumps(entry, ensure_ascii=False)\n"
        '    path.write_text("\\n".join(lines) + "\\n", encoding="utf-8")\n',
    )
    write(path, text)


def patch_judge_demo() -> None:
    path = "tests/test_judge_demo.py"
    text = read(path)
    text = replace_if_present(
        text, "    assert len(ledger.receipts) == 4\n", "    assert len(ledger.receipts) == 6\n"
    )
    text = replace_if_present(
        text,
        '        "confirmation_requested",\n'
        '        "confirmation_requested",\n'
        '        "execution",\n'
        '        "execution",\n',
        '        "confirmation_requested",\n'
        '        "confirmation_requested",\n'
        '        "execution_authorized",\n'
        '        "execution_authorized",\n'
        '        "execution",\n'
        '        "execution",\n',
    )
    write(path, text)


def patch_verified_desktop() -> None:
    path = "tests/test_verified_desktop.py"
    text = read(path)
    text = replace_if_present(
        text,
        '    assert verified["receipt_count"] == 2\n',
        '    assert verified["receipt_count"] == 3\n',
    )
    write(path, text)


def main() -> None:
    patch_verified_skills()
    patch_judge_demo()
    patch_verified_desktop()


if __name__ == "__main__":
    main()
