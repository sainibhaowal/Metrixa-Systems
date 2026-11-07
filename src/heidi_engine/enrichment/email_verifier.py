"""
DNS MX Record Lookup, Email Syntax Validator, info@ Filter,
and German Corporate Personal Email Pattern Generator.
"""

from __future__ import annotations

import asyncio
import re
from typing import Dict, Optional, Tuple
import dns.resolver

from heidi_engine.config import settings
from heidi_engine.entity_resolution.normalizer import (
    FREEMAIL_DOMAINS,
    transliterate_german,
)
from heidi_engine.llm.router import GENERIC_EMAIL_PREFIXES


class EmailVerifier:
    """Verifies domain DNS MX records and generates/validates personal decision-maker emails."""

    def __init__(self) -> None:
        self._mx_cache: Dict[str, Tuple[bool, Optional[str]]] = {}

    def check_domain_mx_sync(self, domain: Optional[str]) -> Tuple[bool, Optional[str]]:
        """Return (has_valid_mx, primary_mx_host) for a domain."""
        if not domain:
            return False, None
        dom = domain.lower().strip()
        if dom in self._mx_cache:
            return self._mx_cache[dom]

        if not settings.enable_dns_mx_check:
            self._mx_cache[dom] = (True, f"mx.{dom}")
            return True, f"mx.{dom}"

        try:
            resolver = dns.resolver.Resolver()
            resolver.timeout = 3.0
            resolver.lifetime = 3.5
            answers = resolver.resolve(dom, "MX")
            hosts = sorted(
                [(r.preference, str(r.exchange).rstrip(".")) for r in answers],
                key=lambda x: x[0],
            )
            if hosts and hosts[0][1]:
                res = (True, hosts[0][1])
                self._mx_cache[dom] = res
                return res
        except Exception:
            pass

        self._mx_cache[dom] = (False, None)
        return False, None

    async def check_domain_mx(
        self, domain: Optional[str]
    ) -> Tuple[bool, Optional[str]]:
        return await asyncio.to_thread(self.check_domain_mx_sync, domain)

    @staticmethod
    def is_personal_email(email: Optional[str]) -> bool:
        """Return True if email is a personal/direct address and NOT a generic info@/kontakt@ inbox."""
        if not email or "@" not in email:
            return False
        local, domain = email.lower().strip().split("@", 1)
        if not local or not domain:
            return False
        if local in GENERIC_EMAIL_PREFIXES:
            return False
        if any(
            local.startswith(p + ".")
            or local.startswith(p + "-")
            or local.startswith(p + "_")
            for p in GENERIC_EMAIL_PREFIXES
        ):
            return False
        return True

    @staticmethod
    def generate_german_b2b_personal_email(
        full_name: str, canonical_domain: Optional[str]
    ) -> Optional[str]:
        """
        Generate standard German corporate email pattern (vorname.nachname@domain.de)
        for a verified Geschäftsführer when the corporate domain is NOT a freemail provider.
        """
        if not full_name or not canonical_domain:
            return None
        dom = canonical_domain.lower().strip()
        if dom in FREEMAIL_DOMAINS:
            return None

        # Strip titles (Dr., Prof., Dipl.-Ing., Dipl.-Kfm.)
        cleaned = re.sub(
            r"\b(?:dr\.|prof\.|dipl\.-[a-zäöüß]+|m\.a\.|ll\.m\.|herr|frau)\b",
            "",
            full_name,
            flags=re.IGNORECASE,
        ).strip()
        parts = [p for p in re.split(r"\s+", cleaned) if len(p) >= 2]
        if len(parts) < 2:
            return None

        first = re.sub(r"[^a-z]", "", transliterate_german(parts[0]).lower())
        last = re.sub(r"[^a-z\-]", "", transliterate_german(parts[-1]).lower())
        if not first or not last:
            return None

        return f"{first}.{last}@{dom}"


email_verifier = EmailVerifier()
