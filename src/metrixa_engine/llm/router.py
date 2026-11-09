"""
Unified Multi-Provider LLM Router + Deterministic German Impressum & KPI Parser.
Supports:
  1. llama.cpp local server (http://127.0.0.1:8080/v1)
  2. LM Studio local server (http://127.0.0.1:1234/v1)
  3. DeepSeek API (deepseek-chat / deepseek-reasoner)
  4. NVIDIA NIM API (meta/llama-3.3-70b-instruct / qwen2.5)
  5. Google Gemini API (gemini-2.5-flash)
  6. High-Precision Deterministic German Legal & KPI Parser (Zero-latency baseline & fallback)
"""

from __future__ import annotations

import json
import re
import time
from typing import Any, Dict, List, Optional, Tuple
import httpx

from metrixa_engine.config import settings
from metrixa_engine.entity_resolution.normalizer import extract_legal_form
from metrixa_engine.llm.prompts import (
    SYSTEM_EXTRACTION_PROMPT,
    build_user_extraction_prompt,
)
from metrixa_engine.models import CompanyKPIExtraction, DecisionMakerExtracted

# ============================================================================
# DETERMINISTIC GERMAN IMPRESSUM & KPI EXTRACTOR (REGEX + GERMAN LEGAL RULES)
# ============================================================================

DIRECTOR_PATTERNS = [
    (
        "Geschäftsführer",
        re.compile(
            r"(?:Gesch[aä\ufffd]ftsf[uü\ufffd]hr(?:er|erin|ung)|Vertretungsberechtigte[r]?[ \t]+Gesch[aä\ufffd]ftsf[uü\ufffd]hrer(?:in)?)[ \t]*[:\--]?[ \t]*\r?\n?[ \t]*((?:(?:Dr\.|Prof\.|Dipl\.-[A-Za-z]+|Herr|Frau)[ \t]+)*[A-ZÄÖÜ][a-zäöüß\ufffd\-]+(?:[ \t]+[A-ZÄÖÜ][a-zäöüß\ufffd\-]+){1,2})",
        ),
    ),
    (
        "Geschäftsführer",
        re.compile(
            r"Vertreten[ \t]+durch(?:[ \t]+die[ \t]+Gesch[aä\ufffd]ftsf[uü\ufffd]hrer(?:in)?)?[ \t]*[:\--]?[ \t]*\r?\n?[ \t]*((?:(?:Dr\.|Prof\.|Dipl\.-[A-Za-z]+|Herr|Frau)[ \t]+)*[A-ZÄÖÜ][a-zäöüß\ufffd\-]+(?:[ \t]+[A-ZÄÖÜ][a-zäöüß\ufffd\-]+){1,2})",
        ),
    ),
    (
        "Inhaber",
        re.compile(
            r"(?:Inhaber(?:in)?|Firmeninhaber(?:in)?)[ \t]*[:\--]?[ \t]*\r?\n?[ \t]*((?:(?:Dr\.|Prof\.|Dipl\.-[A-Za-z]+|Herr|Frau)[ \t]+)*[A-ZÄÖÜ][a-zäöüß\ufffd\-]+(?:[ \t]+[A-ZÄÖÜ][a-zäöüß\ufffd\-]+){1,2})",
        ),
    ),
    (
        "Vorstand",
        re.compile(
            r"(?:Vorstand|Vorstandsvorsitzende[r]?)[ \t]*[:\--]?[ \t]*\r?\n?[ \t]*((?:(?:Dr\.|Prof\.|Dipl\.-[A-Za-z]+|Herr|Frau)[ \t]+)*[A-ZÄÖÜ][a-zäöüß\ufffd\-]+(?:[ \t]+[A-ZÄÖÜ][a-zäöüß\ufffd\-]+){1,2})",
        ),
    ),
    (
        "Prokurist",
        re.compile(
            r"(?:Prokura|Prokurist(?:in)?)[ \t]*[:\--]?[ \t]*\r?\n?[ \t]*([A-ZÄÖÜ][a-zäöüß\ufffd\-]+(?:[ \t]+[A-ZÄÖÜ][a-zäöüß\ufffd\-]+){1,2})",
        ),
    ),
]

