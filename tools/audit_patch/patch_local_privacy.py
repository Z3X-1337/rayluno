from __future__ import annotations

from common import read, replace_once, write


def patch_audit() -> None:
    path = "src/future_assistant/audit.py"
    replace_once(
        path,
        "import hashlib\nimport json\nimport threading\n",
        "import json\nimport os\nimport secrets\nimport threading\n",
        marker="load_or_create_key",
    )
    replace_once(
        path,
        "from .domain import Action, ActionKind\n",
        "from .domain import Action, ActionKind\n"
        "from .local_security import keyed_digest, load_or_create_key, secure_directory, secure_file\n",
        marker="from .local_security import",
    )
    replace_once(
        path,
        "class _BaseAuditLogger:\n"
        "    def __init__(self, clock: Callable[[], datetime] | None = None) -> None:\n"
        "        self.clock = clock or (lambda: datetime.now(UTC))\n",
        "class _BaseAuditLogger:\n"
        "    def __init__(\n"
        "        self,\n"
        "        clock: Callable[[], datetime] | None = None,\n"
        "        *,\n"
        "        fingerprint_key: bytes | None = None,\n"
        "    ) -> None:\n"
        "        self.clock = clock or (lambda: datetime.now(UTC))\n"
        "        self._fingerprint_key = fingerprint_key or secrets.token_bytes(32)\n",
        marker="fingerprint_key: bytes | None",
    )
    replace_once(
        path,
        "        if command is not None:\n"
        "            command_hash = hashlib.sha256(command.encode(\"utf-8\")).hexdigest()\n",
        "        if command is not None:\n"
        "            command_hash = keyed_digest(\n"
        "                self._fingerprint_key,\n"
        "                {\"domain\": \"rayluno.audit.command/v1\", \"command\": command},\n"
        "            )\n",
        marker="rayluno.audit.command/v1",
    )
    replace_once(
        path,
        "class JsonlAuditLogger(_BaseAuditLogger):\n"
        "    def __init__(self, path: Path, clock: Callable[[], datetime] | None = None) -> None:\n"
        "        super().__init__(clock)\n"
        "        self.path = path\n"
        "        self._lock = threading.Lock()\n",
        "class JsonlAuditLogger(_BaseAuditLogger):\n"
        "    def __init__(self, path: Path, clock: Callable[[], datetime] | None = None) -> None:\n"
        "        self.path = Path(path)\n"
        "        secure_directory(self.path.parent)\n"
        "        key_path = self.path.with_name(f\"{self.path.name}.key\")\n"
        "        try:\n"
        "            fingerprint_key = load_or_create_key(key_path)\n"
        "        except (OSError, ValueError):\n"
        "            fingerprint_key = secrets.token_bytes(32)\n"
        "        super().__init__(clock, fingerprint_key=fingerprint_key)\n"
        "        self._lock = threading.Lock()\n",
        marker="key_path = self.path.with_name",
    )
    replace_once(
        path,
        "        with self._lock:\n"
        "            self.path.parent.mkdir(parents=True, exist_ok=True)\n"
        "            with self.path.open(\"a\", encoding=\"utf-8\") as stream:\n"
        "                stream.write(f\"{line}\\n\")\n",
        "        with self._lock:\n"
        "            secure_directory(self.path.parent)\n"
        "            with self.path.open(\"a\", encoding=\"utf-8\") as stream:\n"
        "                stream.write(f\"{line}\\n\")\n"
        "                stream.flush()\n"
        "                os.fsync(stream.fileno())\n"
        "            secure_file(self.path)\n",
        marker="os.fsync(stream.fileno())",
    )


def patch_sqlite_permissions() -> None:
    paths = (
        "src/future_assistant/memory.py",
        "src/future_assistant/tasks.py",
        "src/future_assistant/reminders.py",
    )
    for path in paths:
        replace_once(
            path,
            "from .identity import COMPATIBILITY_DATA_DIRECTORY\n",
            "from .identity import COMPATIBILITY_DATA_DIRECTORY\n"
            "from .local_security import secure_directory, secure_file\n",
            marker="from .local_security import secure_directory, secure_file",
        )
        replace_once(
            path,
            "        self.path.parent.mkdir(parents=True, exist_ok=True)\n"
            "        connection = sqlite3.connect(self.path, timeout=5.0)\n"
            "        connection.row_factory = sqlite3.Row\n",
            "        secure_directory(self.path.parent)\n"
            "        connection = sqlite3.connect(self.path, timeout=5.0)\n"
            "        secure_file(self.path)\n"
            "        connection.row_factory = sqlite3.Row\n",
            marker="secure_file(self.path)",
        )


def patch_memory_secret_detection() -> None:
    path = "src/future_assistant/memory.py"
    text = read(path)
    if "_STRUCTURED_SECRET_PATTERNS" not in text:
        insertion = '''
_STRUCTURED_SECRET_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
        r"\\beyJ[A-Za-z0-9_-]{8,}\\.[A-Za-z0-9_-]{8,}\\.[A-Za-z0-9_-]{8,}\\b",
        r"\\b(?:sk|rk)-[A-Za-z0-9_-]{16,}\\b",
        r"\\bgh[pousr]_[A-Za-z0-9]{20,}\\b",
        r"\\bgithub_pat_[A-Za-z0-9_]{20,}\\b",
        r"\\bAKIA[0-9A-Z]{16}\\b",
        r"\\bAIza[0-9A-Za-z_-]{30,}\\b",
        r"\\bxox[baprs]-[0-9A-Za-z-]{20,}\\b",
    )
)
_CARD_CANDIDATE = re.compile(r"(?<!\\d)(?:\\d[ -]?){13,19}(?!\\d)")
'''
        anchor = ")\n\n\nclass MemoryCategory"
        if anchor not in text:
            raise RuntimeError("Could not locate memory pattern insertion point")
        text = text.replace(anchor, ")\n" + insertion + "\n\nclass MemoryCategory", 1)
        write(path, text)
    replace_once(
        path,
        "def contains_sensitive_material(statement: str) -> bool:\n"
        "    return any(pattern.search(statement) for pattern in _SENSITIVE_PATTERNS)\n",
        "def _luhn_valid(value: str) -> bool:\n"
        "    digits = [int(character) for character in value if character.isdigit()]\n"
        "    if not 13 <= len(digits) <= 19 or len(set(digits)) == 1:\n"
        "        return False\n"
        "    checksum = 0\n"
        "    parity = len(digits) % 2\n"
        "    for index, digit in enumerate(digits):\n"
        "        if index % 2 == parity:\n"
        "            digit *= 2\n"
        "            if digit > 9:\n"
        "                digit -= 9\n"
        "        checksum += digit\n"
        "    return checksum % 10 == 0\n\n\n"
        "def contains_sensitive_material(statement: str) -> bool:\n"
        "    if any(pattern.search(statement) for pattern in _SENSITIVE_PATTERNS):\n"
        "        return True\n"
        "    if any(pattern.search(statement) for pattern in _STRUCTURED_SECRET_PATTERNS):\n"
        "        return True\n"
        "    return any(_luhn_valid(match.group(0)) for match in _CARD_CANDIDATE.finditer(statement))\n",
        marker="def _luhn_valid",
    )


def main() -> None:
    patch_audit()
    patch_sqlite_permissions()
    patch_memory_secret_detection()


if __name__ == "__main__":
    main()
