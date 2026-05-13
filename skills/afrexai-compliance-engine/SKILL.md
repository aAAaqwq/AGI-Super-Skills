# Compliance & Audit Readiness Engine

Your AI compliance officer. Guides startups and scale-ups through SOC 2, ISO 27001, GDPR, HIPAA, and PCI DSS — from zero to audit-ready. No consultants needed.

---

## Phase 1 — Compliance Discovery

### Framework Selection Matrix

| Framework | Who Needs It | Trigger | Timeline | Cost Range |
|-----------|-------------|---------|----------|------------|
| **SOC 2 Type I** | Any B2B SaaS | Enterprise prospect asks | 3-6 months | $20K-$80K |
| **SOC 2 Type II** | Established SaaS | After Type I, or direct | 6-12 months | $30K-$100K |
| **ISO 27001** | Global/EU-facing SaaS | EU enterprise deals | 6-12 months | $40K-$120K |
| **GDPR** | Anyone with EU users | Day 1 if EU data | 1-3 months | $5K-$30K |
| **HIPAA** | Health data handlers | Before first PHI | 3-6 months | $20K-$60K |
| **PCI DSS** | Payment processors | Before card data | 3-9 months | $15K-$50K |
| **SOX** | Public companies | IPO prep | 12-18 months | $100K-$500K |

### Readiness Assessment Brief

```yaml
company_profile:
  name: ""
  industry: ""
  employee_count: 0
  annual_revenue: ""
  data_types_handled:
    - PII (names, emails, addresses)
    - Financial (payment cards, bank accounts)
    - Health (PHI, medical records)
    - Children (COPPA scope)
    - Biometric
    - Government/classified
  customer_segments:
    - SMB
    - Mid-market
    - Enterprise
    - Government
  geographic_scope:
    - US only
    - US + EU
    - Global
  current_state:
    existing_frameworks: []
    security_team_size: 0
    has_written_policies: false
    has_asset_inventory: false
    has_risk_assessment: false
    has_incident_response: false
    has_vendor_management: false
    previous_audits: []
    known_gaps: []
  drivers:
    - Customer requirement
    - Board/investor mandate
    - Regulatory obligation
    - Competitive advantage
    - Insurance requirement
  target_frameworks: []
  target_date: ""
  budget_range: ""
```

### Priority Decision Rules

1. **Customer asking for SOC 2?** → Start there (most requested in B2B SaaS)
2. **EU customers?** → GDPR is non-negotiable, do it alongside SOC 2
3. **Health data?** → HIPAA first, then layer SOC 2
4. **Payment data?** → PCI DSS is legally required, do immediately
5. **Multiple frameworks?** → Map common controls (40-60% overlap between SOC 2 and ISO 27001)

---

## Phase 2 — SOC 2 Deep Dive

### Trust Service Criteria (TSC)

SOC 2 is built on 5 categories. **Security** is mandatory. Others are optional but often expected.

#### CC1 — Control Environment (Foundation)
- [ ] Board/management oversight of security
- [ ] Organizational structure with clear security roles
- [ ] Code of conduct / acceptable use policy
- [ ] HR processes (background checks, onboarding, offboarding)
- [ ] Performance evaluations include security responsibilities

#### CC2 — Communication & Information
- [ ] Security policies documented and accessible to all employees
- [ ] External communication channels for security (status page, security@)
- [ ] Whistleblower / anonymous reporting mechanism
- [ ] Security awareness training program (annual + onboarding)
- [ ] System description document maintained

#### CC3 — Risk Assessment
- [ ] Annual risk assessment process documented
- [ ] Risk register maintained with likelihood × impact scoring
- [ ] Risk treatment plans for high/critical risks
- [ ] Risk appetite statement approved by management
- [ ] Changes in business/technology trigger risk re-assessment

#### CC4 — Monitoring Activities
- [ ] Continuous monitoring of controls (not just annual)
- [ ] Internal audit or self-assessment program
- [ ] Deficiency tracking and remediation
- [ ] Management review of monitoring results
- [ ] Penetration testing (annual minimum)

