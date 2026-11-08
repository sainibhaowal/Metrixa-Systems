export type LeadTier =
  | "Tier A (High Priority)"
  | "Tier B (Qualified Mid-Market)"
  | "Tier C (Long-Tail / Small)"
  | "Disqualified";

export interface LeadItem {
  company_id: number;
  lead_id: string;
  display_name: string;
  legal_form: string | null;
  commercial_register_id: string | null;
  street_address: string | null;
  postal_code: string | null;
  city: string;
  district: string;
  phone_e164: string | null;
  website_url: string | null;
  canonical_domain: string | null;
  general_email: string | null;
  company_linkedin_url: string | null;
  is_vdiv_member: boolean;
  source_count: number;
  sources_csv: string;
  metrixa_lead_score: number;
  lead_tier: LeadTier;
  founding_year: number | null;
  exact_units_managed: number | null;
  units_evidence_quote: string | null;
  estimated_units_tier: string;
  employee_count_est: number | null;
  manages_weg: boolean;
  manages_miet: boolean;
  manages_gewerbe: boolean;
  manages_sev: boolean;
  has_customer_portal: boolean;
  detected_erp_proptech: string | null;
  incumbent_metering_signal: string | null;
  digital_maturity_score: number;
  qualification_reasoning: string;
  decision_maker_name: string | null;
  decision_maker_role: string | null;
  personal_email: string | null;
  email_status: string;
  linkedin_url: string | null;
}

export interface DecisionMaker {
  contact_id?: number;
  full_name: string;
  role: string;
  personal_email: string | null;
  email_status: string;
  mx_valid: boolean;
  mx_host: string | null;
  direct_phone: string | null;
  linkedin_url: string | null;
  evidence_quote: string;
}

export interface CrawledPage {
  page_type: string;
  url: string;
  http_status: number;
  clean_markdown: string;
  detected_erp: string | null;
  detected_metering: string | null;
}

export interface ScorecardBreakdown {
  scale_pts: number;
  focus_pts: number;
  digital_pts: number;
  trust_pts: number;
  contact_pts: number;
  total_score: number;
}

export interface LeadEvidenceDossier {
  company: LeadItem;
  kpi: any;
  scorecard: ScorecardBreakdown;
  decision_makers: DecisionMaker[];
  crawled_pages: CrawledPage[];
}

export interface MetricsResponse {
  status: string;
  raw_total: number;
  golden_total: number;
  tiers: Record<string, number>;
  coverage: {
    with_website: number;
    with_customer_portal: number;
    with_erp_stack: number;
    with_decision_maker: number;
    with_personal_email: number;
    with_linkedin: number;
    crawled_pages: number;
  };
  erp_breakdown: Record<string, number>;
  district_breakdown: { district: string; count: number }[];
  pipeline_state: {
    is_running: boolean;
    current_stage: string;
  };
}

export interface PipelineEvent {
  type: "LOG" | "PROGRESS" | "COMPLETE" | "ERROR" | "HEARTBEAT";
  stage?: string;
  level?: "INFO" | "SUCCESS" | "WARN" | "ERROR";
  message?: string;
  completed?: number;
  total?: number;
  pct?: number;
  run_id?: string;
  timestamp?: string;
}

export interface ToolItem {
  id: string;
  name: string;
  category: string;
  status: string;
  description: string;
  records_extracted: number;
  engine?: string;
  target?: string;
}
