# Compliance Gap Analysis — GDPR & SOC2

**Company:** DasLab (Dasturlash Laboratoriyasi)
**Analyst:** Legal / Compliance Analyst
**Date:** 2026-05-18
**Status:** Initial baseline — no prior compliance program in place

---

## Executive Summary

DasLab has no established compliance program. This document maps required controls for **GDPR** (EU 2016/679) and **SOC2 Type II** (AICPA Trust Services Criteria) against current state. Every item below is a gap; none are partially addressed. Gaps are rated **P1 (critical)**, **P2 (high)**, or **P3 (medium)** by risk and lead time.

---

## GDPR Gaps

| # | Requirement | Gap | Priority | Owner |
|---|-------------|-----|----------|-------|
| G-01 | **Privacy Policy** — public-facing notice of data processing purposes, legal bases, retention, and data subject rights | Not drafted | P1 | Legal Analyst + COO |
| G-02 | **Terms of Service / EULA** | Not drafted | P1 | Legal Analyst + COO |
| G-03 | **Records of Processing Activities (RoPA)** — Article 30 obligation | Not created | P1 | Legal Analyst |
| G-04 | **Legal Basis Documentation** — identify lawful basis (consent, contract, legitimate interest) for each processing activity | Not documented | P1 | Legal Analyst |
| G-05 | **Data Subject Request (DSR) Process** — access, erasure, portability, objection within 30 days | No process or tooling | P1 | Support Lead + Legal Analyst |
| G-06 | **Data Breach Response Plan** — Article 33/34 72-hour DPA notification + affected subject notification | Not drafted | P1 | COO + Legal Analyst |
| G-07 | **Data Processing Agreements (DPAs)** with all sub-processors (cloud providers, SaaS vendors, analytics) | None signed | P1 | COO (vendor contracts) |
| G-08 | **Consent Management / Cookie Policy** — granular consent for non-essential cookies/tracking | Not implemented | P2 | Engineering + Legal Analyst |
| G-09 | **Data Retention & Deletion Policy** — documented schedules, automated purge where feasible | Not defined | P2 | Legal Analyst |
| G-10 | **Data Protection Impact Assessments (DPIA)** — required for high-risk processing (profiling, sensitive data) | No process | P2 | Legal Analyst |
| G-11 | **DPO Appointment** — required if large-scale processing of special categories or public authority | Not assessed; appoint or document exemption | P2 | COO |
| G-12 | **Privacy by Design / Default** — engineering standards for new features | Not established | P3 | CTO + Legal Analyst |
| G-13 | **Cross-border Transfer Mechanisms** — SCCs or adequacy decisions for data leaving EEA | Not assessed | P2 | Legal Analyst |
| G-14 | **Employee Data Privacy Notice** — internal notice for HR data | Not drafted | P3 | COO |

---

## SOC2 Type II Gaps

SOC2 maps to five Trust Service Criteria (TSC). Security (CC series) is mandatory; others apply based on commitments made to customers.

### CC1 — Control Environment

| # | Requirement | Gap | Priority |
|---|-------------|-----|----------|
| S-01 | **Information Security Policy** — top-level policy signed by leadership | Not drafted | P1 |
| S-02 | **Code of Conduct / Acceptable Use Policy** | Not drafted | P1 |
| S-03 | **Organizational chart and roles defined in policy** | No formal org chart in policy | P2 |
| S-04 | **Background check process** for employees and contractors | Not established | P2 |

### CC2 — Communication & Information

| # | Requirement | Gap | Priority |
|---|-------------|-----|----------|
| S-05 | **Security awareness training** — annual minimum, tracked completion | Not established | P1 |
| S-06 | **Internal communication of security policies** | No distribution mechanism | P2 |

### CC3 — Risk Assessment

| # | Requirement | Gap | Priority |
|---|-------------|-----|----------|
| S-07 | **Formal Risk Assessment** — identify, score, and treat risks annually | Not performed | P1 |
| S-08 | **Vendor / Third-party Risk Management Program** | Not established | P2 |
| S-09 | **Threat Modeling** for product features | No process | P3 |

### CC4 — Monitoring Controls

| # | Requirement | Gap | Priority |
|---|-------------|-----|----------|
| S-10 | **Continuous monitoring / SIEM** — log aggregation, alerting | Not deployed | P1 |
| S-11 | **Vulnerability Management** — scans, CVE triage, SLA for patching | No program | P1 |
| S-12 | **Penetration Testing** — annual third-party pen test | Not scheduled | P2 |
| S-13 | **Audit Logging** — who accessed what, when, and from where | Not systematically collected | P2 |

### CC5 — Control Activities