#### CC5 — Control Activities
- [ ] Logical access controls (RBAC, least privilege)
- [ ] Physical access controls (offices, data centers)
- [ ] Change management process
- [ ] System development lifecycle (SDLC)
- [ ] Data backup and recovery procedures

#### CC6 — Logical & Physical Access
- [ ] User provisioning and deprovisioning process
- [ ] MFA enforced on all critical systems
- [ ] Password policy (12+ chars, complexity, rotation)
- [ ] Access reviews (quarterly minimum)
- [ ] Physical access logs for sensitive areas
- [ ] Encryption at rest (AES-256) and in transit (TLS 1.2+)
- [ ] Firewall rules reviewed quarterly
- [ ] VPN or zero-trust network access

#### CC7 — System Operations
- [ ] Monitoring and alerting (uptime, errors, security events)
- [ ] Incident detection and response procedures
- [ ] Vulnerability management (scan weekly, patch critical <72h)
- [ ] Anti-malware / endpoint protection
- [ ] Capacity planning and performance monitoring

#### CC8 — Change Management
- [ ] Formal change request and approval process
- [ ] Separation of duties (dev ≠ prod deploy)
- [ ] Testing before production deployment
- [ ] Rollback procedures documented
- [ ] Emergency change process with post-hoc approval

#### CC9 — Risk Mitigation (Vendors)
- [ ] Vendor risk assessment before onboarding
- [ ] Vendor inventory with criticality ratings
- [ ] Annual vendor reviews
- [ ] BAAs / DPAs with sub-processors
- [ ] Vendor offboarding process

### Additional Criteria

**Availability (A1):**
- [ ] SLAs defined and monitored
- [ ] Disaster recovery plan tested annually
- [ ] Business continuity plan documented
- [ ] RTO/RPO defined for critical systems
- [ ] Redundancy for critical infrastructure

**Confidentiality (C1):**
- [ ] Data classification scheme (Public, Internal, Confidential, Restricted)
- [ ] Handling procedures per classification level
- [ ] Confidentiality agreements (NDA) with employees and vendors
- [ ] Data retention and disposal policies
- [ ] DLP controls for sensitive data

**Processing Integrity (PI1):**
- [ ] Input validation controls
- [ ] Processing completeness and accuracy checks
- [ ] Output reconciliation procedures
- [ ] Error handling and correction processes

**Privacy (P1):**
- [ ] Privacy notice published
- [ ] Consent mechanisms for data collection
- [ ] Data subject rights procedures (access, deletion, portability)
- [ ] Privacy impact assessments for new features
- [ ] Data breach notification procedures

### SOC 2 Project Plan (16-Week Sprint)

| Week | Phase | Key Activities |
|------|-------|---------------|
| 1-2 | **Scoping** | Define system boundaries, select TSC, choose auditor |
| 3-4 | **Gap Assessment** | Audit current state against TSC, document gaps |
| 5-6 | **Policy Writing** | Draft all required policies (see policy list below) |
| 7-8 | **Control Implementation** | Deploy technical controls, configure tools |
| 9-10 | **Process Implementation** | Establish operational processes, train team |
| 11-12 | **Evidence Collection** | Gather evidence for all controls, test internally |
| 13-14 | **Readiness Assessment** | Mock audit, remediate findings |
| 15-16 | **Type I Audit** | Auditor fieldwork, management response, report |

### Required Policy Documents

1. **Information Security Policy** — Master policy, scope, objectives
2. **Access Control Policy** — Authentication, authorization, reviews
3. **Change Management Policy** — SDLC, deployment, emergency changes
4. **Incident Response Policy** — Detection, response, notification
5. **Risk Management Policy** — Assessment methodology, treatment, appetite
6. **Data Classification Policy** — Levels, handling, retention, disposal
7. **Acceptable Use Policy** — Employee responsibilities, prohibited actions
8. **Vendor Management Policy** — Assessment, monitoring, offboarding
9. **Business Continuity / DR Policy** — Plans, testing, RTO/RPO
10. **HR Security Policy** — Background checks, onboarding, offboarding, training
11. **Encryption Policy** — Standards, key management, certificate handling
12. **Physical Security Policy** — Office access, visitor management, clean desk
13. **Logging & Monitoring Policy** — What to log, retention, alerting
14. **Password & Authentication Policy** — Standards, MFA requirements
15. **Backup & Recovery Policy** — Schedule, testing, retention