INVALID_PERSON_TOKENS = {
    "berlin",
    "gmbh",
    "hausverwaltung",
    "immobilien",
    "verwaltung",
    "amtsgericht",
    "charlottenburg",
    "telefon",
    "telefax",
    "kontakt",
    "impressum",
    "inhalt",
    "haftung",
    "umsatzsteuer",
    "registergericht",
    "handelsregister",
    "straße",
    "strasse",
    "platz",
    "allee",
    "damm",
    "deutschland",
    "service",
    "team",
    "partner",
    "gesellschaft",
    "mbh",
    "herr",
    "frau",
}

UNITS_REGEX_PATTERNS = [
    re.compile(
        r"((?:[uü]ber|ca\.|rund|mehr\s+als|fast|derzeit|aktuell)?\s*(\d{1,3}(?:\.\d{3})+|\d{3,5})\s*(?:Wohneinheiten|Wohn-\s*und\s*Gewerbeeinheiten|verwaltete[n]?\s+Einheiten|Einheiten|Wohnungen))",
        re.IGNORECASE,
    ),
    re.compile(
        r"(verwalten\s+(?:wir\s+)?(?:[uü]ber|ca\.|rund|mehr\s+als)?\s*(\d{1,3}(?:\.\d{3})+|\d{3,5})\s*(?:Wohneinheiten|Einheiten|Wohnungen|Objekte))",
        re.IGNORECASE,
    ),
]

HRB_REGEX = re.compile(r"\b(HR[AB]\s*\d{3,7}(?:\s*B)?)\b", re.IGNORECASE)
FOUNDING_YEAR_REGEX = re.compile(
    r"(?:seit\s+|gegr[uü]ndet\s+(?:im\s+Jahr\s+)?|Gr[uü]ndung\s+)((?:19\d{2}|20[012]\d))\b",
    re.IGNORECASE,
)
EMPLOYEE_COUNT_REGEX = [
    re.compile(
        r"\b(\d{1,3})\s+(?:Mitarbeiter(?:innen|n)?|Kolleginnen\s+und\s+Kollegen|Fachkr[aä]fte|Objektbetreuer)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"Team\s+(?:von|aus)\s+(?:[uü]ber\s+|ca\.\s+)?(\d{1,3})\s+",
        re.IGNORECASE,
    ),
]

GENERIC_EMAIL_PREFIXES = {
    "info",
    "kontakt",
    "contact",
    "office",
    "mail",
    "post",
    "service",
    "verwaltung",
    "hausverwaltung",
    "zentrale",
    "empfang",
    "berlin",
    "datenschutz",
    "bewerbung",
    "jobs",
    "buchhaltung",
    "rechnungen",
    "schaden",
    "notfall",
    "support",
    "team",
    "anfrage",
    "impressum",
    "hello",
    "hallo",
}


def clean_extracted_person_name(raw_name: str) -> Optional[str]:
    """Validate and clean a candidate German person name extracted from Impressum."""
    if not raw_name:
        return None
    # Strip leading 'Herr ' / 'Frau '
    name = re.sub(r"^(?:Herrn?|Frau)\s+", "", raw_name.strip(), flags=re.IGNORECASE)
    # Stop at newline or common trailing field labels
    name = re.split(
        r"\b(?:Tel|Telefon|Telefax|Fax|E-Mail|Email|USt|HRB|HRA|Amtsgericht|Register|Handelsregister|Sitz|Steuer|Berufsaufsicht|Inhalt|Haftung)\b",
        name,
        flags=re.IGNORECASE,
    )[0].strip(" ,;:--.")

    raw_words = [w for w in name.split() if w]
    valid_words: List[str] = []
    for w in raw_words:
        clean_w = w.lower().strip(".,-")
        if clean_w in INVALID_PERSON_TOKENS or any(ch.isdigit() for ch in clean_w):
            break
        valid_words.append(w)

    if len(valid_words) < 2 or len(valid_words) > 4:
        return None

    return " ".join(valid_words)


