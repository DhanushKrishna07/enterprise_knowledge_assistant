# NimbusCloud Drive — Technical & Operations Guide

**NimbusCloud Technologies Pvt Ltd — Engineering Department**

| Field | Details |
|-------|---------|
| Document Code | ENG-TECH-027 |
| Version | v2.4 |
| Effective Date | 22-May-2026 |
| Owner | Head of Platform Engineering |

---

## 1. System Architecture

NimbusCloud Drive is built on a **microservices architecture** deployed across multiple availability zones. Client requests are routed through a global load balancer to regional API gateways, which forward requests to backend services:

- **Auth Service** — handles authentication and session management
- **Metadata Service** — manages file names, folder structure, permissions, and version pointers
- **Sync Engine** — processes file sync events from clients
- **Sharing Service** — manages share links, permissions, and collaboration
- **Notification Service** — pushes real-time updates to connected clients

File contents are stored in an **S3-compatible object storage** backend, sharded across three storage clusters per region. Metadata is stored separately in a distributed relational database (PostgreSQL with read replicas) for low-latency lookups.

---

## 2. Deployment Options

| Deployment Mode | Description | Supported Plans |
|----------------|-------------|----------------|
| **Managed Cloud (SaaS)** | Fully hosted and managed by NimbusCloud Technologies | Free, Pro, Business, Enterprise |
| **Private Cloud** | Deployed in customer's own cloud account (AWS/Azure/GCP), managed jointly | Enterprise only |
| **On-Premises** | Deployed on customer-owned infrastructure via Docker/Kubernetes | Enterprise only, by request |

On-premises and private cloud deployments use a **Helm chart** to install all microservices into a Kubernetes cluster. Minimum recommended cluster size is **6 nodes (4 vCPU / 16 GB RAM each)** for deployments supporting up to 2,000 users.

---

## 3. Backup & Disaster Recovery

- Full backups of metadata databases are taken **daily** and retained for **90 days**.
- Object storage is replicated **synchronously** across 3 availability zones within a region.
- Cross-region replication for disaster recovery runs **asynchronously** with a target lag of under 15 minutes.
- **Recovery Time Objective (RTO):** 4 hours
- **Recovery Point Objective (RPO):** 1 hour
- Disaster recovery drills are conducted **quarterly** and results are logged in the DR run-book.

---

## 4. Security Architecture

### 4.1 Encryption

All file content is encrypted at rest using **AES-256**. Data in transit between clients and NimbusCloud servers, and between internal microservices, is encrypted using **TLS 1.2 or higher**. Encryption keys are managed through a dedicated **Key Management Service (KMS)** with automatic key rotation every 12 months.

### 4.2 Authentication & Access Control

User authentication supports:
- Email/password (with bcrypt hashing)
- SSO via **SAML 2.0** (Business and Enterprise)
- OAuth-based sign-in with Google and Microsoft accounts

Multi-factor authentication (MFA) is optional on Free and Pro plans, and can be enforced organization-wide on Business and Enterprise plans by an administrator.

### 4.3 Vulnerability Management

- Automated dependency and container image scanning runs on **every build**.
- **Critical** vulnerabilities must be patched within **48 hours** of identification.
- **High-severity** vulnerabilities must be patched within **7 days**.
- Third-party penetration testing is conducted **twice a year**.

---

## 5. Monitoring & Alerting

All services emit structured logs and metrics to a centralized observability stack.

| Metric | Warning Threshold | Critical Threshold |
|--------|------------------|-------------------|
| API p99 latency | > 800 ms | > 2,000 ms |
| Sync queue backlog | > 50,000 jobs | > 200,000 jobs |
| Storage cluster disk usage | > 75% | > 90% |
| Error rate (5xx responses) | > 1% | > 5% |

---

## 6. Troubleshooting Common Issues

### 6.1 Files Not Syncing

1. Check the sync client's connection status icon in the system tray/menu bar.
2. Verify the device has internet connectivity and can reach `sync.nimbuscloud.example`.
3. Confirm the file does not exceed the plan's maximum file size limit.
4. Check available local disk space; sync pauses if disk space is below **1 GB**.
5. Restart the sync client; if the issue persists, regenerate the device's sync token from **Settings → Devices**.

### 6.2 Login Failures

Repeated login failures (**5 or more within 10 minutes**) trigger a temporary account lock of **15 minutes** as a brute-force protection measure. SSO login failures are most commonly caused by clock skew between the identity provider and NimbusCloud servers exceeding 5 minutes.

### 6.3 Performance Degradation

Large folders (more than **50,000 items**) can slow down folder listing in the web app. Customers experiencing this are advised to use the desktop client or API for bulk operations, and to consider splitting very large folders.

---

## 7. Scalability Considerations

Each microservice scales **horizontally and independently** based on CPU and queue-depth metrics, using Kubernetes Horizontal Pod Autoscalers. The Metadata Service database is sharded by organization ID once an organization exceeds **10 million stored objects**, to keep query latency consistent as customers grow.

---

## 8. Capacity Planning

Capacity planning reviews are conducted **monthly** by the Platform Engineering team, projecting storage and compute needs 6 months ahead based on historical growth trends. Storage clusters are provisioned with a minimum of **30% headroom** above projected peak usage at all times.

---

## 9. On-Call & Incident Response

Platform Engineering maintains a **24/7 on-call rotation** with primary and secondary engineers, each on a 1-week rotation. On-call engineers must acknowledge a P1/P2 page within **10 minutes**; failure to acknowledge automatically escalates to the secondary on-call engineer and then to the Engineering Manager.

Incident severity definitions align with those described in the IT Incident Escalation Process (`OPS-PROC-033`, Section 3).

---

## 10. Change Management

1. All production changes require a **pull request** reviewed and approved by at least one other engineer.
2. Changes are deployed via an automated **CI/CD pipeline** with staged rollout: internal canary → 10% of production traffic → 100%.
3. **High-risk changes** (database migrations, security-sensitive changes) require sign-off from a Staff Engineer or above.
4. All production deployments are logged in the **Change Log** with the associated pull request and rollback plan.

---

## 11. Data Export & Migration

Customers migrating away from NimbusCloud Drive can export all account data via the **Admin Console's bulk export tool**, which packages files and metadata (sharing settings, folder structure) into a downloadable archive. Enterprise customers can request migration assistance from the Professional Services team.

---

*NimbusCloud Technologies Pvt Ltd — Internal & Confidential*
*Technical_Guide.md | ENG-TECH-027 v2.4 | 22-May-2026*