### Policy Template

```markdown
# [Policy Name]

**Version:** 1.0
**Owner:** [Name, Title]
**Approved by:** [Name, Title]
**Effective date:** [Date]
**Next review:** [Date + 1 year]
**Classification:** Internal

## 1. Purpose
[Why this policy exists — 2-3 sentences]

## 2. Scope
[Who and what this policy applies to]

## 3. Policy Statements
[Numbered, actionable requirements — not aspirational]

### 3.1 [Topic]
- SHALL [requirement]
- SHALL NOT [prohibition]
- SHOULD [recommendation]

## 4. Roles & Responsibilities
| Role | Responsibility |
|------|---------------|
| [Role] | [What they must do] |

## 5. Exceptions
[Process for requesting exceptions — who approves, how long, documentation]

## 6. Enforcement
[Consequences of non-compliance]

## 7. Definitions
[Technical terms used in the policy]

## 8. Related Documents
[Links to related policies, standards, procedures]

## 9. Revision History
| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | [Date] | [Author] | Initial release |
```

---

## Phase 3 — ISO 27001 Framework

### ISMS Implementation Roadmap

#### Clause 4 — Context of the Organization
- [ ] Define ISMS scope and boundaries
- [ ] Identify interested parties and their requirements
- [ ] Determine internal and external issues
- [ ] Document scope statement

#### Clause 5 — Leadership
- [ ] Management commitment statement
- [ ] Information security policy (signed by CEO/CTO)
- [ ] Assign ISMS roles and responsibilities
- [ ] Allocate resources (budget, people, tools)

#### Clause 6 — Planning
- [ ] Risk assessment methodology (ISO 27005 or custom)
- [ ] Risk assessment execution
- [ ] Risk treatment plan
- [ ] Statement of Applicability (SoA) — map all 93 Annex A controls
- [ ] Information security objectives (measurable, time-bound)

#### Clause 7 — Support
- [ ] Determine required competencies
- [ ] Security awareness program
- [ ] Internal and external communication plan
- [ ] Document control process

#### Clause 8 — Operation
- [ ] Execute risk treatment plan
- [ ] Implement controls from SoA
- [ ] Manage operational changes
- [ ] Conduct risk assessments on changes

#### Clause 9 — Performance Evaluation
- [ ] Monitoring and measurement program
- [ ] Internal audit schedule and execution
- [ ] Management review (at least annually)
- [ ] Corrective action tracking

#### Clause 10 — Improvement
- [ ] Nonconformity and corrective action process
- [ ] Continual improvement program
- [ ] Lessons learned integration

### ISO 27001:2022 Annex A Control Categories

| Category | Controls | Key Areas |
|----------|----------|-----------|
| A.5 Organizational | 37 | Policies, roles, threat intel, asset mgmt, access, supplier |
| A.6 People | 8 | Screening, T&C, awareness, disciplinary, termination |
| A.7 Physical | 14 | Perimeters, entry, offices, monitoring, utilities, cabling |
| A.8 Technological | 34 | Endpoints, access rights, auth, malware, vuln mgmt, logging, crypto, SDLC |

### SOC 2 ↔ ISO 27001 Control Mapping (Save 40-60% effort)

| SOC 2 TSC | ISO 27001 Annex A | Overlap |
|-----------|------------------|---------|
| CC1 Control Environment | A.5.1-5.6 (Org controls) | ~80% |
| CC2 Communication | A.5.1, A.6.3 (Awareness) | ~70% |
| CC3 Risk Assessment | Clause 6.1, A.5.7 (Threat intel) | ~90% |
| CC5 Control Activities | A.8 (Technological) | ~75% |
| CC6 Access | A.5.15-5.18, A.8.1-8.5 | ~85% |
| CC7 Operations | A.8.7-8.16 (Monitoring) | ~80% |
| CC8 Change Mgmt | A.8.25-8.33 (SDLC) | ~70% |
| CC9 Vendors | A.5.19-5.23 (Supplier) | ~85% |

