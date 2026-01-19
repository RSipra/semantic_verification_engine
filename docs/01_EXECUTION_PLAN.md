2. **Architectural Schemes & ADRs**
   *Detailed diagrams and decision records for each major product release.*

   * **Phase 1: The MVP** (Legacy)
     *Status: Completed*
     *Focus: Rules-based logic, monolithic script, standalone container.*
     [Scheme](#phase-1-scheme) | [ADRs](#phase-1-adrs)

   * **Phase 2: Platform + Intelligence** (Current)
     *Status: In Progress*
     *Focus: Delivering the Semantic Engine (SBERT) and the Data Platform to support it.*
     * **Sprint 1 (Tracer Bullet):** End-to-end infrastructure test. Deploys the container with "Dumb" (Exact Match) logic to validate the build/deploy loop.
     * **Sprint 2 (Release v0.1 - Soft Launch):** The "Smart" Release.
         * *Data:* Manual generation of "Rich Features" (Thematic clusters, hard negatives) via Notebook.
         * *Model:* Fine-tuning SBERT on the rich dataset for domain-specific accuracy.
         * *Runtime:* Deploying the fine-tuned model for the hybrid answer checker.
     * **Sprint 3 (Release v0.1.1 - Hardening):** Retrofitting the automation (Prefect, DVC) to replace the manual data notebooks.
     [Scheme](#phase-2-scheme) | [ADRs](#phase-2-adrs)

   * **Phase 3: Autonomous Game Master** (Future)
     *Status: Planned*
     *Focus: Dynamic question generation and adaptive difficulty using SLMs.*
     [Scheme](#phase-3-scheme) | [ADRs](#phase-3-adrs)