"""
Secret & PII Scrubber Engine
Automatically redacts sensitive API keys, credentials, JWTs, private keys,
passwords, and PII before diffs are processed or transmitted to AI models.
"""

import re
from typing import Tuple, List, Dict, Set


class SecretScrubber:
    """Detects and redacts sensitive credentials and PII from source code diffs."""

    PATTERNS: List[Tuple[str, re.Pattern, str]] = [
        # AWS Access Key ID
        (
            "AWS Access Key",
            re.compile(r"\b(AKIA[0-9A-Z]{16})\b"),
            "[REDACTED_AWS_ACCESS_KEY]"
        ),
        # AWS Secret Access Key
        (
            "AWS Secret Key",
            re.compile(r"(?i)(aws_secret_access_key|aws_secret_key|secret_key)\s*[:=]\s*['\"]?([A-Za-z0-9/+=]{40})['\"]?"),
            r"\1 = '[REDACTED_AWS_SECRET]'"
        ),
        # RSA / EC / SSH Private Keys
        (
            "Private Key",
            re.compile(r"-----BEGIN (?:RSA |DSA |EC |OPENSSH )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |DSA |EC |OPENSSH )?PRIVATE KEY-----"),
            "[REDACTED_PRIVATE_KEY]"
        ),
        # JSON Web Tokens (JWT)
        (
            "JWT Token",
            re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
            "[REDACTED_JWT_TOKEN]"
        ),
        # GitHub Personal Access Token
        (
            "GitHub Token",
            re.compile(r"\b(gh[pousr]_[A-Za-z0-9_]{36,255})\b"),
            "[REDACTED_GITHUB_TOKEN]"
        ),
        # Generic API Key / Bearer Token assignment
        (
            "API Token",
            re.compile(r"(?i)(api[_-]?key|auth[_-]?token|bearer[_-]?token|access[_-]?token)\s*[:=]\s*['\"]?([a-zA-Z0-9_\-\.]{12,80})['\"]?"),
            r"\1: '[REDACTED_API_TOKEN]'"
        ),
        # Authorization header
        (
            "Auth Header",
            re.compile(r"(?i)(authorization:\s*bearer\s+)([A-Za-z0-9\-\._~+/]+=*)"),
            r"\1[REDACTED_BEARER_TOKEN]"
        ),
        # Passwords in assignments
        (
            "Password",
            re.compile(r"(?i)(password|passwd|pwd|db_pass|secret)\s*[:=]\s*['\"]?([^'\"\s\r\n]{4,64})['\"]?"),
            r"\1: '[REDACTED_PASSWORD]'"
        ),
        # Database URIs with credentials
        (
            "Database URL Password",
            re.compile(r"(?i)([a-z0-9+.-]+://[^:]+:)([^@\s]+)(@[a-z0-9.-]+)"),
            r"\1[REDACTED_CREDENTIALS]\3"
        ),
        # IPv4 addresses
        (
            "IP Address",
            re.compile(r"\b(?!(?:127\.0\.0\.1|0\.0\.0\.0|255\.255\.255\.255)\b)(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b"),
            "[REDACTED_IP]"
        ),
        # Email addresses
        (
            "Email Address",
            re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b"),
            "[REDACTED_EMAIL]"
        )
    ]

    @classmethod
    def scrub_text(cls, text: str) -> Tuple[str, int, List[str]]:
        """
        Redacts secrets and PII from a single text string.
        Returns: (scrubbed_text, total_redactions_count, categories_detected)
        """
        scrubbed = text
        total_count = 0
        detected_categories: Set[str] = set()

        for category, pattern, replacement in cls.PATTERNS:
            matches = list(pattern.finditer(scrubbed))
            if matches:
                detected_categories.add(category)
                total_count += len(matches)
                scrubbed = pattern.sub(replacement, scrubbed)

        return scrubbed, total_count, sorted(list(detected_categories))

    @classmethod
    def scrub_lines(cls, lines: List[str]) -> Tuple[List[str], int, List[str]]:
        """Scrubs a list of lines, preserving line counts."""
        full_text = "\n".join(lines)
        scrubbed_text, count, categories = cls.scrub_text(full_text)
        return scrubbed_text.splitlines(), count, categories