**Strategy:** Build for one framework, extend to the other. SOC 2 first (faster) → ISO 27001 (adds clauses 4-10 management system).

---

## Phase 4 — GDPR Compliance Program

### 12 Core Requirements

1. **Lawful Basis for Processing** — Document legal basis for each data processing activity
   - Consent | Contract | Legal obligation | Vital interest | Public task | Legitimate interest
   - [ ] Data processing register (Article 30)
   - [ ] Legitimate Interest Assessments (LIAs) where applicable

2. **Data Subject Rights** — Respond within 30 days
   - [ ] Right of access (SAR) process
   - [ ] Right to rectification
   - [ ] Right to erasure ("right to be forgotten")
   - [ ] Right to data portability (machine-readable export)
   - [ ] Right to restrict processing
   - [ ] Right to object
   - [ ] Automated decision-making opt-out

3. **Privacy by Design & Default** — Build privacy into products
   - [ ] Privacy Impact Assessment (PIA/DPIA) template
   - [ ] Data minimization review for each feature
   - [ ] Default privacy settings (opt-in, not opt-out)

4. **Data Protection Officer (DPO)** — Required if:
   - Public authority, OR
   - Large-scale systematic monitoring, OR
   - Large-scale processing of special category data

5. **Consent Management**
   - [ ] Granular consent mechanisms (not bundled)
   - [ ] Easy withdrawal (as easy as giving consent)
   - [ ] Consent records with timestamp, version, scope
   - [ ] Cookie consent banner (ePrivacy)

6. **Data Processing Agreements (DPAs)**
   - [ ] DPA template for sub-processors
   - [ ] Article 28 requirements checklist
   - [ ] Sub-processor notification process
   - [ ] Sub-processor register

7. **International Transfers**
   - [ ] Transfer mechanism (SCCs, adequacy decision, BCRs)
   - [ ] Transfer Impact Assessment
   - [ ] Supplementary measures where needed

8. **Breach Notification**
   - [ ] 72-hour notification to supervisory authority
   - [ ] "Undue delay" notification to affected individuals
   - [ ] Breach register with risk assessment
   - [ ] Breach response team and escalation path

9. **Records of Processing Activities (ROPA)**

```yaml
processing_activity:
  name: ""
  purpose: ""
  lawful_basis: ""
  data_categories: []
  data_subjects: []
  recipients: []
  retention_period: ""
  transfers_outside_eea: false
  transfer_mechanism: ""
  technical_measures: []
  organizational_measures: []
  dpia_required: false
  last_reviewed: ""
```

10. **Privacy Notice** — Must include:
    - Identity of controller
    - DPO contact (if applicable)
    - Purposes and lawful basis
    - Categories of data
    - Recipients / transfers
    - Retention periods
    - Data subject rights
    - Right to complain to supervisory authority
    - Whether providing data is statutory/contractual requirement

11. **Data Retention Schedule**

| Data Type | Retention Period | Legal Basis | Disposal Method |
|-----------|-----------------|-------------|-----------------|
| Customer PII | Duration + 3 years | Contract + legitimate interest | Automated deletion |
| Employee records | Duration + 7 years | Legal obligation | Secure shred |
| Financial records | 7 years | Legal obligation | Secure shred |
| Server logs | 90 days | Legitimate interest | Automated rotation |
| Marketing consent | Until withdrawn | Consent | Database purge |
| Support tickets | 2 years after resolution | Legitimate interest | Automated deletion |

12. **Training & Awareness**
    - [ ] Mandatory GDPR training for all employees (annual)
    - [ ] Role-specific training (developers, support, marketing, HR)
    - [ ] Training records with completion tracking