| # | Requirement | Gap | Priority |
|---|-------------|-----|----------|
| S-14 | **Access Control Policy** — least privilege, role-based access, review cadence | Not documented | P1 |
| S-15 | **Identity and Access Management (IAM)** — MFA enforced, SSO where possible | Not enforced | P1 |
| S-16 | **Offboarding / Access Revocation** — immediate revocation on termination | No formal process | P1 |
| S-17 | **Change Management Process** — tested, approved, rollback-capable deploys | Not documented | P2 |
| S-18 | **Encryption at Rest and in Transit** — documented standard (TLS 1.2+, AES-256) | Not documented; status unknown | P1 |
| S-19 | **Secret / Key Management** — no hardcoded credentials, rotation schedule | Not established | P1 |

### CC6 — Logical Access & Boundaries

| # | Requirement | Gap | Priority |
|---|-------------|-----|----------|
| S-20 | **Network Segmentation** — prod/dev/staging isolation | Not documented | P2 |
| S-21 | **Endpoint Protection** — MDM, AV, disk encryption on company devices | Not established | P2 |

### CC7 — System Operations

| # | Requirement | Gap | Priority |
|---|-------------|-----|----------|
| S-22 | **Incident Response Plan (IRP)** — detection, escalation, containment, recovery | Not drafted | P1 |
| S-23 | **Business Continuity / Disaster Recovery (BC/DR)** — RTO/RPO targets, tested | Not drafted | P2 |
| S-24 | **Backup & Recovery** — automated backups, restore tested quarterly | Not established | P2 |

### CC8 — Change Management

| # | Requirement | Gap | Priority |
|---|-------------|-----|----------|
| S-25 | **SDLC Security Gates** — SAST, dependency scanning, code review in CI/CD | Not integrated | P2 |
| S-26 | **Staging / QA environment** parity with production | Not enforced | P3 |

### CC9 — Risk Mitigation

| # | Requirement | Gap | Priority |
|---|-------------|-----|----------|
| S-27 | **Cyber Liability Insurance** | Not assessed | P3 |
| S-28 | **Supply Chain Risk** — OSS dependency review, SBOM | No process | P2 |

### Availability (A Series) — if SLA commitments are made

| # | Requirement | Gap | Priority |
|---|-------------|-----|----------|
| A-01 | **Uptime SLA** — defined, monitored, and reported | Not defined | P2 |
| A-02 | **Status Page** — public incident communication | Not deployed | P3 |

### Confidentiality (C Series)

| # | Requirement | Gap | Priority |
|---|-------------|-----|----------|
| C-01 | **Data Classification Policy** — public / internal / confidential / restricted | Not defined | P2 |
| C-02 | **NDA / Confidentiality agreements** for employees and vendors | Not in place | P1 |

---

## Prioritized Remediation Roadmap

### Phase 1 — Days 0–30 (P1 Critical)
Must complete before any customer data is processed or external commitments are made.

1. Draft and publish **Privacy Policy** and **Terms of Service** (G-01, G-02)
2. Create **Records of Processing Activities** (G-03)
3. Document **lawful bases** for each processing activity (G-04)
4. Draft **Data Breach Response Plan** (G-06)
5. Sign **DPAs** with all active sub-processors (G-07)
6. Publish **Information Security Policy** and **Code of Conduct** (S-01, S-02)
7. Implement **MFA** across all production systems; enforce least-privilege (S-15, S-16)
8. Draft **Access Control Policy** (S-14)
9. Draft **Incident Response Plan** (S-22)
10. Audit encryption at rest and in transit; document (S-18)
11. Establish **secret/key management** practice (S-19)
12. Sign **NDAs** with employees and contractors (C-02)
13. Launch **security awareness training** (S-05)
14. Perform initial **Risk Assessment** (S-07)

### Phase 2 — Days 31–90 (P2 High)
Required for SOC2 readiness and GDPR completeness.

- DSR process + tooling (G-05)
- Cookie/consent management (G-08)
- Data retention policy (G-09)
- Vendor risk management (S-08)
- Vulnerability scanning program (S-11)
- Audit logging (S-13)
- Change management process (S-17)
- BC/DR plan with tested RTO/RPO (S-23)
- Backup automation + restore test (S-24)
- Data classification policy (C-01)
- Uptime SLA definition and monitoring (A-01)
- Cross-border transfer mechanism assessment (G-13)
- DPO appointment or exemption memo (G-11)
- Background check process (S-04)
- Schedule annual pen test (S-12)

### Phase 3 — Days 91–180 (P3 Medium)
Maturity and audit-readiness.

- Privacy by Design engineering standards (G-12)
- Employee data privacy notice (G-14)
- SDLC security gates in CI/CD (S-25)
- SBOM and supply chain review (S-28)
- Threat modeling process (S-09)
- Status page (A-02)
- Cyber liability insurance (S-27)

---

## Next Steps

1. **COO review** — confirm scope and customer-facing commitments (determines which SOC2 criteria are in scope).
2. **Create tracking issues** in DAS for each Phase 1 item.
3. **Assign DPA collection** to COO (vendor authority per charter).
4. **Schedule quarterly review** of this document — cadence matches CLAUDE.md success metrics.

---

*This document is a living artifact. Update after each quarterly review or when a new processing activity is introduced.*
