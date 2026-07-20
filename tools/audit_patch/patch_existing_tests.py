from __future__ import annotations

from common import read, write


def main() -> None:
    path = "tests/test_verified_skills.py"
    text = read(path)
    changes = (
        ("    assert len(ledger.receipts) == 2\n", "    assert len(ledger.receipts) == 3\n"),
        ("    assert len(ledger.receipts) == 1\n", "    assert len(ledger.receipts) == 2\n"),
        (
            '    assert "secret-demo-query" not in repr(ledger.receipts[0])\n'
            '    assert ledger.receipts[0].action["query_keys"] == ["q"]\n'
            '    assert ledger.receipts[0].argument_keys == ("purpose", "url")\n'
            "    assert len(ledger.receipts[0].argument_digest) == 64\n",
            '    assert "secret-demo-query" not in repr(ledger.receipts)\n'
            '    assert ledger.receipts[-1].action["query_keys"] == ["q"]\n'
            '    assert ledger.receipts[-1].argument_keys == ("purpose", "url")\n'
            "    assert len(ledger.receipts[-1].argument_digest) == 64\n",
        ),
        (
            "    first, second = ledger.receipts\n"
            '    assert first.previous_hash == "0" * 64\n'
            "    assert second.previous_hash == first.receipt_hash\n"
            "    assert first.receipt_hash != second.receipt_hash\n",
            "    receipts = ledger.receipts\n"
            '    assert receipts[0].previous_hash == "0" * 64\n'
            "    assert all(\n"
            "        current.previous_hash == previous.receipt_hash\n"
            "        for previous, current in zip(receipts, receipts[1:], strict=False)\n"
            "    )\n"
            "    assert len({receipt.receipt_hash for receipt in receipts}) == len(receipts)\n",
        ),
        (
            '        "cancelled",\n        "completed",\n',
            '        "cancelled",\n        "authorized",\n        "completed",\n',
        ),
    )
    for old, new in changes:
        if old in text:
            text = text.replace(old, new, 1)
    write(path, text)


if __name__ == "__main__":
    main()