---

## Phase 5 — HIPAA Compliance (Health Data)

### HIPAA Security Rule — 3 Safeguard Categories

#### Administrative Safeguards
- [ ] Security Management Process (risk analysis, risk management)
- [ ] Assigned Security Responsibility (HIPAA Security Officer)
- [ ] Workforce Security (authorization, clearance, termination)
- [ ] Information Access Management (access authorization, establishment, modification)
- [ ] Security Awareness Training (reminders, malware, login monitoring, password mgmt)
- [ ] Security Incident Procedures (response, reporting)
- [ ] Contingency Plan (backup, DR, emergency mode, testing)
- [ ] Evaluation (periodic technical/non-technical)
- [ ] BAAs with all business associates

#### Physical Safeguards
- [ ] Facility Access Controls (contingency ops, facility security plan, access control, maintenance records)
- [ ] Workstation Use (policies, restrictions)
- [ ] Workstation Security (physical safeguards)
- [ ] Device and Media Controls (disposal, re-use, accountability, data backup)

#### Technical Safeguards
- [ ] Access Control (unique user ID, emergency access, automatic logoff, encryption)
- [ ] Audit Controls (hardware, software, procedural mechanisms)
- [ ] Integrity Controls (authentication of ePHI, transmission security)
- [ ] Person or Entity Authentication (verify identity)
- [ ] Transmission Security (integrity controls, encryption)

### HIPAA Breach Rule
- **≤500 individuals:** Annual batch notification to HHS (within 60 days of year end)
- **>500 individuals:** Notify HHS within 60 days + media notification
- **All breaches:** Notify affected individuals without unreasonable delay (≤60 days)
- **Penalties:** $100-$50,000 per violation, up to $1.5M per year per category

---

## Phase 6 — PCI DSS 4.0 (Payment Data)

### 12 Requirements Summary

| # | Requirement | Key Controls |
|---|------------|-------------|
| 1 | Install/maintain network security controls | Firewalls, network segmentation |
| 2 | Apply secure configurations | No vendor defaults, CIS benchmarks |
| 3 | Protect stored account data | Encryption, masking, key mgmt |
| 4 | Encrypt transmission over open networks | TLS 1.2+, no SSL/early TLS |
| 5 | Protect from malicious software | Anti-malware, regular updates |
| 6 | Develop secure systems | SDLC, vuln mgmt, WAF |
| 7 | Restrict access by business need | RBAC, least privilege |
| 8 | Identify users and authenticate | MFA, password standards |
| 9 | Restrict physical access | Badges, cameras, visitor logs |
| 10 | Log and monitor all access | Centralized logging, review |
| 11 | Test security regularly | Vuln scans, pen tests, IDS |
| 12 | Support security with policies | Policies, training, incident response |

### Scope Reduction Strategy
- **Use tokenization** — Replace card data with tokens (Stripe, Braintree handle PCI for you)
- **Use hosted payment pages** — Never touch raw card data (SAQ A instead of SAQ D)
- **Network segmentation** — Isolate cardholder data environment
- **Cloud provider compliance** — Leverage AWS/GCP/Azure PCI certifications

**SAQ Decision:**
- Fully outsourced (Stripe Checkout) → **SAQ A** (22 controls, simplest)
- API-based (Stripe Elements) → **SAQ A-EP** (~140 controls)
- You store/process card data → **SAQ D** (300+ controls, avoid this)

---

## Phase 7 — Compliance Tooling Stack

### Essential Tools by Category

| Category | Budget Option | Mid-Range | Enterprise |
|----------|-------------|-----------|-----------|
| GRC Platform | Notion/Sheets | Vanta, Drata | ServiceNow, OneTrust |
| Policy Mgmt | Google Docs + versioning | Vanta policies | Hyperproof |
| Vulnerability Scanning | OWASP ZAP, Trivy | Qualys, Tenable | Rapid7 |
| SIEM/Logging | ELK Stack, Wazuh | Datadog, Sumo Logic | Splunk |
| Endpoint Protection | CrowdStrike Falcon Go | SentinelOne | CrowdStrike Enterprise |
| Identity/Access | Google Workspace + Okta | JumpCloud | Azure AD P2 |
| Training | KnowBe4 Free | KnowBe4 | Proofpoint |
| Pen Testing | HackerOne Community | Cobalt | Bishop Fox |
| Backup | Native cloud backups | Veeam | Commvault |

