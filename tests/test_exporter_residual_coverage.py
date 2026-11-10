from __future__ import annotations

from pathlib import Path

from openpyxl import load_workbook

from metrixa_engine.db import Database
from metrixa_engine.telemetry.excel_exporter import ExcelExporter


def test_exporter_styles_and_writes_all_populated_tabs(tmp_path, monkeypatch):
    import metrixa_engine.telemetry.excel_exporter as module

    db = Database(tmp_path / "export-residual.db")
    export_dir = tmp_path / "exports"
    monkeypatch.setattr(module.settings, "export_dir", export_dir)
    monkeypatch.setattr(module.settings, "database_path", db.db_path)
    with db.connect() as conn:
        company_id = conn.execute(
            """INSERT INTO companies_golden (
                canonical_name,display_name,legal_form,commercial_register_id,street_address,
                postal_code,city,district,phone_e164,website_url,canonical_domain,general_email,
                company_linkedin_url,is_vdiv_member,source_count,sources_csv,metrixa_lead_score,
                lead_tier,pipeline_stage,updated_at
            ) VALUES ('alpha','Alpha GmbH','GmbH','HRB 123','Main Street 1','10115','Berlin','Mitte',
                '+4930555123','https://alpha.example','alpha.example','info@alpha.example',
                'https://linkedin.com/company/alpha',1,2,'osm, directory',90,'Tier A (High Priority)','SCORED','now')"""
        ).lastrowid
        conn.execute(
            """INSERT INTO kpi_extractions (
                company_id,founding_year,exact_units_managed,units_evidence_quote,
                estimated_units_tier,employee_count_est,reference_buildings_count,manages_weg,
                manages_miet,manages_gewerbe,manages_sev,has_customer_portal,
                detected_erp_proptech,incumbent_metering_signal,digital_maturity_score,
                qualification_reasoning,llm_provider_used,extracted_at
            ) VALUES (?,1998,3200,'3,200 units','1,000-5,000',15,40,1,1,0,0,1,
                'Casavi','Techem',4,'Evidence-backed summary','deterministic','now')""",
            (company_id,),
        )
        conn.execute(
            """INSERT INTO decision_makers (
                company_id,full_name,first_name,last_name,role,personal_email,email_status,
                mx_valid,mx_host,direct_phone,linkedin_url,source_url,evidence_quote,is_primary_contact
            ) VALUES (?, 'Max Mustermann','Max','Mustermann','Director','max@alpha.example',
                'PUBLIC_LISTED',1,'mx.alpha.example','+4930555123','https://linkedin.com/in/max',
                'https://alpha.example/impressum','Impressum: Max Mustermann',1)""",
            (company_id,),
        )
        conn.execute(
            """INSERT INTO decision_makers (company_id,full_name,role,is_primary_contact)
               VALUES (?, 'Anna Schmidt','Director',0)""",
            (company_id,),
        )
        conn.execute(
            """INSERT INTO crawled_pages (
                company_id,page_type,url,http_status,clean_markdown,detected_erp_csv,
                detected_metering_csv,has_portal_link,crawled_at
            ) VALUES (?, 'impressum','https://alpha.example/impressum',200,
                'Evidence text','Casavi','Techem',1,'now')""",
            (company_id,),
        )

    xlsx, csv_path = export_dir / "complete.xlsx", export_dir / "complete.csv"
    result = ExcelExporter(db).export_all(xlsx, csv_path)
    assert Path(result["xlsx_path"]).exists() and Path(result["csv_path"]).exists()
    workbook = load_workbook(xlsx, read_only=True)
    assert workbook.sheetnames == [
        "Qualified_Berlin_Leads",
        "All_Decision_Makers_Contacts",
        "Evidence_And_Audit_Trail",
        "KPI_Methodology_And_Summary",
    ]
    assert workbook["Qualified_Berlin_Leads"].max_row == 2
    assert workbook["All_Decision_Makers_Contacts"].max_row == 3
    assert workbook["Evidence_And_Audit_Trail"].max_row == 2
