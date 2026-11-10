from __future__ import annotations

from fastapi.testclient import TestClient

from metrixa_engine.api import server
from metrixa_engine.db import Database


def test_lead_filter_sort_paging_and_evidence_scorecard(tmp_path, monkeypatch):
    isolated = Database(tmp_path / "leads.db")
    monkeypatch.setattr(server, "db", isolated)
    with isolated.connect() as conn:
        alpha = conn.execute(
            """INSERT INTO companies_golden (
            canonical_name,display_name,legal_form,commercial_register_id,street_address,postal_code,city,district,
            phone_e164,website_url,canonical_domain,general_email,company_linkedin_url,is_vdiv_member,source_count,
            sources_csv,pipeline_stage,metrixa_lead_score,lead_tier,updated_at)
            VALUES ('alpha','Alpha Berlin Hausverwaltung GmbH','GmbH','HRB 1','Main St 1','10115','Berlin','Mitte',
            '+4930123','https://alpha.de','alpha.de','info@alpha.de','https://linkedin.com/company/alpha',1,2,'osm,11880','SCORED',91,'Tier A (High Priority)','old')"""
        ).lastrowid
        beta = conn.execute(
            """INSERT INTO companies_golden (canonical_name,display_name,legal_form,postal_code,city,district,sources_csv,pipeline_stage,metrixa_lead_score,lead_tier,updated_at)
            VALUES ('beta','Beta Hausverwaltung GmbH','GmbH','10719','Berlin','Charlottenburg','test','SCORED',50,'Tier B (Qualified Mid-Market)','old')"""
        ).lastrowid
        conn.execute(
            "INSERT INTO companies_golden (canonical_name,display_name,sources_csv,pipeline_stage,updated_at) VALUES ('bad','Disqualified','test','DISQUALIFIED','old')"
        )
        conn.execute(
            """INSERT INTO kpi_extractions (
            company_id,exact_units_managed,units_evidence_quote,estimated_units_tier,manages_weg,manages_miet,
            has_customer_portal,detected_erp_proptech,incumbent_metering_signal,digital_maturity_score,qualification_reasoning,extracted_at)
            VALUES (?,3000,'3,000 units','5,000+',1,1,1,'Casavi','Techem',5,'Verified facts','now')""",
            (alpha,),
        )
        conn.execute(
            "INSERT INTO decision_makers (company_id,full_name,first_name,last_name,role,personal_email,email_status,linkedin_url,is_primary_contact) VALUES (?, 'Max Mustermann','Max','Mustermann','Director','max@alpha.de','PUBLIC_DIRECT_VERIFIED','https://linkedin.com/in/max',1)",
            (alpha,),
        )
        conn.execute(
            "INSERT INTO crawled_pages (company_id,page_type,url,http_status,detected_erp_csv,detected_metering_csv,clean_markdown,crawled_at) VALUES (?, 'impressum','https://alpha.de/impressum',200,'Casavi','Techem, Ista',?, 'now')",
            (alpha, "A" * 2600),
        )

    client = TestClient(server.app)
    response = client.get(
        "/api/leads",
        params={
            "q": "Max",
            "tier": "Tier A",
            "district": "Mitte",
            "has_dm": "true",
            "has_email": "true",
            "has_erp": "true",
            "is_vdiv": "true",
            "sort_by": "display_name",
            "sort_dir": "asc",
            "page": 1,
            "limit": 1,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1 and data["pages"] == 1
    lead = data["items"][0]
    assert lead["lead_id"] == f"METRIXA-BER-{alpha:04d}"
    assert lead["email_status_code"] == "PUBLIC_LISTED"
    assert lead["email_status"] == "Publicly listed; mailbox not tested"
    assert lead["linkedin_url"] == "https://linkedin.com/in/max"

    # Other search columns, false facet values, sort expressions, and pagination offset.
    assert client.get("/api/leads?q=alpha.de").json()["total"] == 1
    assert client.get("/api/leads?q=Main").json()["total"] == 1
    assert (
        client.get(
            "/api/leads",
            params={"is_vdiv": "false", "sort_by": "company_id", "sort_dir": "asc"},
        ).json()["total"]
        == 1
    )
    assert (
        client.get(
            "/api/leads",
            params={
                "sort_by": "exact_units_managed",
                "sort_dir": "desc",
                "page": 2,
                "limit": 1,
            },
        ).json()["items"][0]["company_id"]
        == beta
    )
    assert (
        client.get(
            "/api/leads",
            params={"sort_by": "bad", "sort_dir": "unexpected", "page": 20, "limit": 1},
        ).json()["items"]
        == []
    )

    evidence = client.get(f"/api/leads/{alpha}/evidence").json()
    assert evidence["scorecard"] == {
        "scale_pts": 35,
        "focus_pts": 25,
        "digital_pts": 20,
        "trust_pts": 10,
        "contact_pts": 10,
        "total_score": 91,
    }
    assert evidence["decision_makers"][0]["email_status_code"] == "PUBLIC_LISTED"
    assert len(evidence["crawled_pages"][0]["clean_markdown"]) == 2500
    # A lead without KPI/contact records still gets a bounded scorecard and empty arrays.
    basic = client.get(f"/api/leads/{beta}/evidence").json()
    assert (
        basic["kpi"] == {}
        and basic["decision_makers"] == []
        and basic["crawled_pages"] == []
    )
    assert basic["scorecard"]["scale_pts"] == 16