### Automation-First Compliance

**What to automate (saves 70%+ of audit prep):**
- Evidence collection (screenshots of configs → API pulls)
- Access reviews (quarterly manual → continuous monitoring)
- Vulnerability scanning (manual → scheduled + auto-ticket)
- Policy acknowledgment (email → onboarding workflow)
- Vendor assessments (spreadsheets → intake forms with scoring)
- Training tracking (manual → LMS with auto-reminders)

### Compliance-as-Code Patterns

```
# Infrastructure compliance
- Terraform with Sentinel policies (enforce encryption, tagging)
- OPA/Rego for Kubernetes admission control
- AWS Config Rules / Azure Policy for cloud compliance
- GitHub branch protection rules as change management evidence

# Application compliance
- Automated dependency scanning in CI (Snyk, Dependabot)
- SAST in PR pipeline (Semgrep, CodeQL)
- Container scanning (Trivy, Grype)
- License compliance (FOSSA, Licensee)
```

---

## Phase 8 — Audit Preparation

### 90-Day Audit Prep Checklist

**Days 90-60: Foundation**
- [ ] Confirm audit scope with auditor
- [ ] Complete system description document
- [ ] Verify all policies are current (reviewed within 12 months)
- [ ] Confirm all employees completed security training
- [ ] Run vulnerability scan and remediate critical/high findings
- [ ] Schedule penetration test (results needed before audit)

**Days 60-30: Evidence Gathering**
- [ ] Collect evidence for each control (organized by TSC/clause)
- [ ] Access review documentation (screenshots of reviews, action items)
- [ ] Change management evidence (sample of tickets showing approval flow)
- [ ] Incident response test evidence (tabletop exercise minutes)
- [ ] DR test evidence (recovery test results, RTO achieved)
- [ ] Vendor review evidence (assessment records, DPAs)
- [ ] Risk assessment and treatment plan (current year)
- [ ] Board/management meeting minutes discussing security

**Days 30-0: Final Prep**
- [ ] Internal mock audit — walk through every control
- [ ] Remediate any mock audit findings
- [ ] Brief team on auditor interviews (what to expect, who answers what)
- [ ] Prepare management assertion letter
- [ ] Set up auditor access (read-only to evidence repository)
- [ ] Confirm all monitoring/alerting is functioning
- [ ] Verify offboarding was completed for all departed employees

### Evidence Organization

```
/compliance-evidence/
  /SOC2-2026/
    /CC1-control-environment/
      org-chart.pdf
      code-of-conduct-signed.pdf
      background-check-process.pdf
    /CC2-communication/
      security-training-completion.csv
      security-policy-acknowledgments.pdf
    /CC3-risk-assessment/
      risk-assessment-2026.xlsx
      risk-treatment-plan.pdf
    /CC6-access/
      access-review-Q1.pdf
      access-review-Q2.pdf
      mfa-enforcement-screenshot.png
      offboarding-checklist-samples/
    /CC7-operations/
      vulnerability-scan-reports/
      pentest-report-2026.pdf
      incident-log-2026.csv
    /CC8-change-management/
      sample-change-tickets/
      deployment-pipeline-config.png
    /CC9-vendors/
      vendor-inventory.xlsx
      vendor-assessments/
      dpas-and-baas/
```

### Auditor Interview Prep

**Common questions and who should answer:**

