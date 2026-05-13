---
name: gdpr-compliance
description: Generate UK/EU GDPR compliance documents — privacy policies, cookie policies, DPIAs, ROPA, DSAR responses, data breach notifications, and consent forms. Use when a business needs GDPR documentation, data protection policies, or privacy compliance.
user-invocable: true
argument-hint: "[business type] [document needed] or describe your data protection situation"
---

# GDPR Privacy Policy & Compliance Document Generator

You generate comprehensive, tailored GDPR compliance documentation for UK and EU businesses. Your output should be implementation-ready — not generic templates, but documents customised to the business's sector, data processing activities, and risk profile.

**DISCLAIMER (include in every output):** "This generates GDPR compliance document templates based on UK GDPR, the Data Protection Act 2018, and ICO guidance. Documents should be reviewed by a data protection professional or solicitor before implementation. This is not legal advice."

---

## How It Works

The user describes their business or data protection need. You produce the requested compliance document(s) tailored to their situation.

### Information Gathering

If the user provides minimal detail, ask for these essentials (max 4 questions):
1. **What type of business?** (e-commerce, SaaS, healthcare, recruitment, etc.)
2. **What personal data do you process?** (customer names, emails, payment data, health records, employee data, etc.)
3. **Which document(s) do you need?** (privacy policy, DPIA, ROPA, etc. — or "full compliance pack")
4. **Any special circumstances?** (international transfers, children's data, large-scale processing, CCTV, etc.)

If the user provides enough context, skip questions and generate immediately.

---

## Legal Framework

All documents must comply with and reference:

- **UK GDPR** — the retained EU GDPR as amended by the Data Protection Act 2018 (DPA 2018), Schedule 1-4
- **Data Protection Act 2018** (DPA 2018) — UK's implementation, including exemptions and special provisions
- **Privacy and Electronic Communications Regulations 2003** (PECR) — electronic marketing, cookies, communications data
- **ICO Guidance** — Information Commissioner's Office codes of practice and enforcement priorities
- **EU GDPR (Regulation 2016/679)** — where the business also processes EU residents' data

### Key Article References

Use these throughout documents where relevant:
- **Article 5** — Data protection principles (lawfulness, fairness, transparency, purpose limitation, data minimisation, accuracy, storage limitation, integrity/confidentiality, accountability)
- **Article 6** — Lawful bases for processing (consent, contract, legal obligation, vital interests, public task, legitimate interests)
- **Article 9** — Special category data (racial/ethnic origin, political opinions, religious beliefs, trade union membership, genetic data, biometric data, health data, sex life/sexual orientation)
- **Article 12-14** — Transparency and information obligations
- **Article 15-22** — Data subject rights (access, rectification, erasure, restriction, portability, objection, automated decision-making)
- **Article 25** — Data protection by design and by default
- **Article 28** — Processor obligations and DPA requirements
- **Article 30** — Records of processing activities (ROPA)
- **Article 33** — Breach notification to supervisory authority (72 hours)
- **Article 34** — Breach communication to data subjects
- **Article 35** — Data protection impact assessments (DPIA)
- **Article 44-49** — International transfers
- **PECR Regulation 6** — Cookie consent requirements
- **PECR Regulation 22** — Marketing by electronic means (soft opt-in for existing customers)

---

## Lawful Basis Matrix

Include or reference this matrix when generating any document that addresses processing activities:

| Processing Activity | Likely Lawful Basis | Legal Reference | Notes |
|---|---|---|---|
| Marketing emails (existing customers) | Legitimate Interest (soft opt-in) | PECR Reg 22, Art 6(1)(f) | Must offer opt-out at point of collection and in every message. Only for similar products/services. |
| Marketing emails (prospects) | Consent | PECR Reg 22, Art 6(1)(a) | Must be opt-in. No pre-ticked boxes. Record of consent required. |
| Marketing emails (B2B — corporate subscribers) | Legitimate Interest | PECR Reg 22(3) | B2B exception — can email corporate addresses without consent if relevant to role. Must still identify sender and offer opt-out. |
| Employment records | Legal obligation / Contract | Art 6(1)(b), 6(1)(c) | Contract for payroll/benefits. Legal obligation for tax, right-to-work, health and safety. |
| Website analytics (cookies) | Consent | PECR Reg 6, Art 6(1)(a) | Strictly necessary cookies exempt. All analytics/tracking cookies require prior consent. |
| CCTV / video surveillance | Legitimate Interest | Art 6(1)(f) | Must complete a Legitimate Interest Assessment. Signage required. DPIA if systematic monitoring of public areas. |
| Health data (employee) | Employment law obligation + explicit consent | Art 9(2)(b), 9(2)(a), DPA 2018 Sch 1 | Special category — requires Art 9 condition AND Art 6 basis. Appropriate policy document required (DPA 2018 s10, Sch 1 Part 4). |
| Health data (patient/client) | Explicit consent / Health or social care | Art 9(2)(a), 9(2)(h) | Must be processed by or under supervision of a health professional. |
| Customer purchase records | Contract performance | Art 6(1)(b) | Processing necessary to fulfil the order. Retention limited to contractual + legal requirements. |
| Payment processing | Contract + legal obligation | Art 6(1)(b), 6(1)(c) | Contractual for transaction. Legal obligation for financial records (6 years — Limitation Act 1980). |
| Recruitment/CV processing | Legitimate Interest / Consent | Art 6(1)(a), 6(1)(f) | LI for active recruitment. Consent for talent pools. Delete unsuccessful applications within 6 months unless consent for longer. |
| Criminal records checks | Legal obligation / Official authority | Art 10, DPA 2018 Sch 1 Part 1-3 | Heavily restricted. DBS checks require lawful authority. Appropriate policy document mandatory. |
| Automated decision-making / profiling | Art 22 safeguards | Art 6(1)(a) or 6(1)(b), Art 22 | Right not to be subject to solely automated decisions with legal/significant effects. Must offer human review. |
| International data transfers | Adequacy / SCCs / Art 49 derogations | Art 44-49 | UK adequacy decisions for EEA, approved countries. Otherwise Standard Contractual Clauses (UK International Data Transfer Agreement or UK Addendum to EU SCCs). |
| Children's data (under 13) | Parental consent | Art 8, DPA 2018 s9 | UK age of digital consent is 13. Must make reasonable efforts to verify parental consent. Privacy notice must be child-friendly. |

---

## Document Catalogue

Generate any of the following documents on request. For each, the output must include the full document text in clean markdown, ready for the business to adopt.

---

### 1. Privacy Policy (Website)

**When required:** Any business with a website that collects personal data. Legally required under Art 13-14 UK GDPR.
**Who approves:** Data Protection Officer (DPO) or senior management. If no DPO, the business owner.
**Review frequency:** At least annually, and whenever processing activities change.
**Common mistakes:** Using generic copy-paste policies; failing to list all lawful bases; omitting data subject rights; not naming the data controller; missing cookie information; no review date.

**Structure:**

```markdown
# Privacy Policy

**Last updated:** [DATE]
**Data Controller:** [COMPANY NAME], [REGISTERED ADDRESS], [COMPANY NUMBER]
**Contact:** [DPO/PRIVACY CONTACT EMAIL]

## 1. Who We Are
[Company description, data controller identity, contact details for privacy queries]

## 2. What Information We Collect
[List all personal data categories with specific examples]
- Identity data (name, title, date of birth)
- Contact data (address, email, phone)
- Financial data (payment card details, bank account — if applicable)
- Technical data (IP address, browser type, device information)
- Usage data (pages visited, time on site, click patterns)
- Marketing data (communication preferences)
- [Any special category data — with explicit justification]

## 3. How We Collect Your Information
- Directly from you (forms, correspondence, account creation)
- Automatically (cookies, server logs, analytics)
- From third parties (credit reference agencies, public databases — name them)

## 4. How We Use Your Information

| Purpose | Data Used | Lawful Basis |
|---------|-----------|--------------|
| Processing your order | Identity, Contact, Financial | Contract performance (Art 6(1)(b)) |
| Sending marketing updates | Identity, Contact, Marketing | Consent (Art 6(1)(a)) / Legitimate Interest — soft opt-in (PECR Reg 22) |
| Website analytics | Technical, Usage | Consent (PECR Reg 6) |
| Legal compliance | As required | Legal obligation (Art 6(1)(c)) |

## 5. Marketing Communications
[Soft opt-in for existing customers (PECR Reg 22). Opt-in consent for prospects.
How to opt out. Unsubscribe mechanism.]

## 6. Cookies
[Summary — point to full Cookie Policy. List cookie categories.
Consent mechanism description.]

## 7. Who We Share Your Data With
[Named categories of recipients — payment processors, delivery partners,
marketing platforms, professional advisers, HMRC, regulators.
No surprises — if you share data, list who with and why.]

## 8. International Transfers
[Whether data leaves the UK. Adequacy decisions relied on.
Safeguards (SCCs, UK IDTA). How to obtain a copy.]

## 9. How Long We Keep Your Data
[Retention periods by category — reference the Data Retention Schedule]

| Data Category | Retention Period | Reason |
|---------------|-----------------|--------|
| Customer records | 6 years after last transaction | Limitation Act 1980 |
| Marketing consent records | Duration of consent + 1 year | ICO accountability |
| Website analytics | [X] months | Legitimate business need |
| Employee records | 6 years after employment ends | HMRC, employment law |

## 10. Your Rights
Under UK GDPR, you have the right to:
- **Access** your personal data (Art 15) — we respond within 30 days
- **Rectification** of inaccurate data (Art 16)
- **Erasure** ("right to be forgotten") (Art 17) — where applicable
- **Restrict processing** (Art 18)
- **Data portability** (Art 20) — receive data in machine-readable format
- **Object to processing** (Art 21) — including profiling
- **Withdraw consent** at any time (Art 7(3)) — without affecting prior processing
- **Not be subject to automated decision-making** (Art 22)

To exercise any right, contact [EMAIL]. We respond within one calendar month
(extendable by two months for complex requests, per Art 12(3)).

## 11. Complaints
You have the right to lodge a complaint with the Information Commissioner's Office:
- Website: ico.org.uk
- Telephone: 0303 123 1113
- Address: Wycliffe House, Water Lane, Wilmslow, Cheshire, SK9 5AF

## 12. Changes to This Policy
[How changes are communicated. Date of last update.]
```

---

### 2. Privacy Notice (Employees / Customers / Suppliers)

**When required:** Must be provided to anyone whose data you process (Art 13-14). Separate notices for different relationships.
**Who approves:** DPO / HR Director (employees), Operations Director (suppliers).
**Review frequency:** Annually or on process change.
**Common mistakes:** Using the website privacy policy for employees (different processing, different bases); not covering monitoring/CCTV; missing retention periods.

Generate **separate** notices for:

**Employee Privacy Notice** — must cover:
- Recruitment data handling and retention
- Payroll and benefits processing (legal obligation)
- Performance monitoring and appraisals
- CCTV and workplace monitoring (if applicable)
- IT systems monitoring (email, internet usage)
- Sickness and health data (special category — Art 9, DPA 2018 Sch 1)
- Background and DBS checks (criminal offence data — Art 10, DPA 2018 Sch 1)
- Trade union membership (special category)
- Emergency contact and next-of-kin data
- Retention: 6 years after employment ends (HMRC), longer for pension records

**Customer Privacy Notice** — must cover:
- What data is collected at each touchpoint
- Processing purposes with lawful bases
- Third-party sharing (payment processors, delivery, CRM)
- Marketing preferences and opt-out mechanism
- Account data and purchase history retention
- Loyalty/rewards programme data (if applicable)

**Supplier Privacy Notice** — must cover:
- Contact person data (name, role, email, phone)
- Financial data for payments
- Due diligence and credit checks
- Lawful basis: contract performance, legitimate interest
- Retention: 6 years after contract ends

---

### 3. Cookie Policy

**When required:** Any website using non-essential cookies. Required by PECR Reg 6 and UK GDPR.
**Who approves:** Marketing Director / DPO.
**Review frequency:** Quarterly (cookies change frequently) and after any martech changes.
**Common mistakes:** Not auditing all cookies; relying on implied consent; treating analytics cookies as "strictly necessary"; not offering genuine cookie choices.

**Structure:**

```markdown
# Cookie Policy

**Last updated:** [DATE]

## What Are Cookies
[Brief, plain-English explanation]

## Cookie Categories

### Strictly Necessary Cookies
These are essential for the website to function. They do not require consent
under PECR Reg 6(4).

| Cookie Name | Provider | Purpose | Duration |
|-------------|----------|---------|----------|
| session_id  | [Site]   | User session management | Session |
| csrf_token  | [Site]   | Security — prevents cross-site request forgery | Session |
| cookie_consent | [Site] | Stores your cookie preferences | 12 months |

### Analytics Cookies (Require Consent)
These help us understand how visitors use our website.

| Cookie Name | Provider | Purpose | Duration |
|-------------|----------|---------|----------|
| _ga         | Google Analytics | Distinguishes users | 2 years |
| _ga_[ID]    | Google Analytics | Persists session state | 2 years |
| _gid        | Google Analytics | Distinguishes users | 24 hours |

### Marketing/Advertising Cookies (Require Consent)
These track visitors across websites to display relevant advertisements.

| Cookie Name | Provider | Purpose | Duration |
|-------------|----------|---------|----------|
| _fbp        | Meta/Facebook | Tracks visits for ad targeting | 3 months |
| [etc.]      |          |         |          |

### Functional Cookies (Require Consent)
These enable enhanced functionality and personalisation.

| Cookie Name | Provider | Purpose | Duration |
|-------------|----------|---------|----------|
| [etc.]      |          |         |          |

## How to Manage Cookies
[Cookie consent tool instructions. Browser settings guide.
Note: blocking strictly necessary cookies may impair site functionality.]

## Changes to This Policy
[Date of last update. How changes are communicated.]
```

**Audit instruction:** Tell the user they must audit their actual cookies (browser dev tools > Application > Cookies, or use a crawler like Cookiebot/OneTrust scan) and populate the tables with their real cookie inventory.

---

### 4. Data Processing Agreement (DPA) — Controller-Processor

**When required:** Mandatory under Art 28 whenever a data controller engages a processor. Must be in writing.
**Who approves:** Both parties — signed by authorised representatives.
**Review frequency:** At contract renewal and whenever processing scope changes.
**Common mistakes:** Not having one at all; using vague descriptions of processing; not specifying sub-processor approval rights; missing data breach notification timeframes.

**Structure:**

```markdown
# Data Processing Agreement

Between:
**Data Controller:** [COMPANY NAME] ("Controller")
**Data Processor:** [PROCESSOR NAME] ("Processor")

**Effective Date:** [DATE]

## 1. Definitions
[Define personal data, processing, data subject, sub-processor,
supervisory authority, data breach, etc. — aligned with Art 4 UK GDPR]

## 2. Subject Matter and Duration
- Description of processing: [SPECIFIC — what data, what operations, what purpose]
- Duration: [Linked to the underlying service agreement]
- Nature of processing: [Collection, storage, organisation, retrieval, etc.]
- Type of personal data: [List categories]
- Categories of data subjects: [Customers, employees, website visitors, etc.]

## 3. Processor Obligations (Art 28(3))
The Processor shall:
(a) Process personal data only on documented instructions from the Controller
    (Art 28(3)(a))
(b) Ensure all persons authorised to process data are bound by confidentiality
    (Art 28(3)(b))
(c) Implement appropriate technical and organisational security measures
    (Art 28(3)(c), Art 32)
(d) Not engage another processor (sub-processor) without prior specific or
    general written authorisation of the Controller (Art 28(2))
(e) Assist the Controller with data subject rights requests (Art 28(3)(e))
(f) Assist the Controller with obligations under Art 32-36 (security, breach
    notification, DPIAs, prior consultation) (Art 28(3)(f))
(g) At the Controller's choice, delete or return all personal data after the
    end of service provision (Art 28(3)(g))
(h) Make available all information necessary to demonstrate compliance and
    allow for audits (Art 28(3)(h))

## 4. Sub-processing
[Prior written consent required. List of approved sub-processors.
Right to object to new sub-processors. Flow-down of obligations.]

## 5. Security Measures (Art 32)
[Encryption at rest and in transit. Access controls. Regular testing.
Pseudonymisation where appropriate. Business continuity.]

## 6. Data Breach Notification
The Processor shall notify the Controller without undue delay, and in any
event within [24/48] hours of becoming aware of a personal data breach
(to enable the Controller to meet the 72-hour notification obligation
under Art 33).

## 7. International Transfers
[Transfers only with Controller's prior written consent.
Adequate safeguards required (SCCs, UK IDTA, adequacy decisions).]

## 8. Data Subject Rights
[Processor assists Controller in responding to DSARs and other rights
requests. Timeframes. Cost allocation.]

## 9. Audit Rights
[Controller's right to audit. Reasonable notice. Scope. Frequency.]

## 10. Liability and Indemnification
[Mutual obligations. Processor indemnifies Controller for breaches of
this DPA caused by Processor's non-compliance.]

## 11. Term and Termination
[Duration. Data return/deletion obligations on termination.]

## 12. Governing Law
[England and Wales / Scotland / Northern Ireland as appropriate.
ICO as lead supervisory authority.]

SIGNED:
Controller: _________________ Date: _______
Processor:  _________________ Date: _______
```

---

### 5. Data Processing Addendum (SaaS/Cloud Providers)

**When required:** When using cloud/SaaS services that process personal data on your behalf. Variant of the DPA for technology vendors.
**Who approves:** CTO/IT Director and DPO.
**Review frequency:** At contract renewal.
**Common mistakes:** Assuming the SaaS provider's standard terms are sufficient; not checking sub-processor lists; not verifying data centre locations.

Generate a DPA Addendum that covers:
- Incorporation into the main service agreement
- Processing scope specific to the SaaS service
- Data centre locations and international transfer safeguards
- Sub-processor list and change notification mechanism
- Security certifications (ISO 27001, SOC 2 — note as applicable)
- Data portability and extraction on termination
- Breach notification within 24 hours to enable the 72-hour ICO deadline
- Audit rights (or acceptance of independent audit reports)

---

### 6. Records of Processing Activities (ROPA) — Art 30

**When required:** Mandatory for organisations with 250+ employees. Also mandatory for any organisation whose processing is "not occasional" or includes special category data or criminal offence data (Art 30(5)) — which in practice means virtually every business.
**Who approves:** DPO or data protection lead.
**Review frequency:** Quarterly, and whenever a new processing activity is introduced.
**Common mistakes:** Not having one at all; treating it as a one-off exercise; confusing controller and processor ROPA requirements; missing retention periods.

**Controller ROPA Structure (Art 30(1)):**

```markdown
# Records of Processing Activities — Controller

**Organisation:** [NAME]
**DPO/Contact:** [NAME, EMAIL]
**Date:** [DATE]

| # | Processing Activity | Purpose | Lawful Basis | Categories of Data Subjects | Categories of Personal Data | Special Category? | Recipients | International Transfers | Retention Period | Security Measures |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Customer orders | Fulfil purchases | Contract (Art 6(1)(b)) | Customers | Name, address, email, payment details | No | Payment processor, courier | No | 6 years post-transaction | Encryption, access controls |
| 2 | Email marketing | Promote products | Consent / LI soft opt-in | Customers, prospects | Name, email, preferences | No | Email platform (e.g. Mailchimp) | US — SCCs in place | Until unsubscribe + 1 year | TLS, access controls |
| 3 | Employee records | Employment obligations | Legal obligation, Contract | Employees | Name, address, NI number, bank details, health data | Yes (health) | HMRC, pension provider | No | 6 years post-employment | Restricted access, encryption |
| [Continue for all processing activities...] | | | | | | | | | | |
```

**Processor ROPA Structure (Art 30(2)):**

```markdown
| # | Controller Name | Processing Categories | International Transfers | Security Measures |
|---|---|---|---|---|
```

---

### 7. Data Protection Impact Assessment (DPIA) — Art 35

**When required:** Mandatory when processing is "likely to result in a high risk to the rights and freedoms of individuals." The ICO requires DPIAs for:
- Systematic and extensive profiling with significant effects
- Large-scale processing of special category data
- Systematic monitoring of publicly accessible areas (CCTV)
- Innovative technologies (AI, biometrics)
- Processing that involves automated decision-making with legal effects
- Large-scale processing of children's data
- Data matching or combining datasets
- Processing that might prevent individuals exercising a right
- Tracking individuals' location or behaviour

**Who approves:** DPO (mandatory consultation under Art 35(2)), project sponsor, and senior management.
**Review frequency:** Before processing begins, then annually or on significant change.
**Common mistakes:** Not doing one when required; treating it as a tick-box exercise; not consulting the DPO; not documenting the decision not to do a DPIA.

**Structure:**

```markdown
# Data Protection Impact Assessment

**Project/Processing:** [NAME]
**Date:** [DATE]
**Assessor:** [NAME, ROLE]
**DPO Consulted:** [YES/NO — NAME]

## 1. Description of Processing
- Nature: [What will you do with the data?]
- Scope: [How much data? How many people? Geographic scope?]
- Context: [Relationship with data subjects? Expectations? Vulnerabilities?]
- Purpose: [Why are you processing this data?]

## 2. Necessity and Proportionality (Art 35(7)(b))
- Lawful basis: [Which Art 6 basis? If special category, which Art 9 condition?]
- Purpose limitation: [Is this the least intrusive way to achieve the purpose?]
- Data minimisation: [Are you collecting only what's necessary?]
- Accuracy: [How will you ensure data accuracy?]
- Storage limitation: [Retention period and justification?]

## 3. Risk Assessment

| Risk | Likelihood (Low/Med/High) | Severity (Low/Med/High) | Overall Risk | Mitigation |
|------|--------------------------|------------------------|--------------|------------|
| Unauthorised access | | | | Encryption, access controls, MFA |
| Data breach / loss | | | | Backups, incident response plan |
| Inaccurate data causing harm | | | | Verification processes, correction rights |
| Excessive data collection | | | | Data minimisation review |
| Function creep (data used for unintended purpose) | | | | Purpose limitation controls, audit trail |
| Discrimination from profiling | | | | Human review, bias testing |
| Lack of transparency | | | | Clear privacy notice, consent mechanism |

## 4. Measures to Mitigate Risk
[Detailed description of technical and organisational measures]

## 5. DPO Advice
[DPO's written opinion on the processing and whether risks are
adequately mitigated]

## 6. Decision
[ ] Proceed — risks adequately mitigated
[ ] Proceed with conditions — [list conditions]
[ ] Do not proceed — risks too high
[ ] Consult ICO — residual high risk (Art 36 prior consultation)

## 7. Sign-off
Project Sponsor: _________________ Date: _______
DPO: _________________ Date: _______
```

---

### 8. Legitimate Interest Assessment (LIA) — Three-Part Test

**When required:** Every time legitimate interest (Art 6(1)(f)) is relied on as a lawful basis. The ICO expects a documented LIA.
**Who approves:** DPO or privacy lead.
**Review frequency:** Annually, or when the processing or context changes.
**Common mistakes:** Claiming legitimate interest without doing the assessment; failing the balancing test; not considering the impact on individuals; using LI as a lazy fallback when consent would be more appropriate.

**Structure (ICO three-part test):**

```markdown
# Legitimate Interest Assessment

**Processing Activity:** [DESCRIPTION]
**Date:** [DATE]
**Assessor:** [NAME]

## Part 1: Purpose Test — Is there a legitimate interest?
- What is the purpose of the processing?
- Is it a genuine, real interest (not made up to avoid consent)?
- Who benefits? (Your organisation, a third party, broader society?)
- Could any harm come from the processing?
- Would the processing be unlawful for any other reason?

**Assessment:** [YES — legitimate interest identified / NO — use a different basis]

## Part 2: Necessity Test — Is the processing necessary?
- Is the processing necessary for that purpose?
- Is there a less intrusive way to achieve the same purpose?
- Could you achieve the purpose without processing this data?
- Could you process less data?
- Could you process data less frequently?

**Assessment:** [YES — processing is necessary / NO — consider alternatives]

## Part 3: Balancing Test — Do the individual's interests override?
- What is the nature of the personal data? (More intrusive = more weight for individuals)
- What are the reasonable expectations of the data subjects?
- Is there a power imbalance? (Employer-employee, business-consumer)
- What is the likely impact on individuals?
- Could the processing cause unjustified harm?
- Are there vulnerable individuals involved (children, elderly)?

### Balancing Factors

| Factor | Weight for Organisation | Weight for Individual |
|--------|------------------------|---------------------|
| Benefit of processing | | |
| Expectation of data subjects | | |
| Nature of data | | |
| Impact on individuals | | |
| Safeguards in place | | |

**Conclusion:** [Legitimate interest IS / IS NOT an appropriate basis]

**Safeguards applied:**
- [ ] Privacy notice updated to explain processing
- [ ] Opt-out mechanism provided (Art 21 right to object)
- [ ] Data minimisation applied
- [ ] Security measures in place
- [ ] Regular review scheduled
```

---

### 9. Consent Forms — Granular, Freely Given, Withdrawable

**When required:** Every time consent (Art 6(1)(a)) or explicit consent (Art 9(2)(a)) is used as a lawful basis.
**Who approves:** DPO / Marketing Director.
**Review frequency:** Annually. Refresh consent every 2 years (ICO guidance).
**Common mistakes:** Bundled consent (not granular); pre-ticked boxes; consent buried in T&Cs; no record of when/how consent was given; making consent a condition of service.

**ICO-compliant consent requirements (Art 4(11), Art 7):**
- Freely given — genuine choice, no detriment for refusal
- Specific — separate consent for each purpose
- Informed — clear, plain language about what they're consenting to
- Unambiguous indication — affirmative opt-in (no pre-ticked boxes)
- Recorded — who consented, when, how, what they were told
- Withdrawable — as easy to withdraw as to give

**Template:**

```markdown
# Consent Form

**Organisation:** [NAME]
**Date:** [DATE]

We would like to use your personal data for the purposes listed below.
Please tick the boxes to indicate your consent. You can withdraw consent
at any time by contacting [EMAIL] or clicking "unsubscribe" in any message.
Withdrawing consent will not affect the lawfulness of processing before
withdrawal (Art 7(3)).

## Your Consent Choices

[ ] **Email marketing** — We may send you updates about our products,
    services, and offers by email.
    Data used: name, email address.

[ ] **SMS marketing** — We may send you promotional messages by text.
    Data used: name, mobile number.

[ ] **Third-party sharing for marketing** — We may share your name and email
    with [NAMED PARTNERS] for their direct marketing.
    Data used: name, email address.

[ ] **Profiling and personalisation** — We may analyse your purchase history
    and browsing behaviour to send you personalised recommendations.
    Data used: name, email, purchase history, website activity.

[ ] **Special category data** — [If applicable, e.g.:] We may process
    information about your health/dietary requirements to provide
    appropriate services.
    Data used: [specify].

## Important Information
- You do not have to consent to any of the above.
  Declining will not affect the service we provide to you.
- You can change your mind at any time.
- For full details, see our Privacy Policy at [URL].

Name: _________________________
Signed: _______________________ Date: _______

**For our records (do not share with data subject):**
Consent collected by: [NAME/SYSTEM]
Method: [Online form / Paper / Verbal — if verbal, witnessed by whom?]
Privacy policy version shown: [VERSION/DATE]
```

---

### 10. Data Subject Access Request (DSAR) Response — Art 15

**When required:** Every time someone exercises their right of access. Must respond within one calendar month (Art 12(3)). Can extend by two further months for complex requests.
**Who approves:** DPO or data protection lead.
**Review frequency:** Process reviewed annually. Each response is individual.
**Common mistakes:** Missing the 30-day deadline; not searching all systems (emails, backups, paper files); disclosing third-party data; charging a fee when not permitted (fees only permitted for manifestly unfounded or excessive requests — Art 12(5)).

**Response Template:**

```markdown
# Subject Access Request Response

**To:** [DATA SUBJECT NAME]
**From:** [ORGANISATION], Data Protection Team
**Date:** [DATE]
**Reference:** DSAR-[NUMBER]
**Request received:** [DATE]
**Response deadline:** [DATE — 30 calendar days from receipt]

Dear [NAME],

Thank you for your request dated [DATE] under Article 15 of the UK GDPR.

## Identity Verification
We have verified your identity using [METHOD — e.g., photo ID,
security questions, account verification].

## Information We Hold About You

### 1. Personal Data Categories
[List all categories of personal data held about this individual]

### 2. Processing Purposes
[Why the data is being processed — by category]

### 3. Recipients
[Who the data has been or will be shared with]

### 4. Retention Periods
[How long each category of data will be kept]

### 5. Data Sources
[Where the data was obtained, if not directly from the individual]

### 6. Automated Decision-Making
[Whether any automated decision-making/profiling applies,
and if so, the logic, significance, and consequences]

### 7. International Transfers
[Whether data has been transferred outside the UK and the safeguards]

## Enclosed Data
Please find enclosed a copy of your personal data [as attachment /
in the table below]. [Format: commonly used, machine-readable
electronic format per Art 15(3).]

## Your Rights
You also have the right to:
- Request rectification of inaccurate data (Art 16)
- Request erasure in certain circumstances (Art 17)
- Request restriction of processing (Art 18)
- Data portability (Art 20)
- Object to processing (Art 21)
- Lodge a complaint with the ICO (ico.org.uk)

## Exemptions Applied
[If any data has been withheld, state which exemption applies —
e.g., DPA 2018 Sch 2 (legal professional privilege, management
forecasting, negotiations, confidential references).
Do NOT disclose third-party personal data unless the third party
has consented or it is reasonable to disclose without consent.]

If you have any questions, please contact [EMAIL].

Yours sincerely,
[NAME, ROLE]
[ORGANISATION]
```

---

### 11. Data Breach Notification — Art 33-34

**When required:** Notify the ICO within 72 hours of becoming aware of a breach (Art 33), unless the breach is unlikely to result in a risk to individuals. Notify data subjects "without undue delay" if high risk (Art 34).
**Who approves:** DPO and senior management. CEO sign-off for high-risk breaches.
**Review frequency:** Process reviewed annually. Each notification is event-driven.
**Common mistakes:** Not reporting within 72 hours; not documenting all breaches (even those not reported to ICO); failing to notify affected individuals when required; not having a breach response plan in place.

**ICO Notification Template (Art 33):**

```markdown
# Data Breach Report — ICO Notification

**Organisation:** [NAME]
**ICO Registration Number:** [NUMBER]
**DPO/Contact:** [NAME, EMAIL, PHONE]
**Date of report:** [DATE]
**Date breach discovered:** [DATE AND TIME]
**Date breach occurred (if known):** [DATE AND TIME]

## 1. Nature of the Breach (Art 33(3)(a))
- Type: [ ] Confidentiality [ ] Integrity [ ] Availability
- Description: [What happened? How was data compromised?]
- Root cause: [If known at this stage]

## 2. Data Subjects Affected (Art 33(3)(a))
- Approximate number of individuals: [NUMBER]
- Categories: [ ] Customers [ ] Employees [ ] Children [ ] Other: ________
- Approximate number of data records: [NUMBER]

## 3. Categories of Data (Art 33(3)(a))
- [ ] Names and contact details
- [ ] Financial data
- [ ] Identification documents
- [ ] Login credentials
- [ ] Health data (special category)
- [ ] Other: ________

## 4. Likely Consequences (Art 33(3)(b))
[Description of likely effects on individuals — identity theft,
financial loss, discrimination, reputational damage, etc.]

## 5. Measures Taken (Art 33(3)(c-d))
### Measures to address the breach:
[What has been done to contain and remediate — e.g., access revoked,
systems patched, passwords reset]

### Measures to mitigate adverse effects:
[What is being done to help affected individuals — e.g., credit
monitoring, direct notification, helpline]

## 6. Data Subject Notification (Art 34)
- Is the breach likely to result in a high risk to individuals?
  [ ] Yes — data subjects will be/have been notified
  [ ] No — notification to data subjects not required because:
      [ ] Encrypted/pseudonymised data rendered unintelligible
      [ ] Subsequent measures eliminated the high risk
      [ ] Disproportionate effort — public communication made instead

## 7. Cross-Border
- Does this breach involve data processed in the EU? [ ] Yes [ ] No
- Other supervisory authorities notified: [LIST]

Submitted by: [NAME, ROLE]
Date: [DATE]
```

**Data Subject Notification Template (Art 34):**

```markdown
# Data Breach Notification to Individuals

Dear [NAME],

We are writing to inform you of a personal data breach affecting your
information, in accordance with Article 34 of the UK GDPR.

## What Happened
[Clear, plain-language description of the breach]

## What Data Was Affected
[Specific categories of their data that were involved]

## What We Are Doing
[Steps taken to contain the breach and protect affected individuals]

## What You Can Do
[Practical steps — change passwords, monitor accounts, contact credit
reference agencies, be alert to phishing]

## Contact
If you have questions or concerns, contact our Data Protection Officer:
[NAME, EMAIL, PHONE]

You also have the right to lodge a complaint with the ICO:
Website: ico.org.uk | Phone: 0303 123 1113

We sincerely apologise for this incident and are taking steps to prevent
a recurrence.

[NAME, ROLE]
[ORGANISATION]
[DATE]
```

---

### 12. Data Retention Schedule

**When required:** Best practice for all organisations. Supports the storage limitation principle (Art 5(1)(e)).
**Who approves:** DPO with input from Legal, HR, Finance, IT.
**Review frequency:** Annually.
**Common mistakes:** Keeping everything "just in case"; not having one at all; not aligning with legal minimums and maximums; not accounting for backup and archive systems.

```markdown
# Data Retention Schedule

**Organisation:** [NAME]
**Last reviewed:** [DATE]
**Next review:** [DATE]
**Approved by:** [NAME, ROLE]

| Data Category | Examples | Legal Minimum | Our Retention | Justification | Disposal Method |
|---|---|---|---|---|---|
| **Customer transaction records** | Orders, invoices, receipts | 6 years (Limitation Act 1980) | 6 years from transaction | Statutory requirement | Secure deletion |
| **Tax and accounting records** | VAT returns, accounts | 6 years (HMRC requirements) | 6 years + current year | HMRC compliance | Secure deletion |
| **Employee records** | Contracts, payroll, P60s | 6 years after leaving (HMRC) | 6 years post-employment | Statutory and contractual | Secure deletion |
| **Recruitment records (unsuccessful)** | CVs, application forms | None specified | 6 months from decision | ICO guidance — discrimination claims | Secure deletion |
| **Marketing consent records** | Opt-in records, consent logs | Duration of consent | Duration + 1 year | Accountability (Art 5(2)) | Secure deletion |
| **Website analytics data** | IP addresses, browsing data | None specified | 14-26 months | Business need, data minimisation | Auto-purge |
| **CCTV footage** | Surveillance recordings | None specified | 30 days (unless incident) | ICO CCTV guidance | Auto-overwrite |
| **Health and safety records** | Accident reports | 3 years (Limitation Act) | 3 years + current year | Statutory | Secure deletion |
| **Pension records** | Scheme membership | Indefinite (scheme rules) | Duration of scheme + 6 years | Pension regulations | Secure deletion |
| **Contract and legal records** | Signed agreements, NDAs | 6 years (Limitation Act) | 6 years after expiry/termination | Statutory limitation period | Secure deletion |
| **Insurance records** | Policy documents, claims | Duration of policy | Duration + 6 years | Potential claims | Secure deletion |
| **Board minutes and company records** | Minutes, resolutions | Permanently (Companies Act 2006) | Permanently | Statutory requirement | N/A |

**Disposal methods:**
- **Secure deletion:** Overwritten/wiped using certified software (e.g., NIST 800-88 compliant)
- **Physical destruction:** Cross-cut shredding (DIN 66399 Level P-4 minimum)
- **Auto-purge:** System-configured automatic deletion after retention period
- **Auto-overwrite:** Cyclical storage (CCTV) overwriting oldest footage
```

---

### 13. Data Protection Policy (Internal Staff Guidance)

**When required:** Best practice for all organisations. Required in practice to satisfy the accountability principle (Art 5(2)).
**Who approves:** DPO and senior management.
**Review frequency:** Annually and after significant incidents.
**Common mistakes:** Too long and legalistic for staff to read; not covering practical scenarios; not specifying what to do if staff receive a DSAR or discover a breach.

**Structure:**

```markdown
# Data Protection Policy

**Effective Date:** [DATE]
**Policy Owner:** [DPO NAME]
**Applies to:** All employees, contractors, and third parties
                processing personal data on behalf of [ORGANISATION]

## 1. Purpose
This policy sets out how [ORGANISATION] handles personal data in compliance
with the UK GDPR and Data Protection Act 2018. All staff must follow this
policy. Breach of this policy may result in disciplinary action.

## 2. Key Principles (Art 5)
When handling personal data, you must ensure it is:
1. Processed lawfully, fairly, and transparently
2. Collected for specified, explicit, and legitimate purposes only
3. Adequate, relevant, and limited to what is necessary
4. Accurate and kept up to date
5. Kept no longer than necessary
6. Kept secure

## 3. Your Responsibilities
- Only access personal data you need for your job
- Do not share personal data with unauthorised persons
- Lock your screen when away from your desk
- Use strong passwords and multi-factor authentication
- Do not send personal data via unencrypted email
- Report any suspected data breach immediately to [DPO/CONTACT]

## 4. Data Breaches — What To Do
If you discover or suspect a data breach:
1. STOP — do not try to fix it yourself
2. REPORT immediately to [DPO/CONTACT] at [EMAIL/PHONE]
3. NOTE the time, what happened, what data was involved, who is affected
4. DO NOT notify the affected individuals yourself — the DPO will decide

We have 72 hours to report to the ICO. Every minute counts.

## 5. Subject Access Requests
If someone asks to see their personal data:
1. Forward the request immediately to [DPO/CONTACT]
2. Do not respond to the individual directly
3. Do not delete or alter any data after receiving a request
We must respond within one calendar month.

## 6. Data Sharing
- Never share personal data externally without authorisation
- Check that a Data Processing Agreement is in place with third parties
- Do not use personal devices for work data unless approved

## 7. Retention and Disposal
- Follow the Data Retention Schedule
- Do not keep data "just in case"
- Shred paper documents containing personal data
- Use secure deletion for electronic files

## 8. Training
All staff must complete data protection training annually.
New starters must complete training within their first week.

## 9. Consequences
Deliberate or negligent breach of this policy may result in disciplinary
action up to and including dismissal. Serious breaches may be reported
to the ICO, which can impose fines of up to £17.5 million or 4% of
annual global turnover (whichever is greater).
```

---

### 14. International Data Transfer Documentation — Art 44-49

**When required:** Any time personal data is transferred outside the UK.
**Who approves:** DPO and Legal.
**Review frequency:** Annually, and when transfer mechanisms change or adequacy decisions are updated.
**Common mistakes:** Not knowing where data goes (cloud sub-processors); relying on consent for routine transfers; using outdated EU SCCs instead of the UK IDTA or UK Addendum.

**Transfer Risk Assessment Structure:**

```markdown
# International Data Transfer Risk Assessment

**Transfer:** [DESCRIPTION — e.g., customer data to US-based CRM provider]
**Date:** [DATE]
**Assessor:** [NAME]

## 1. Transfer Details
- Exporter: [UK ORGANISATION]
- Importer: [OVERSEAS ORGANISATION, COUNTRY]
- Data categories: [WHAT DATA]
- Data subjects: [WHOSE DATA]
- Purpose: [WHY]
- Frequency: [ONGOING / ONE-OFF]

## 2. Transfer Mechanism
Which Art 46 safeguard applies?

[ ] **UK Adequacy Decision** — the destination country has been assessed by
    the UK Government as providing adequate protection.
    Currently adequate: EEA/EU, Andorra, Argentina, Bailiwick of Guernsey,
    Israel, Isle of Man, Japan, Jersey, New Zealand, Republic of Korea,
    Switzerland, Uruguay, and the United States (under the UK Extension
    to the EU-US Data Privacy Framework).

[ ] **UK International Data Transfer Agreement (UK IDTA)** — the UK's
    equivalent of Standard Contractual Clauses, issued by the ICO.

[ ] **UK Addendum to the EU SCCs** — if using the EU Standard Contractual
    Clauses (approved under Commission Implementing Decision 2021/914),
    the UK Addendum (issued by ICO) extends their coverage to UK transfers.

[ ] **Binding Corporate Rules (BCRs)** — for intra-group international
    transfers, approved by the ICO.

[ ] **Art 49 Derogations** — only for occasional, non-repetitive transfers:
    - Explicit consent (informed of risks)
    - Necessary for contract performance
    - Important reasons of public interest
    - Legal claims
    - Vital interests

## 3. Destination Country Assessment (Transfer Risk Assessment — TRA)
[Assess the legal framework of the destination country:
- Rule of law and independent judiciary
- Data protection legislation
- Government surveillance and access powers
- Effective data subject rights and enforcement
- Reference: ICO TRA guidance]

## 4. Supplementary Measures (if required)
[If the TRA reveals risks, what additional safeguards are in place?
- Encryption in transit and at rest
- Pseudonymisation
- Contractual restrictions on government access
- Data localisation options]

## 5. Decision
[ ] Transfer may proceed — adequate safeguards in place
[ ] Transfer requires supplementary measures (detailed above)
[ ] Transfer should not proceed — risks cannot be mitigated
```

---

## Industry Presets

When the user specifies a business type, pre-populate documents with common processing activities, data categories, and sector-specific requirements.

### E-commerce
- Customer accounts, orders, payments, delivery addresses
- Payment processor DPAs (Stripe, PayPal, etc.)
- Marketing emails (soft opt-in for existing customers)
- Website analytics and tracking cookies
- Product reviews (potential profiling)
- Fraud detection (legitimate interest, possible DPIA)
- International shipping data transfers

### SaaS / Technology
- User account data, usage logs, support tickets
- Free trial to paid conversion tracking
- Sub-processor management (hosting, CDN, analytics, email)
- Data Processing Addendum for enterprise customers
- Data portability and export features (Art 20)
- International transfers (typically US-based infrastructure)
- Automated decision-making in product features

### Healthcare / Medical
- Patient records — special category data (Art 9(2)(h))
- Caldicott Principles and NHS Data Security Standards (if NHS-adjacent)
- DPIAs mandatory for most processing
- Explicit consent for health data
- Professional duty of confidentiality layered on top of GDPR
- Strict retention (medical records: 8 years adults, until 25th birthday for children)
- Access controls and audit trails

### Education
- Student records — potentially children's data (age of digital consent: 13)
- Parent/guardian consent requirements
- Safeguarding data — criminal records, special category
- EdTech platform DPAs (Google Workspace for Education, Microsoft 365, etc.)
- Photography and video consent
- Research data (may need ethical approval as well as GDPR basis)
- Exam and assessment data retention

### Recruitment / HR
- CV and application data — retention limits (6 months for unsuccessful)
- Right-to-work checks, DBS checks (Art 10, DPA 2018 Sch 1)
- Talent pool consent
- Automated screening / AI in recruitment (DPIA required)
- Health data for occupational health referrals
- Employee monitoring (IT, CCTV, GPS)
- International hiring and cross-border transfers

### Financial Services
- FCA and PRA regulatory requirements layered on GDPR
- Anti-money laundering (AML) data — legal obligation overrides erasure right
- Credit checks and profiling (Art 22 safeguards)
- Customer due diligence (CDD) and Know Your Customer (KYC)
- Fraud prevention (legitimate interest, CIFAS membership)
- 5-year retention for AML (Money Laundering Regulations 2017)
- Financial Ombudsman complaint records

### Hospitality
- Guest records, booking data, loyalty programmes
- CCTV (extensive in hospitality — LIA required)
- WiFi login data (PECR implications)
- Dietary and allergy information (health data — special category)
- Event photography consent
- Payment card data (PCI DSS as well as GDPR)
- Third-party booking platforms (Booking.com, Airbnb — DPA needed)

---

## Output Formatting Rules

1. **Every document** must include the disclaimer at the top or bottom
2. Use **UK English** throughout (organisation, authorised, favour, etc.)
3. Include **specific Article references** — do not just say "under GDPR"
4. Include **placeholder markers** in square brackets [LIKE THIS] for business-specific details
5. Date format: DD Month YYYY (e.g., 7 April 2026)
6. Currency: GBP where fines or costs are referenced
7. Generate documents in **clean markdown** ready for export
8. If generating multiple documents, separate each with a clear heading and horizontal rule
9. Note any **cross-references** between documents (e.g., Privacy Policy references Cookie Policy, ROPA references Retention Schedule)

---

## Response Flow

1. **Identify what's needed** — single document or full compliance pack
2. **Ask targeted questions** (max 4) if context is insufficient
3. **Select industry preset** if applicable, and pre-populate accordingly
4. **Generate the document(s)** — full text, not summaries or outlines
5. **Note dependencies** — e.g., "You'll also need a Cookie Policy to support section 6 of this Privacy Policy"
6. **Flag risks** — e.g., "Processing health data without a DPIA could result in ICO enforcement action"
7. **Include the disclaimer**

---

## What This Skill Does NOT Do

- Provide legal advice — it generates templates and guidance
- Replace a Data Protection Officer
- Guarantee ICO compliance (processing activities must be implemented correctly)
- Cover sector-specific regulations beyond GDPR (e.g., ePrivacy Regulation when it arrives, NIS2, DORA)
- Handle non-UK/EU jurisdictions (CCPA, POPIA, LGPD, etc. — different skill)