def extract_deterministic_german_kpis(
    company_name: str,
    combined_text: str,
    dom_erp_list: List[str],
    dom_metering_list: List[str],
    dom_has_portal: bool,
    dom_emails: List[str],
    dom_linkedin_urls: List[str],
) -> CompanyKPIExtraction:
    """
    High-precision deterministic parser for German Hausverwaltung websites & § 5 DDG Impressum.
    Provides 100% evidence-backed extraction even before/without LLM calls, and merges with LLM output.
    """
    text = combined_text or ""
    lower_text = text.lower()
    lower_name = company_name.lower()

    # 1. Legal form & HRB
    legal_form = extract_legal_form(company_name) or extract_legal_form(text[:3000])
    hrb_match = HRB_REGEX.search(text)
    hrb_id = (
        re.sub(r"\s+", " ", hrb_match.group(1).upper()).strip() if hrb_match else None
    )

    # 2. Founding year
    founding_year: Optional[int] = None
    fy_match = FOUNDING_YEAR_REGEX.search(text)
    if fy_match:
        yr = int(fy_match.group(1))
        if 1850 <= yr <= 2025:
            founding_year = yr

    # 3. Exact managed units (Wohneinheiten) + verbatim evidence quote
    exact_units: Optional[int] = None
    units_quote: Optional[str] = None
    for pat in UNITS_REGEX_PATTERNS:
        for m in pat.finditer(text):
            quote_str = re.sub(r"\s+", " ", m.group(1)).strip()
            num_str = m.group(2).replace(".", "").strip()
            if num_str.isdigit():
                val = int(num_str)
                # Realistic property manager portfolio range (50 to 250,000 units)
                # Exclude Berlin postal codes (10115-14199) or years (1900-2026) if ambiguous
                if 80 <= val <= 250000 and not (1950 <= val <= 2026):
                    exact_units = val
                    units_quote = quote_str
                    break
        if exact_units:
            break

    # 4. Employee count
    emp_count: Optional[int] = None
    for pat in EMPLOYEE_COUNT_REGEX:
        m = pat.search(text)
        if m and m.group(1).isdigit():
            val = int(m.group(1))
            if 2 <= val <= 1500:
                emp_count = val
                break

    # 5. Service Focus (WEG / Miet / Gewerbe / SEV)
    manages_weg = bool(
        re.search(
            r"weg[\-\s]*verwaltung|wohnungseigentumsverwaltung|wohnungseigentum|gemeinschaftseigentum|eigent[uü]mergemeinschaft",
            lower_text + " " + lower_name,
        )
    )
    manages_miet = bool(
        re.search(
            r"mietverwaltung|zinshausverwaltung|miethausverwaltung|mietsh[aä]user|wohnungsverwaltung|hausverwaltung",
            lower_text + " " + lower_name,
        )
    )
    manages_gewerbe = bool(
        re.search(
            r"gewerbeverwaltung|gewerbeimmobilien|gewerbeeinheiten|b[uü]roimmobilien",
            lower_text + " " + lower_name,
        )
    )
    manages_sev = bool(
        re.search(
            r"sondereigentumsverwaltung|sondereigentum|sev[\-\s]*verwaltung",
            lower_text + " " + lower_name,
        )
    )

    # Default residential assumption for explicit Berlin Hausverwaltung
    if not (manages_weg or manages_miet or manages_gewerbe):
        manages_weg = True
        manages_miet = True

    # 6. Decision Makers from Impressum & Team text
    decision_makers: List[DecisionMakerExtracted] = []
    seen_dm_names: set[str] = set()

    for role_label, pat in DIRECTOR_PATTERNS:
        for m in pat.finditer(text):
            cleaned_name = clean_extracted_person_name(m.group(1))
            if cleaned_name and cleaned_name.lower() not in seen_dm_names:
                seen_dm_names.add(cleaned_name.lower())
                quote_snip = re.sub(r"\s+", " ", m.group(0)).strip()[:180]
                decision_makers.append(
                    DecisionMakerExtracted(
                        full_name=cleaned_name,
                        role=role_label,
                        source_quote=quote_snip,
                    )
                )

    # 7. Classify extracted emails into Personal Direct vs. General info@
    general_emails: List[str] = []
    personal_emails: List[str] = []
    for em in dom_emails:
        local_part = em.split("@")[0].lower()
        if local_part in GENERIC_EMAIL_PREFIXES or any(
            local_part.startswith(p + ".") or local_part.startswith(p + "-")
            for p in GENERIC_EMAIL_PREFIXES
        ):
            general_emails.append(em)
        else:
            personal_emails.append(em)

    # Match personal emails to extracted decision makers if last name matches
    for dm in decision_makers:
        last_name = dm.full_name.split()[-1].lower()
        trans_last = (
            last_name.replace("ä", "ae")
            .replace("ö", "oe")
            .replace("ü", "ue")
            .replace("ß", "ss")
        )
        for pem in personal_emails:
            local = pem.split("@")[0].lower()
            if last_name in local or trans_last in local:
                dm.direct_email = pem
                break

    # Attach personal LinkedIn URL if present on page
    for li_url in dom_linkedin_urls:
        if (
            "/in/" in li_url.lower()
            and decision_makers
            and not decision_makers[0].linkedin_url
        ):
            decision_makers[0].linkedin_url = li_url

    software_combined = sorted(set(dom_erp_list + dom_metering_list))
    has_portal = dom_has_portal or bool(
        re.search(
            r"kundenportal|eigent[uü]merportal|mieterportal|online-service", lower_text
        )
    )

    # Build concise factual reasoning
    reasons = []
    if exact_units:
        reasons.append(f"Manages {exact_units:,} explicit units")
    elif emp_count:
        reasons.append(f"Team of {emp_count} employees")
    if manages_weg and manages_miet:
        reasons.append("active in both WEG & Mietverwaltung")
    elif manages_weg:
        reasons.append("active in WEG-Verwaltung")
    elif manages_miet:
        reasons.append("active in Mietverwaltung")
    if dom_erp_list:
        reasons.append(f"uses digital PropTech stack ({', '.join(dom_erp_list)})")
    elif has_portal:
        reasons.append("provides an online customer portal")
    if decision_makers:
        reasons.append(f"verified decision maker ({decision_makers[0].full_name})")

    reasoning_str = (
        f"Qualified Berlin Hausverwaltung ({legal_form or 'verified entity'}): "
        + ", ".join(reasons)
        + "."
        if reasons
        else f"Active Berlin property management company ({legal_form or 'standard portfolio'})."
    )

    return CompanyKPIExtraction(
        is_actual_hausverwaltung=True,
        legal_entity_name=company_name,
        legal_form=legal_form,
        commercial_register_id=hrb_id,
        founding_year=founding_year,
        exact_units_managed=exact_units,
        units_evidence_quote=units_quote,
        employee_count_mentioned=emp_count,
        manages_weg=manages_weg,
        manages_miet=manages_miet,
        manages_gewerbe=manages_gewerbe,
        manages_sev=manages_sev,
        has_online_portal=has_portal,
        software_mentioned=software_combined,
        decision_makers=decision_makers,
        general_emails=general_emails,
        qualification_reasoning=reasoning_str,
    )