| Question | Best Respondent | Key Points |
|----------|----------------|-----------|
| "Walk me through your risk assessment process" | CISO/Security Lead | Methodology, frequency, treatment |
| "How do you manage access to production?" | Engineering Lead | RBAC, approval flow, reviews |
| "Describe your change management process" | Engineering Lead | PR review, testing, deployment |
| "How do you handle security incidents?" | Security Lead | Detection, response, communication |
| "How do you evaluate vendors?" | Security/Procurement | Assessment, monitoring, contracts |
| "Describe your backup and recovery process" | Infrastructure Lead | Schedule, testing, RTO/RPO |
| "How do you track and remediate vulnerabilities?" | Security Lead | Scanning, SLAs, patching |
| "Walk me through employee onboarding/offboarding" | HR + IT | Checklist, timing, verification |

---

## Phase 9 — Continuous Compliance

### Monthly Compliance Dashboard

```yaml
compliance_dashboard:
  month: ""
  
  control_health:
    total_controls: 0
    controls_passing: 0
    controls_failing: 0
    controls_not_tested: 0
    health_percentage: 0
    
  action_items:
    open: 0
    overdue: 0
    closed_this_month: 0
    
  key_metrics:
    mean_time_to_patch_critical: ""
    access_reviews_completed: "X/X"
    security_training_completion: ""
    incidents_this_month: 0
    vendor_reviews_due: 0
    policies_due_for_review: 0
    
  risk_register:
    high_risks: 0
    risks_without_treatment: 0
    new_risks_identified: 0
    
  upcoming:
    next_pen_test: ""
    next_dr_test: ""
    next_audit: ""
    next_access_review: ""
```

### Compliance Calendar

| Frequency | Activity |
|-----------|----------|
| **Weekly** | Review security alerts, patch critical vulln |
| **Monthly** | Control testing sample, metrics dashboard, policy exception review |
| **Quarterly** | Access reviews, vendor risk check, risk register update, tabletop exercise |
| **Semi-annual** | Vulnerability scan (external), BCP/DR test, security training refresh |
| **Annual** | Full risk assessment, penetration test, policy review cycle, SOC 2/ISO audit, security awareness training, management review |

### Compliance Debt Tracker

```yaml
compliance_debt:
  - id: "CD-001"
    framework: "SOC 2"
    control: "CC6.1"
    finding: "MFA not enforced on staging environment"
    severity: "High"
    identified: "2026-01-15"
    owner: ""
    target_remediation: "2026-02-15"
    status: "In Progress"
    compensating_control: "VPN + IP allowlisting"
```

### When Controls Fail

**Severity-based response:**

| Severity | Response Time | Actions |
|----------|-------------|---------|
| **Critical** | 24 hours | Immediate remediation, notify management, consider if breach occurred |
| **High** | 7 days | Remediation plan, compensating control if needed, risk acceptance by CISO |
| **Medium** | 30 days | Add to sprint, track in compliance debt |
| **Low** | 90 days | Batch with next review cycle |

---

## Phase 10 — Multi-Framework Management

### Common Control Framework (CCF)

Build controls ONCE, map to MULTIPLE frameworks:

```yaml
control:
  id: "CCF-AC-001"
  title: "Multi-Factor Authentication"
  description: "MFA required for all access to production systems and sensitive data"
  owner: "Security Team"
  
  framework_mapping:
    soc2: ["CC6.1", "CC6.6"]
    iso27001: ["A.8.5"]
    gdpr: ["Article 32"]
    hipaa: ["§164.312(d)"]
    pci_dss: ["Req 8.4"]
    
  evidence:
    - type: "Configuration screenshot"
      source: "Okta MFA policy"
      frequency: "Quarterly"
    - type: "Access review"
      source: "Okta user report"
      frequency: "Quarterly"
      
  test_procedure: "Verify MFA policy is enforced, test with non-MFA login attempt"
  last_tested: ""
  result: ""
  next_test: ""
```

### Framework Expansion Strategy

**Year 1:** SOC 2 Type I → establishes baseline
**Year 1-2:** SOC 2 Type II → proves sustained operation
**Year 2:** + GDPR → covers EU expansion
**Year 2-3:** + ISO 27001 → international credibility
**As needed:** + HIPAA / PCI DSS → industry-specific

### Audit Fatigue Prevention

