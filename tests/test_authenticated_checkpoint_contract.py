from future_assistant.verified_skills import HashChainedReceiptLedger


def test_authenticated_checkpoint_claim_requires_a_present_verified_anchor(tmp_path) -> None:  # noqa: ANN001
    journal = tmp_path / "execution-receipts.jsonl"
    ledger = HashChainedReceiptLedger(journal)

    assert ledger.integrity_ok
    assert ledger.authenticated_checkpoint

    anchor = journal.with_name(f"{journal.name}.anchor.json")
    anchor.unlink()

    assert not ledger.authenticated_checkpoint
    assert not ledger.verify_integrity()