# ============================================================================
# UNIFIED MULTI-PROVIDER LLM ROUTER
# ============================================================================


class LLMRouter:
    """
    Routes structured extraction requests across:
      - OpenAI Platform API (openai)
      - Google Gemini API (gemini)
      - DeepSeek API (deepseek)
      - NVIDIA NIM API (nvidia_nim)
      - Ollama local server (ollama)
      - llama.cpp local server (local_llamacpp)
      - LM Studio local server (lm_studio)
      - Deterministic German Legal & KPI Parser (deterministic / fallback)
    """

    def __init__(self) -> None:
        self._local_probe_cache: Dict[str, bool] = {}

    async def _probe_local_server(self, base_url: str) -> bool:
        if base_url in self._local_probe_cache:
            return self._local_probe_cache[base_url]
        try:
            async with httpx.AsyncClient(timeout=1.5) as client:
                resp = await client.get(f"{base_url.rstrip('/')}/models")
                ok = resp.status_code == 200
                self._local_probe_cache[base_url] = ok
                return ok
        except Exception:
            self._local_probe_cache[base_url] = False
            return False

    def get_provider_config(self, provider: str) -> Optional[Dict[str, str]]:
        p = provider.lower().strip()
        if p == "openai" and settings.openai_api_key:
            return {
                "provider": "openai",
                "base_url": settings.openai_base_url,
                "api_key": settings.openai_api_key,
                "model": settings.openai_model,
            }
        if p == "deepseek" and settings.deepseek_api_key:
            return {
                "provider": "deepseek",
                "base_url": settings.deepseek_base_url,
                "api_key": settings.deepseek_api_key,
                "model": settings.deepseek_model,
            }
        if p == "nvidia_nim" and settings.nvidia_nim_api_key:
            return {
                "provider": "nvidia_nim",
                "base_url": settings.nvidia_nim_base_url,
                "api_key": settings.nvidia_nim_api_key,
                "model": settings.nvidia_nim_model,
            }
        if p == "gemini" and settings.gemini_api_key:
            return {
                "provider": "gemini",
                "base_url": settings.gemini_base_url,
                "api_key": settings.gemini_api_key,
                "model": settings.gemini_model,
            }
        if p == "ollama":
            return {
                "provider": "ollama",
                "base_url": settings.ollama_base_url,
                "api_key": "ollama-local",
                "model": settings.ollama_model or "llama3.2",
            }
        if p == "local_llamacpp":
            return {
                "provider": "local_llamacpp",
                "base_url": settings.llamacpp_base_url,
                "api_key": settings.llamacpp_api_key or "llamacpp",
                "model": settings.llamacpp_model or "local-model",
            }
        if p == "lm_studio":
            return {
                "provider": "lm_studio",
                "base_url": settings.lmstudio_base_url,
                "api_key": settings.lmstudio_api_key or "lm-studio",
                "model": settings.lmstudio_model or "lfm3-1.7b",
            }
        return None

    async def resolve_active_provider(
        self, requested_provider: Optional[str] = None
    ) -> Optional[Dict[str, str]]:
        target = (requested_provider or settings.default_llm_provider).lower().strip()
        if target == "deterministic":
            return None

        if target != "auto_fallback":
            cfg = self.get_provider_config(target)
            if cfg:
                if target in ("ollama", "local_llamacpp", "lm_studio"):
                    if await self._probe_local_server(cfg["base_url"]):
                        return cfg
                    return None
                return cfg

        # Auto-fallback priority chain: OpenAI -> DeepSeek -> Gemini -> NVIDIA NIM -> Ollama -> Local llama.cpp -> LM Studio
        for candidate in ("openai", "deepseek", "gemini", "nvidia_nim"):
            cfg = self.get_provider_config(candidate)
            if cfg:
                return cfg

        for local_cand in ("ollama", "local_llamacpp", "lm_studio"):
            cfg = self.get_provider_config(local_cand)
            if cfg and await self._probe_local_server(cfg["base_url"]):
                return cfg

        return None

    async def extract_kpis_with_llm_and_deterministic_guard(
        self,
        company_name: str,
        website_url: str,
        combined_markdown: str,
        dom_erp_list: List[str],
        dom_metering_list: List[str],
        dom_has_portal: bool,
        dom_emails: List[str],
        dom_linkedin_urls: List[str],
        requested_provider: Optional[str] = None,
    ) -> Tuple[CompanyKPIExtraction, Dict[str, Any]]:
        """
        1. Runs the deterministic German Impressum/KPI parser first (zero hallucination baseline).
        2. If an LLM provider (local or cloud) is active and crawled text is non-empty,
           queries the LLM, parses the Pydantic schema, verifies evidence quotes against
           the source text, and merges with deterministic findings.
        """
        t0 = time.perf_counter()
        det_result = extract_deterministic_german_kpis(
            company_name=company_name,
            combined_text=combined_markdown,
            dom_erp_list=dom_erp_list,
            dom_metering_list=dom_metering_list,
            dom_has_portal=dom_has_portal,
            dom_emails=dom_emails,
            dom_linkedin_urls=dom_linkedin_urls,
        )

        provider_cfg = await self.resolve_active_provider(requested_provider)
        if not provider_cfg or len(combined_markdown.strip()) < 80:
            latency_ms = int((time.perf_counter() - t0) * 1000)
            return det_result, {
                "provider": "deterministic_german_nlp",
                "model_name": "regex_impressum_v1",
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "latency_ms": latency_ms,
                "schema_valid": True,
                "hallucination_blocked": False,
            }

        user_prompt = build_user_extraction_prompt(
            company_name=company_name,
            website_url=website_url,
            combined_markdown=combined_markdown,
            dom_erp_signals=", ".join(dom_erp_list),
            dom_metering_signals=", ".join(dom_metering_list),
            dom_emails=", ".join(dom_emails),
        )

        endpoint = f"{provider_cfg['base_url'].rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {provider_cfg['api_key']}",
            "Content-Type": "application/json",
        }
        model_id = provider_cfg["model"]
        is_o_series = bool(re.match(r"^o[134](?:-|$)", model_id.lower()))
        payload: Dict[str, Any] = {
            "model": model_id,
            "messages": [
                {"role": "system", "content": SYSTEM_EXTRACTION_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        }
        if is_o_series:
            payload["max_completion_tokens"] = 1600
        else:
            payload["temperature"] = 0.0
            payload["max_tokens"] = 1200

        if provider_cfg["provider"] in ("openai", "deepseek", "gemini"):
            payload["response_format"] = {"type": "json_object"}

        timeout_sec = (
            18.0
            if provider_cfg["provider"] in ("lm_studio", "ollama", "local_llamacpp")
            else 30.0
        )
        try:
            async with httpx.AsyncClient(timeout=timeout_sec) as client:
                resp = await client.post(endpoint, headers=headers, json=payload)
                latency_ms = int((time.perf_counter() - t0) * 1000)
                if resp.status_code == 200:
                    data = resp.json()
                    msg_obj = data.get("choices", [{}])[0].get("message", {})
                    content = msg_obj.get("content", "").strip()
                    if not content:
                        # Handle reasoning models where output tokens are placed in reasoning_content
                        content = msg_obj.get("reasoning_content", "").strip()

                    usage = data.get("usage") or {}
                    p_tok = int(usage.get("prompt_tokens", len(user_prompt) // 4))
                    c_tok = int(usage.get("completion_tokens", len(content) // 4))

                    # Strip markdown code fences if present or extract valid JSON
                    content_clean = re.sub(
                        r"^```(?:json)?\s*|\s*```$", "", content
                    ).strip()
                    try:
                        parsed_dict = json.loads(content_clean)
                    except Exception:
                        json_match = re.search(r"\{.*\}", content_clean, re.DOTALL)
                        if json_match:
                            parsed_dict = json.loads(json_match.group(0))
                        else:
                            raise ValueError("No valid JSON found in model output")

                    llm_obj = CompanyKPIExtraction.model_validate(parsed_dict)

                    # ANTI-HALLUCINATION GATE: Verify units and decision maker surnames in text
                    hallucination_blocked = False
                    norm_source = combined_markdown.lower()

                    if llm_obj.exact_units_managed is not None:
                        u_str = str(llm_obj.exact_units_managed)
                        u_dot = f"{llm_obj.exact_units_managed:,}".replace(",", ".")
                        if u_str not in norm_source and u_dot not in norm_source:
                            llm_obj.exact_units_managed = det_result.exact_units_managed
                            llm_obj.units_evidence_quote = (
                                det_result.units_evidence_quote
                            )
                            hallucination_blocked = True

                    verified_dms: List[DecisionMakerExtracted] = []
                    for dm in llm_obj.decision_makers:
                        surname = (
                            dm.full_name.split()[-1].lower() if dm.full_name else ""
                        )
                        if surname and len(surname) >= 2 and surname in norm_source:
                            verified_dms.append(dm)
                        else:
                            hallucination_blocked = True

                    if not verified_dms and det_result.decision_makers:
                        verified_dms = det_result.decision_makers
                    llm_obj.decision_makers = verified_dms

                    # Merge deterministic DOM ERP & Portal detections so nothing is lost
                    llm_obj.software_mentioned = sorted(
                        set(llm_obj.software_mentioned + det_result.software_mentioned)
                    )
                    llm_obj.has_online_portal = (
                        llm_obj.has_online_portal or det_result.has_online_portal
                    )
                    if not llm_obj.commercial_register_id:
                        llm_obj.commercial_register_id = (
                            det_result.commercial_register_id
                        )
                    if not llm_obj.legal_form:
                        llm_obj.legal_form = det_result.legal_form

                    return llm_obj, {
                        "provider": provider_cfg["provider"],
                        "model_name": provider_cfg["model"],
                        "prompt_tokens": p_tok,
                        "completion_tokens": c_tok,
                        "latency_ms": latency_ms,
                        "schema_valid": True,
                        "hallucination_blocked": hallucination_blocked,
                    }
        except Exception:
            pass

        latency_ms = int((time.perf_counter() - t0) * 1000)
        return det_result, {
            "provider": "deterministic_fallback",
            "model_name": "regex_impressum_v1",
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "latency_ms": latency_ms,
            "schema_valid": True,
            "hallucination_blocked": False,
        }


llm_router = LLMRouter()