- **Single evidence repository** — collect once, map to all frameworks
- **Continuous monitoring** — evidence auto-collected, not scrambled at audit time
- **Control owner accountability** — each control has ONE owner, not "security team"
- **Compliance sprints** — 2-week sprints dedicated to compliance work, not crammed before audit
- **Auditor relationship** — same firm for multiple frameworks if possible (they know your environment)

---

## Phase 11 — Scoring & Quality

### Compliance Readiness Score (0-100)

| Dimension | Weight | Score 0-10 |
|-----------|--------|-----------|
| **Policy Coverage** — All required policies exist, reviewed, approved | 15% | |
| **Technical Controls** — Security tools deployed and configured | 20% | |
| **Process Maturity** — Operational processes followed consistently | 20% | |
| **Evidence Quality** — Complete, organized, recent evidence | 15% | |
| **Training & Awareness** — All employees trained, records maintained | 10% | |
| **Vendor Management** — All critical vendors assessed and contracted | 10% | |
| **Risk Management** — Current assessment, treatment plans, monitoring | 10% | |

**Scoring guide:**
- 0-2: Not started / major gaps
- 3-4: In progress / significant gaps
- 5-6: Partially implemented / some gaps
- 7-8: Implemented / minor improvements needed
- 9-10: Mature / audit-ready

**Interpretation:**
- **< 40:** Not ready — significant work needed (3-6 months)
- **40-60:** Getting there — focus on gaps (1-3 months)
- **60-80:** Nearly ready — polish and evidence gathering (2-6 weeks)
- **80+:** Audit-ready — schedule the audit

---

## Edge Cases & Special Situations

### Startup with Zero Compliance
- Start with **security basics** (MFA, encryption, access control, backups) before any framework
- Use a GRC platform from Day 1 (Vanta/Drata cost $10-15K/yr but save 100+ hours)
- Don't wait for perfect — "documented and improving" beats "undocumented and perfect"
- Budget $20-40K for first SOC 2 Type I (auditor + tools + time)

### Multi-Cloud / Hybrid Infrastructure
- Map shared responsibility model for each provider
- Ensure consistent controls across environments
- Consider cloud-specific compliance tools (AWS Audit Manager, Azure Compliance Manager)
- Network segmentation especially important

### Acquired Company Integration
- Conduct compliance gap assessment within 30 days of close
- Identify highest-risk gaps (access control, data handling)
- 90-day integration plan to bring to baseline
- Don't assume their compliance posture matches claims

### International (Multi-Jurisdiction)
- Map all jurisdictions where you operate or store data
- GDPR applies if you have EU *users* — not just EU office
- Data residency requirements (Russia, China, India, Brazil)
- Consider local DPA registrations

### Regulated Industries (FinTech, HealthTech)
- Layer industry regulations ON TOP of SOC 2/ISO
- FinTech: SOC 2 + PCI DSS + potentially banking regs (state MTLs, FinCEN)
- HealthTech: SOC 2 + HIPAA + potentially FDA (SaMD)
- EdTech: SOC 2 + FERPA + COPPA (if under 13)

---

## Natural Language Commands

| Command | What It Does |
|---------|-------------|
| "Assess our compliance readiness" | Run readiness assessment, score, identify gaps |
| "Create SOC 2 project plan" | Generate 16-week implementation timeline |
| "Write [policy name] policy" | Generate policy from template with your context |
| "Map controls across frameworks" | Build common control framework mapping |
| "Prepare for audit" | Generate 90-day audit prep checklist with evidence needs |
| "Review our GDPR compliance" | Check all 12 GDPR requirements against current state |
| "Score our compliance posture" | Run 7-dimension scoring rubric |
| "Generate evidence checklist" | List all evidence needed for specific framework |
| "Build vendor assessment" | Create vendor risk assessment for a specific vendor |
| "Plan framework expansion" | Recommend next framework based on business needs |
| "Track compliance debt" | Review and prioritize open compliance items |
| "Run monthly compliance review" | Update dashboard, check deadlines, identify actions |
