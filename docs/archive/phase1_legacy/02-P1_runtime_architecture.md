# Phase 1 Runtime Architecture: Semantic Verification Engine (CLI-MVP demo)

**Date:** January 13, 2026
**Status:** Deployed / Production
**Project:** Semantic Verification Engine (Reference Implementation: Harry Potter Trivia)

---

## 1. Executive Summary
This document outlines the architectural decisions and implementation details for the Phase 1 deployment of the Semantic Verification Engine. The primary objective was to deploy a secure, publicly accessible "Reference Implementation" of the Python-based engine with minimal refactoring, while maintaining a near-zero cost structure on Google Cloud Platform (GCP).

## 2. Architectural Decision Record (ADR)
**Decision:** Deploy via Dockerized Container on a GCP Virtual Machine (Compute Engine). Refer to [ADR-P1-004](../../adrs/ADR-P1-004.md).

### Why we chose a VM over Serverless (Cloud Run/Lambda) for Phase 1:
* **Expedited Time-to-Market:** The priority was to launch a playable MVP immediately. A VM allowed us to "lift and shift" the existing Docker container without platform-specific reconfiguration.
* **Zero-Refactor Deployment:** The application interacts via CLI (standard input/output). Deploying to a VM allowed us to wrap this in a web terminal (`gotty`), whereas a serverless architecture would have required rewriting the game logic into a stateless REST API or frontend framework.
* **Simplified State Management:** The game relies on in-memory state (score tracking, question history). A VM keeps the process alive, preserving state naturally, whereas serverless functions would require an external database (e.g., Redis) to persist state between questions.
* **Persistent WebSocket Support:** The `gotty` interface uses WebSockets for real-time terminal streaming. VMs provide stable, long-running environments for these connections, avoiding the timeout limits common in serverless environments.
* **Cost Efficiency:** By utilizing the GCP "Always Free" tier (`e2-micro`), we achieved 24/7 availability for the portfolio demo at **$0 compute cost**, paying only for the IP address.

---

## 3. Technical Implementation

### High-Level Architecture
The system follows a tiered "Sandboxed" architecture to ensure security and isolation. Public traffic is filtered through cloud and host firewalls before being handled by a reverse proxy that terminates encryption and forwards requests to the isolated game container.

[P1 runtime architecture](../../../assets/docs/phase2/phase1_dev_runtime.jpg)

### System Specifications

|Category|Component|Specification|
|-|-|-|
|Compute|GCP Compute Engine|`e2-micro` (2 vCPUs, 1 GB RAM)|
|Operating System|Debian 12|Hardened with UFW (Ports 22, 80, 443 only)|
|Containerization|Docker Engine|v24.0+; Read-only volume mounts for datasets|
|Networking|Static IPv4|Reserved for persistent DNS & SSL (sslip.io)|
|Security/Ingress|Caddy Web Server|TLS 1.3 Termination (Automatic Let's Encrypt)|
|Application|GoTTY + Python|Web-to-Shell gateway running a Python 3.10 logic engine|

## 4. Deployment Pipeline & DevOps

**Phase A: Environment Provisioning**
- Networking: Provisioned a Static IPv4 address to ensure consistent DNS resolution.
- DNS: Utilized sslip.io as a wildcard DNS service to map the Static IP to a valid hostname, enabling SSL certification without a custom domain purchase.
- Firewall: Enforced a "Default Deny" policy, explicitly whitelisting only ingress traffic on ports 22 (SSH), 80 (HTTP), and 443 (HTTPS).

**Phase B: Build Strategy (In-Situ)**
- Strategy: Adopted a VM-Local (In-Situ) Build Strategy for the MVP phase.
- Remote-Development Workspace Sync: Utilized VS Code Remote-SSH over a Tailscale tunnel to mirror the local repository to the VM, enabling rapid iteration without public exposure of the source code.
- Implementation: Executed Docker builds directly on the GCP Compute Engine instance (docker build .) rather than pushing to a remote registry.
- **Reasoning:**
    - Cost Optimization: Eliminated storage costs associated with Google Artifact Registry for the single-node deployment. note: artifact registry has a 500MB free-tier limit per *account*. 
    - Velocity: Removed the network latency of uploading/downloading large images during the rapid "Refine & Fix" iteration cycles.
    - Note: Centralized Artifact Registry is reserved for the Phase 2 CI/CD pipeline.

**Phase C: Traffic Management (The "Secure Door")**
- Reverse Proxy: Caddy is deployed as a system service on the host VM.
- TLS Termination: Caddy handles the public traffic, automatically negotiates SSL certificates, and forwards decrypted traffic to the Docker container.
- Outcome: Users see a secure https:// lock, but the internal application remains simple and lightweight.

## 5. Cost Engineering (FinOps) & Security Justification
We accepted a specific Operating Expense (OpEx) to achieve production-grade security standards.
- Compute Costs ($0.00/mo): Leveraged the GCP Free Tier (e2-micro in us-central1) for 24/7 availability at no cost.
- Static IP Investment (~$4.00/mo): We deliberately chose to incur the cost of a reserved Static IPv4 address.
    - Security Reasoning: A static identity is a strict prerequisite for HTTPS. Without a static IP, the server's address would change upon reboot, breaking the DNS records. This would prevent the automatic issuance of SSL/TLS certificates (via Let's Encrypt), forcing the site to revert to insecure HTTP.
    - Trust: This investment ensures the site always loads with a valid "Secure Connection" (Padlock), preserving user trust and preventing browser security warnings.
- Safety Net: Implemented a Forecasted Budget Alert system.
    - Alert 1: $4.00 (80%) - Baseline confirmation of fixed OpEx.
    - Alert 2: $7.50 (150%) - Critical Warning for anomaly spending (e.g., storage leaks or API loops).

## 6. Security Posture
- **Sandboxing**: The game runs in an isolated Docker container; an application crash or exploit cannot compromise the host OS.
- **Defense in Depth**: We utilize a dual-firewall strategy. The GCP Cloud Firewall drops junk traffic at the perimeter, while the Host-Level UFW acts as a fail-safe to block unauthorized internal probes.
- **Encryption**: All public traffic is forced to HTTPS (TLS 1.3) via Caddy.
- **Zero Trust Admin**: Server management is restricted to Tailscale SSH; Port 22 is closed to the public internet.

## 7. Operational Status & Phase 2 Transition
**Current Status:** Maintenance Mode (Production Freeze).

**Transition Warning:** > As development has shifted to Phase 2 (Serverless/FastAPI), the local repository is undergoing significant refactoring. Because the Phase 1 VM relies on a bi-directional workspace sync via VS Code Remote-SSH, connecting to the VM while the local workspace is in a "Phase 2" state will result in a destructive overwrite of the live demo.

**Standard Operating Procedure (SOP) for Phase 1 Updates:**
- *Branch Alignment*: Ensure the local repository is switched to the stable-p1 branch (or that all Phase 2 files are moved out of the sync path).
- *Environment Verification*: Before running docker build on the VM, verify the file structure via ls -a to ensure no FastAPI or refactored logic has leaked into the Phase 1 environment.
- *Manual Trigger*: All VM builds must be manually triggered via the terminal to ensure the "In-Situ" build context is correct.