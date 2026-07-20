from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from future_assistant import product_updates
from future_assistant.product_updates import ProductUpdateService
from future_assistant.updates import NoUpdateAvailableError


class FakeClient:
    def __init__(self, *, available: bool = True) -> None:
        self.available = available
        self.downloads: list[Path] = []
        self.result = SimpleNamespace(
            update_available=available,
            manifest=SimpleNamespace(
                release=SimpleNamespace(version="0.2.0", size=1234),
            ),
        )

    def check(self):  # noqa: ANN201
        return self.result

    def download(self, check, destination):  # noqa: ANN001, ANN201
        assert check is self.result
        path = Path(destination)
        self.downloads.append(path)
        return SimpleNamespace(path=path)


def test_unconfigured_updates_report_safe_disabled_state() -> None:
    status = ProductUpdateService(None).check()

    assert status.configured is False
    assert status.checked is False
    assert status.available is False
    assert status.to_public_dict()["staged"] is False
    assert status.to_public_dict()["managed_by_store"] is False


def test_store_managed_updates_never_configure_or_stage_direct_installer() -> None:
    service = ProductUpdateService(None, managed_by_store=True)

    public = service.check().to_public_dict()

    assert public["managed_by_store"] is True
    assert public["configured"] is False
    with pytest.raises(RuntimeError, match="Microsoft Store"):
        service.stage()


def test_store_build_ignores_direct_update_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        product_updates,
        "packaged_distribution_channel",
        lambda: product_updates.STORE_DISTRIBUTION,
    )
    monkeypatch.setenv(
        "FUTURE_ASSISTANT_UPDATE_MANIFEST_URL",
        "https://updates.example.com/manifest.json",
    )

    service = product_updates.build_default_update_service()

    assert service.managed_by_store is True
    assert service.configured is False


def test_sideload_build_disables_direct_installer_without_store_claim(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        product_updates,
        "packaged_distribution_channel",
        lambda: product_updates.SIDELOAD_DISTRIBUTION,
    )
    monkeypatch.setenv(
        "FUTURE_ASSISTANT_UPDATE_MANIFEST_URL",
        "https://updates.example.com/manifest.json",
    )

    service = product_updates.build_default_update_service()

    assert service.managed_by_store is False
    assert service.configured is False


def test_packaged_distribution_channel_requires_signed_payload_marker(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    executable = tmp_path / "Rayluno.exe"
    executable.write_bytes(b"MZ")
    monkeypatch.setattr(product_updates, "is_msix_packaged", lambda: True)

    assert product_updates.packaged_distribution_channel(executable=executable) == "msix-unknown"

    marker = tmp_path / product_updates.DISTRIBUTION_MARKER
    marker.write_text(product_updates.STORE_DISTRIBUTION + "\n", encoding="utf-8")
    assert (
        product_updates.packaged_distribution_channel(executable=executable)
        == product_updates.STORE_DISTRIBUTION
    )


def test_check_exposes_only_release_facts() -> None:
    service = ProductUpdateService(FakeClient())  # type: ignore[arg-type]

    public = service.check().to_public_dict()

    assert public["available"] is True
    assert public["checked"] is True
    assert public["version"] == "0.2.0"
    assert public["size"] == 1234
    assert "url" not in public
    assert "sha256" not in public
    assert service.current_status().available is True


def test_stage_uses_verified_check_and_fixed_destination(tmp_path: Path) -> None:
    client = FakeClient()
    service = ProductUpdateService(client, destination=tmp_path)  # type: ignore[arg-type]
    service.check()

    status = service.stage()

    assert client.downloads == [tmp_path / "Rayluno-Setup-0.2.0.exe"]
    assert status.staged_path == str(client.downloads[0])
    assert status.checked is True


def test_stage_requires_prior_check(tmp_path: Path) -> None:
    service = ProductUpdateService(FakeClient(), destination=tmp_path)  # type: ignore[arg-type]

    with pytest.raises(RuntimeError, match="check"):
        service.stage()


def test_stage_rejects_a_checked_release_when_no_update_is_available(tmp_path: Path) -> None:
    client = FakeClient(available=False)
    service = ProductUpdateService(client, destination=tmp_path)  # type: ignore[arg-type]
    service.check()

    with pytest.raises(NoUpdateAvailableError):
        service.stage()

    assert client.downloads == []


def test_new_check_clears_previous_staged_state(tmp_path: Path) -> None:
    client = FakeClient()
    service = ProductUpdateService(client, destination=tmp_path)  # type: ignore[arg-type]
    service.check()
    service.stage()
    assert service.current_status().to_public_dict()["staged"] is True

    service.check()

    status = service.current_status().to_public_dict()
    assert status["checked"] is True
    assert status["staged"] is False
