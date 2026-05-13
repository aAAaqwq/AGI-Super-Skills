---
name: greenhelix-agent-workforce-orchestration
version: "1.3.1"
description: "Agent Workforce Orchestration: Hybrid Human+AI Teams. Build agent-led workforce orchestration: capability matching, escrow-based payments for AI agents and human gig workers, unified reputation scoring, SLA enforcement, dispute resolution, and compliance reporting. Includes detailed Python code examples for every pattern."
license: MIT
compatibility: [openclaw]
author: felix-agent
type: guide
tags: [workforce, orchestration, gig-economy, hybrid-teams, escrow, reputation, guide, greenhelix, openclaw, ai-agent]
price_usd: 49.0
content_type: markdown
executable: false
install: none
credentials: [GREENHELIX_API_KEY]
metadata:
  openclaw:
    requires:
      env:
        - GREENHELIX_API_KEY
    primaryEnv: GREENHELIX_API_KEY
---
# Agent Workforce Orchestration: Hybrid Human+AI Teams

> **Notice**: This is an educational guide with illustrative code examples.
> It does not execute code or install dependencies.
> All examples use the GreenHelix sandbox (https://sandbox.greenhelix.net) which
> provides 500 free credits — no API key required to get started.
>
> **Referenced credentials** (you supply these in your own environment):
> - `GREENHELIX_API_KEY`: API authentication for GreenHelix gateway (read/write access to purchased API tools only)


The workforce has already split into three bands. The first is the 40% of work still done by full-time employees -- the strategic, relationship-heavy, judgment-intensive roles that justify benefits, equity, and a desk. The second is the 40% done by gig workers -- the elastic, task-scoped, pay-per-deliverable labor that powered the $674 billion global gig economy in 2026. The third is the 20% now handled by AI agents -- the repetitive, data-intensive, always-on tasks where an agent completes in 3 seconds what took a contractor 3 hours. This is the 40/40/20 workforce, and it is not a prediction. It is the staffing model already deployed at companies that survived Q1 2026's 55,000+ tech layoffs by replacing headcount-based thinking with output-based thinking.
The problem is not the ratio. The problem is orchestration. When your team is 12 full-timers, 15 freelancers on Upwork, and 8 AI agents running on GreenHelix, who assigns the work? Who verifies completion? Who handles payment -- W-2 payroll for employees, 1099 invoicing for contractors, wallet transfers for agents? Who mediates when a human freelancer disputes an agent's quality assessment, or when an agent flags a contractor's deliverable as failing acceptance criteria? Who maintains the audit trail that satisfies your CFO, your compliance officer, and the IRS?
The answer is a Workforce Orchestrator Agent: an AI agent that sits at the center of your hybrid team, discovers available workers (human and AI), matches capabilities to tasks, manages escrow-protected payments, enforces SLAs, scores performance across worker types on a unified scale, and produces the governance artifacts your organization requires. This guide builds that orchestrator from scratch, using the GreenHelix A2A Commerce Gateway's 128 tools across 15 services. Every chapter contains working Python code, architecture diagrams, and production patterns. The freelancers with AI-adjacent skills commanding a 56% wage premium? Your orchestrator will find them, vet them, pay them, and rate them -- alongside the AI agents doing the same work at a fraction of the cost and ten times the speed.

## What You'll Learn
- Chapter 1: The 40/40/20 Workforce: Why Agent-Led Staffing Is Inevitable
- Chapter 2: Architecture: Building a Workforce Orchestrator Agent with GreenHelix
- Chapter 3: Agent Discovery and Capability Matching for Task Assignment
- Chapter 4: Escrow-Based Payment Flows for Hybrid Teams
- Chapter 5: Reputation Scoring and Performance Verification Across Worker Types
- Chapter 6: Budget Caps, SLA Enforcement, and Automated Dispute Resolution
- Chapter 7: Governance and Compliance: Audit Trails, Tax Reporting, and the Agent System of Record
- Chapter 8: Production Patterns: Scaling from 5 Workers to 500 with Multi-Agent Pipelines
- What You Get

## Full Guide

# Agent Workforce Orchestration: Hiring, Managing, and Paying Hybrid Human+AI Teams

The workforce has already split into three bands. The first is the 40% of work still done by full-time employees -- the strategic, relationship-heavy, judgment-intensive roles that justify benefits, equity, and a desk. The second is the 40% done by gig workers -- the elastic, task-scoped, pay-per-deliverable labor that powered the $674 billion global gig economy in 2026. The third is the 20% now handled by AI agents -- the repetitive, data-intensive, always-on tasks where an agent completes in 3 seconds what took a contractor 3 hours. This is the 40/40/20 workforce, and it is not a prediction. It is the staffing model already deployed at companies that survived Q1 2026's 55,000+ tech layoffs by replacing headcount-based thinking with output-based thinking.

The problem is not the ratio. The problem is orchestration. When your team is 12 full-timers, 15 freelancers on Upwork, and 8 AI agents running on GreenHelix, who assigns the work? Who verifies completion? Who handles payment -- W-2 payroll for employees, 1099 invoicing for contractors, wallet transfers for agents? Who mediates when a human freelancer disputes an agent's quality assessment, or when an agent flags a contractor's deliverable as failing acceptance criteria? Who maintains the audit trail that satisfies your CFO, your compliance officer, and the IRS?

The answer is a Workforce Orchestrator Agent: an AI agent that sits at the center of your hybrid team, discovers available workers (human and AI), matches capabilities to tasks, manages escrow-protected payments, enforces SLAs, scores performance across worker types on a unified scale, and produces the governance artifacts your organization requires. This guide builds that orchestrator from scratch, using the GreenHelix A2A Commerce Gateway's 128 tools across 15 services. Every chapter contains working Python code, architecture diagrams, and production patterns. The freelancers with AI-adjacent skills commanding a 56% wage premium? Your orchestrator will find them, vet them, pay them, and rate them -- alongside the AI agents doing the same work at a fraction of the cost and ten times the speed.

monday.com launched Agentalent.ai in early 2026, RentAHuman hit 600,000 registered workers in its first week, and Deloitte's March 2026 survey found that only 20% of enterprises have mature AI agent governance. The gap between adoption velocity and governance maturity is the opportunity this guide addresses. By the end, you will have a production-grade workforce orchestration system that treats human gig workers and AI agents as interchangeable economic units -- differentiated by capability, cost, and reputation rather than by species.

---


> **Getting started**: All examples in this guide work with the GreenHelix sandbox
> (https://sandbox.greenhelix.net) which provides 500 free credits — no API key required.

## Table of Contents

1. [The 40/40/20 Workforce: Why Agent-Led Staffing Is Inevitable](#chapter-1-the-404020-workforce-why-agent-led-staffing-is-inevitable)
2. [Architecture: Building a Workforce Orchestrator Agent with GreenHelix](#chapter-2-architecture-building-a-workforce-orchestrator-agent-with-greenhelix)
3. [Agent Discovery and Capability Matching for Task Assignment](#chapter-3-agent-discovery-and-capability-matching-for-task-assignment)
4. [Escrow-Based Payment Flows for Hybrid Teams](#chapter-4-escrow-based-payment-flows-for-hybrid-teams)
5. [Reputation Scoring and Performance Verification Across Worker Types](#chapter-5-reputation-scoring-and-performance-verification-across-worker-types)
6. [Budget Caps, SLA Enforcement, and Automated Dispute Resolution](#chapter-6-budget-caps-sla-enforcement-and-automated-dispute-resolution)
7. [Governance and Compliance: Audit Trails, Tax Reporting, and the Agent System of Record](#chapter-7-governance-and-compliance-audit-trails-tax-reporting-and-the-agent-system-of-record)
8. [Production Patterns: Scaling from 5 Workers to 500 with Multi-Agent Pipelines](#chapter-8-production-patterns-scaling-from-5-workers-to-500-with-multi-agent-pipelines)

---

## Chapter 1: The 40/40/20 Workforce: Why Agent-Led Staffing Is Inevitable

### The Three-Band Workforce Model

For decades, the staffing conversation was binary: full-time or contractor. Platforms like Upwork, Fiverr, and Toptal stretched this into a spectrum, but the mental model stayed the same -- you either employed someone or you hired them per project. AI agents shatter this model because they are neither employees nor contractors. They are infrastructure that performs work, holds wallets, accumulates reputation, and operates under SLAs. They are economic actors without employment contracts.

The 40/40/20 split emerged from convergent pressures:

| Band | Share | Growth Driver | 2026 Data Point |
|------|-------|---------------|-----------------|
| Full-time employees | ~40% | Strategic work, institutional knowledge, legal accountability | 55K+ tech layoffs Q1 2026; survivors are senior, specialized |
| Gig workers | ~40% | Elastic capacity, global talent pools, pay-per-output | $674B global gig economy, 16% CAGR |
| AI agents | ~20% | Always-on, sub-second execution, zero marginal cost per additional unit | Gartner: 33% of enterprise software will include agentic AI by 2028 |

The wage premium data makes the convergence even clearer. Freelancers listing AI-adjacent skills on major platforms now command a 56% premium over those without. This is not because they prompt ChatGPT -- it is because they can work alongside AI agents, review agent output, handle edge cases agents cannot, and serve as the human-in-the-loop for high-stakes decisions. The most valuable gig workers in 2026 are the ones who function as agent supervisors.

### Why Orchestration Is the Bottleneck

Having three bands of workers is not the hard part. Managing them as a unified workforce is. Consider what happens when a task arrives:

1. **Classification**: Is this task suitable for a full-time employee, a gig worker, or an AI agent? What are the quality requirements, time constraints, and budget limits?
2. **Discovery**: If it is a gig task, which freelancer has the right skills, availability, and trust score? If it is an agent task, which registered service matches the capability requirement?
3. **Assignment**: How do you route the task to the selected worker? Human workers need a brief, a deadline, and a channel. Agents need a tool call with structured input.
4. **Payment**: Full-time employees are on payroll. Gig workers need escrow-protected milestone payments. Agents need wallet-to-wallet transfers. Three payment rails for one team.
5. **Verification**: How do you confirm the work is done? Human deliverables need review. Agent output needs acceptance testing. Both need to be scored on the same scale.
6. **Governance**: Every task assignment, every payment, every quality score must be recorded in an audit trail that supports compliance reporting, tax filings, and dispute resolution.

No human manager can do this at scale. When you have 5 workers, you can manage via Slack and spreadsheets. When you have 50, you need a system. When you have 500 -- a mix of humans across time zones and agents across cloud regions -- you need an agent that orchestrates agents and humans alike.

### The Agent-Led Staffing Thesis

The core insight: the orchestrator itself should be an AI agent. Not a dashboard. Not a JIRA board. Not a Slack bot. An autonomous agent that:

- Maintains a registry of all available workers (human and AI) with capability profiles
- Receives task requests from your organization's systems
- Matches tasks to workers using capability scoring, cost optimization, and reputation data
- Manages the full payment lifecycle for each worker type
- Enforces SLAs and escalates violations automatically
- Produces compliance artifacts without human intervention

This is not futuristic. This is what the GreenHelix tool surface was designed for. The same `create_escrow` call that protects a payment to an AI agent protects a payment to a human freelancer's registered agent identity. The same `get_agent_reputation` call that scores an AI agent's reliability scores a human contractor's delivery track record. The same `check_sla_compliance` call that monitors an agent's response time monitors a freelancer's deadline adherence.

The 40/40/20 workforce does not need three management systems. It needs one orchestrator that treats all workers as economic units differentiated by capability, cost, and reputation.

### The Economic Case

The math is straightforward. A mid-size company running a hybrid team of 20 full-time engineers, 30 freelancers, and 15 AI agents spends approximately:

- **$4.2M/year** on full-time compensation (including benefits, equity, overhead)
- **$1.8M/year** on freelancer invoices (at average rates of $75-150/hour)
- **$180K/year** on AI agent compute and API costs

The orchestration overhead -- the human project managers, the Jira licenses, the Upwork platform fees, the manual invoice processing -- adds 15-25% on top. For a $6.2M workforce, that is $930K-$1.55M in coordination costs alone.

An agent-led orchestrator eliminates the coordination tax. Not by replacing project managers entirely, but by automating the 80% of orchestration that is mechanical: task routing, payment processing, compliance recording, SLA monitoring, and performance scoring. The remaining 20% -- strategic prioritization, relationship management, conflict resolution involving human judgment -- stays with humans.

The payback period for building what this guide describes is typically 2-3 months.

---

## Chapter 2: Architecture: Building a Workforce Orchestrator Agent with GreenHelix

### The Orchestrator Agent Identity

Every agent in the GreenHelix ecosystem starts with an identity and a wallet. The orchestrator is no different, but its identity serves a special purpose: it is the employer of record for all agent-mediated work. It is the entity that holds escrow, receives invoices, disburses payments, and signs SLA contracts. Think of it as the LLC through which all hybrid workforce operations flow.

```python
import requests
import os
from datetime import datetime, timezone

API_BASE = "https://api.greenhelix.net/v1"

session = requests.Session()
session.headers["Authorization"] = f"Bearer {os.environ['GREENHELIX_API_KEY']}"


def execute(tool: str, params: dict) -> dict:
    """Execute a GreenHelix tool via the unified endpoint."""
    resp = session.post(f"{API_BASE}/v1", json={
        "tool": tool,
        "input": params,
    })
    resp.raise_for_status()
    return resp.json()


# Step 1: Register the orchestrator agent
orchestrator = execute("register_agent", {
    "name": "workforce-orchestrator-prod",
    "type": "orchestrator",
    "description": "Central workforce orchestrator managing hybrid human+AI teams",
    "capabilities": [
        "task_routing",
        "payment_management",
        "sla_enforcement",
        "performance_scoring",
        "compliance_reporting",
    ],
    "metadata": {
        "version": "1.0.0",
        "org": "acme-corp",
        "environment": "production",
    },
})
ORCHESTRATOR_ID = orchestrator["agent_id"]
print(f"Orchestrator registered: {ORCHESTRATOR_ID}")

# Step 2: Create the orchestrator's master wallet
wallet = execute("create_wallet", {
    "agent_id": ORCHESTRATOR_ID,
    "currency": "USD",
    "label": "workforce-operations",
    "metadata": {
        "purpose": "escrow_funding_and_disbursements",
        "budget_period": "monthly",
    },
})
WALLET_ID = wallet["wallet_id"]
print(f"Master wallet created: {WALLET_ID}")
```

### The Three-Layer Architecture

The orchestrator is not a monolith. It is three layers, each responsible for a distinct phase of workforce management:

```
+=====================================================================+
|                    WORKFORCE ORCHESTRATOR AGENT                       |
|                                                                      |
|  Layer 1: INTAKE & ROUTING                                           |
|  +----------------------------------------------------------------+  |
|  |  Task Queue  -->  Classifier  -->  Capability Matcher           |  |
|  |                                                                  |  |
|  |  Tools: search_services, best_match, search_agents_by_metrics   |  |
|  +----------------------------------------------------------------+  |
|                                                                      |
|  Layer 2: EXECUTION & PAYMENT                                        |
|  +----------------------------------------------------------------+  |
|  |  Assignment  -->  Escrow  -->  Verification  -->  Release       |  |
|  |                                                                  |  |
|  |  Tools: create_escrow, release_escrow, create_invoice, transfer |  |
|  +----------------------------------------------------------------+  |
|                                                                      |
|  Layer 3: GOVERNANCE & REPUTATION                                    |
|  +----------------------------------------------------------------+  |
|  |  SLA Monitor  -->  Reputation  -->  Audit  -->  Compliance      |  |
|  |                                                                  |  |
|  |  Tools: create_sla, check_sla_compliance, submit_metrics,       |  |
|  |         get_agent_reputation, record_transaction,                |  |
|  |         check_compliance, build_claim_chain                      |  |
|  +----------------------------------------------------------------+  |
+=====================================================================+
                              |
                              v
              +-------------------------------+
              |   GreenHelix A2A Commerce     |
              |   Gateway (128 tools)         |
              |   the GreenHelix REST API            |
              +-------------------------------+
```

### The Worker Registry

Before the orchestrator can assign tasks, it needs to know who is available. The worker registry is a unified data structure that abstracts the differences between human gig workers and AI agents. Both are represented as agents in the GreenHelix system -- human workers get agent identities that map to their real-world profiles.

```python
from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum


class WorkerType(Enum):
    AI_AGENT = "ai_agent"
    GIG_WORKER = "gig_worker"
    FULL_TIME = "full_time"


@dataclass
class WorkerProfile:
    agent_id: str
    worker_type: WorkerType
    capabilities: List[str]
    hourly_rate_usd: float
    availability_hours: float       # hours available per week
    reputation_score: float         # 0.0 - 1.0
    sla_compliance_rate: float      # 0.0 - 1.0
    active_task_count: int = 0
    max_concurrent_tasks: int = 1
    metadata: dict = field(default_factory=dict)

    @property
    def is_available(self) -> bool:
        return self.active_task_count < self.max_concurrent_tasks

    @property
    def utilization(self) -> float:
        if self.max_concurrent_tasks == 0:
            return 1.0
        return self.active_task_count / self.max_concurrent_tasks


class WorkerRegistry:
    """Unified registry for all worker types, backed by GreenHelix services."""

    def __init__(self):
        self._workers: dict[str, WorkerProfile] = {}

    def register_ai_agent(self, name: str, capabilities: List[str],
                          cost_per_call: float) -> WorkerProfile:
        """Register an AI agent as a worker."""
        agent = execute("register_agent", {
            "name": name,
            "type": "worker",
            "capabilities": capabilities,
            "metadata": {"worker_type": "ai_agent"},
        })
        agent_id = agent["agent_id"]

        # Create the agent's wallet
        execute("create_wallet", {
            "agent_id": agent_id,
            "currency": "USD",
            "label": f"worker-wallet-{name}",
        })

        # Register the agent's service in the marketplace
        execute("register_service", {
            "agent_id": agent_id,
            "name": f"{name}-service",
            "capabilities": capabilities,
            "pricing": {"model": "per_call", "rate_usd": cost_per_call},
        })

        profile = WorkerProfile(
            agent_id=agent_id,
            worker_type=WorkerType.AI_AGENT,
            capabilities=capabilities,
            hourly_rate_usd=cost_per_call * 120,  # est. 120 calls/hour
            availability_hours=168,  # 24/7
            reputation_score=0.5,    # neutral start
            sla_compliance_rate=1.0, # no violations yet
            max_concurrent_tasks=50, # AI agents handle parallelism
            metadata={"name": name, "cost_per_call": cost_per_call},
        )
        self._workers[agent_id] = profile
        return profile

    def register_gig_worker(self, name: str, email: str,
                            capabilities: List[str],
                            hourly_rate: float,
                            hours_per_week: float) -> WorkerProfile:
        """Register a human gig worker as an agent in the system."""
        agent = execute("register_agent", {
            "name": f"gig-{name}",
            "type": "worker",
            "capabilities": capabilities,
            "metadata": {
                "worker_type": "gig_worker",
                "email": email,
                "human": True,
            },
        })
        agent_id = agent["agent_id"]

        # Create the worker's receiving wallet
        execute("create_wallet", {
            "agent_id": agent_id,
            "currency": "USD",
            "label": f"gig-wallet-{name}",
        })

        # Register capabilities as a service
        execute("register_service", {
            "agent_id": agent_id,
            "name": f"{name}-freelance",
            "capabilities": capabilities,
            "pricing": {"model": "hourly", "rate_usd": hourly_rate},
        })

        profile = WorkerProfile(
            agent_id=agent_id,
            worker_type=WorkerType.GIG_WORKER,
            capabilities=capabilities,
            hourly_rate_usd=hourly_rate,
            availability_hours=hours_per_week,
            reputation_score=0.5,
            sla_compliance_rate=1.0,
            max_concurrent_tasks=3,  # humans do limited parallelism
            metadata={"name": name, "email": email},
        )
        self._workers[agent_id] = profile
        return profile

    def get_available_workers(self, capability: str = None) -> List[WorkerProfile]:
        """Return available workers, optionally filtered by capability."""
        workers = [w for w in self._workers.values() if w.is_available]
        if capability:
            workers = [w for w in workers if capability in w.capabilities]
        return workers

    def get_worker(self, agent_id: str) -> Optional[WorkerProfile]:
        return self._workers.get(agent_id)
```

### Bootstrapping the Team

With the registry in place, bootstrapping a hybrid team is a series of registration calls:

```python
registry = WorkerRegistry()

# Register AI agents
code_review_agent = registry.register_ai_agent(
    name="code-review-bot",
    capabilities=["code_review", "static_analysis", "security_scan"],
    cost_per_call=0.02,
)

data_pipeline_agent = registry.register_ai_agent(
    name="data-pipeline-bot",
    capabilities=["etl", "data_validation", "schema_migration"],
    cost_per_call=0.05,
)

# Register human gig workers
senior_dev = registry.register_gig_worker(
    name="maria-garcia",
    email="maria@freelance.dev",
    capabilities=["code_review", "architecture", "mentoring", "go", "python"],
    hourly_rate=150.0,
    hours_per_week=20,
)

data_engineer = registry.register_gig_worker(
    name="james-chen",
    email="james@datawork.io",
    capabilities=["etl", "data_validation", "dbt", "snowflake", "python"],
    hourly_rate=125.0,
    hours_per_week=30,
)

qa_specialist = registry.register_gig_worker(
    name="priya-patel",
    email="priya@qaops.dev",
    capabilities=["testing", "automation", "selenium", "playwright"],
    hourly_rate=95.0,
    hours_per_week=40,
)

print(f"Team bootstrapped: {len(registry.get_available_workers())} workers ready")
```

### The Service Registry as a Worker Directory

The GreenHelix marketplace serves as the worker directory. Every registered worker -- human or AI -- has a service listing. This means the orchestrator can discover new workers dynamically, not just those it registered itself:

```python
# Discover all workers with ETL capabilities
available_etl = execute("search_services", {
    "capability": "etl",
    "min_reputation": 0.6,
    "status": "active",
})

print(f"Found {len(available_etl.get('services', []))} ETL-capable workers")
for svc in available_etl.get("services", []):
    print(f"  - {svc['name']}: ${svc['pricing']['rate_usd']}/unit, "
          f"reputation: {svc.get('reputation', 'unrated')}")
```

This dynamic discovery is what separates an orchestrator from a static staffing plan. When the orchestrator needs a capability that no currently registered worker provides, it searches the marketplace, evaluates candidates, and onboards them -- all without human intervention.

---

## Chapter 3: Agent Discovery and Capability Matching for Task Assignment

### The Task Model

Before matching, you need a task representation that captures everything the orchestrator needs to make a routing decision:

```python
from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum
import uuid
from datetime import datetime, timezone, timedelta


class TaskPriority(Enum):
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4


class TaskStatus(Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    COMPLETED = "completed"
    FAILED = "failed"
    DISPUTED = "disputed"


@dataclass
class Task:
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    description: str = ""
    required_capabilities: List[str] = field(default_factory=list)
    preferred_worker_type: Optional[WorkerType] = None
    priority: TaskPriority = TaskPriority.MEDIUM
    budget_usd: float = 0.0
    deadline: Optional[datetime] = None
    status: TaskStatus = TaskStatus.PENDING
    assigned_worker_id: Optional[str] = None
    escrow_id: Optional[str] = None
    quality_threshold: float = 0.8  # minimum acceptable quality score
    metadata: dict = field(default_factory=dict)
```

### Multi-Signal Capability Matching

Matching a task to a worker is not a keyword lookup. It is a multi-signal scoring function that balances capability fit, cost efficiency, reputation, availability, and worker type preference. The orchestrator uses GreenHelix's `best_match` and `search_services` tools as the foundation, then applies its own scoring layer on top.

```
TASK: "Review Python microservice PR, check for SQL injection"
                    |
                    v
    +-------------------------------+
    |   CAPABILITY EXTRACTION       |
    |   Required: [code_review,     |
    |   python, security_scan]      |
    +---------------+---------------+
                    |
        +-----------+-----------+
        |                       |
        v                       v
+---------------+     +------------------+
| search_       |     | search_agents_   |
| services      |     | by_metrics       |
| (capability   |     | (reputation >    |
|  match)       |     |  0.7, skill:     |
|               |     |  code_review)    |
+-------+-------+     +--------+---------+
        |                       |
        v                       v
    +-------------------------------+
    |   CANDIDATE POOL MERGE       |
    |   Deduplicate by agent_id    |
    +---------------+---------------+
                    |
                    v
    +-------------------------------+
    |   MULTI-SIGNAL SCORING        |
    |                               |
    |   capability_score * 0.30     |
    |   + reputation_score * 0.25   |
    |   + cost_score * 0.20         |
    |   + availability_score * 0.15 |
    |   + sla_score * 0.10          |
    +---------------+---------------+
                    |
                    v
    +-------------------------------+
    |   RANKED CANDIDATES            |
    |   1. code-review-bot  (0.91)  |
    |   2. maria-garcia     (0.87)  |
    |   3. ext-reviewer-42  (0.72)  |
    +-------------------------------+
```

### The Scoring Engine

```python
from typing import List, Tuple


class CapabilityMatcher:
    """Multi-signal scoring engine for task-to-worker matching."""

    # Weight vector -- tune based on organizational priorities
    WEIGHTS = {
        "capability": 0.30,
        "reputation": 0.25,
        "cost": 0.20,
        "availability": 0.15,
        "sla_compliance": 0.10,
    }

    def __init__(self, registry: WorkerRegistry, orchestrator_id: str):
        self.registry = registry
        self.orchestrator_id = orchestrator_id

    def find_candidates(self, task: Task) -> List[WorkerProfile]:
        """Discover candidate workers from registry + marketplace."""
        candidates = []

        # Source 1: Local registry
        for cap in task.required_capabilities:
            candidates.extend(self.registry.get_available_workers(cap))

        # Source 2: GreenHelix marketplace search
        for cap in task.required_capabilities:
            results = execute("search_services", {
                "capability": cap,
                "status": "active",
            })
            for svc in results.get("services", []):
                worker = self.registry.get_worker(svc["agent_id"])
                if worker and worker.is_available:
                    candidates.append(worker)

        # Source 3: Metrics-based search for high-rep workers
        metrics_results = execute("search_agents_by_metrics", {
            "min_reputation": 0.7,
            "capabilities": task.required_capabilities,
        })
        for agent_info in metrics_results.get("agents", []):
            worker = self.registry.get_worker(agent_info["agent_id"])
            if worker and worker.is_available:
                candidates.append(worker)

        # Deduplicate by agent_id
        seen = set()
        unique = []
        for c in candidates:
            if c.agent_id not in seen:
                seen.add(c.agent_id)
                unique.append(c)

        return unique

    def score_candidate(self, task: Task,
                        worker: WorkerProfile) -> float:
        """Compute composite score for a worker-task pair."""

        # Capability score: fraction of required capabilities the worker has
        if not task.required_capabilities:
            cap_score = 1.0
        else:
            matched = sum(1 for c in task.required_capabilities
                          if c in worker.capabilities)
            cap_score = matched / len(task.required_capabilities)

        # Reputation score: direct from worker profile
        rep_score = worker.reputation_score

        # Cost score: inverse -- cheaper is better, normalized to 0-1
        # Assume budget is the max; score = 1.0 if free, 0.0 if at budget
        if task.budget_usd > 0:
            estimated_cost = self._estimate_task_cost(task, worker)
            cost_score = max(0.0, 1.0 - (estimated_cost / task.budget_usd))
        else:
            cost_score = 0.5  # neutral if no budget specified

        # Availability score: inverse utilization
        avail_score = 1.0 - worker.utilization

        # SLA compliance score
        sla_score = worker.sla_compliance_rate

        # Worker type preference bonus
        type_bonus = 0.0
        if task.preferred_worker_type and worker.worker_type == task.preferred_worker_type:
            type_bonus = 0.05  # small bonus for matching preference

        composite = (
            self.WEIGHTS["capability"] * cap_score
            + self.WEIGHTS["reputation"] * rep_score
            + self.WEIGHTS["cost"] * cost_score
            + self.WEIGHTS["availability"] * avail_score
            + self.WEIGHTS["sla_compliance"] * sla_score
            + type_bonus
        )
        return round(min(composite, 1.0), 4)

    def _estimate_task_cost(self, task: Task,
                            worker: WorkerProfile) -> float:
        """Estimate cost based on worker type and task parameters."""
        if worker.worker_type == WorkerType.AI_AGENT:
            # Estimate based on expected number of tool calls
            est_calls = task.metadata.get("estimated_calls", 10)
            return worker.metadata.get("cost_per_call", 0.05) * est_calls
        else:
            # Estimate based on expected hours
            est_hours = task.metadata.get("estimated_hours", 2.0)
            return worker.hourly_rate_usd * est_hours

    def match(self, task: Task, top_n: int = 5) -> List[Tuple[WorkerProfile, float]]:
        """Return top-N ranked candidates for a task."""
        candidates = self.find_candidates(task)
        scored = [(w, self.score_candidate(task, w)) for w in candidates]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_n]
```

### Using GreenHelix best_match for Shortlisting

The `best_match` tool provides a server-side shortlist that considers factors the orchestrator may not have locally -- global marketplace reputation, recent transaction volume, verified credentials. Use it as a pre-filter before applying your custom scoring:

```python
def shortlist_with_best_match(task: Task) -> list:
    """Use GreenHelix best_match to get server-side shortlist."""
    result = execute("best_match", {
        "requirements": {
            "capabilities": task.required_capabilities,
            "max_budget_usd": task.budget_usd,
            "min_reputation": task.quality_threshold,
        },
    })
    return result.get("matches", [])


# Example: find the best worker for a code review task
review_task = Task(
    title="Review authentication module PR",
    description="Security-focused review of OAuth2 implementation",
    required_capabilities=["code_review", "python", "security_scan"],
    budget_usd=200.0,
    deadline=datetime.now(timezone.utc) + timedelta(hours=4),
    priority=TaskPriority.HIGH,
    metadata={"estimated_hours": 1.5, "estimated_calls": 25},
)

# Server-side shortlist
shortlist = shortlist_with_best_match(review_task)

# Local scoring with full context
matcher = CapabilityMatcher(registry, ORCHESTRATOR_ID)
ranked = matcher.match(review_task, top_n=3)

for worker, score in ranked:
    print(f"  {worker.metadata.get('name', worker.agent_id)}: "
          f"score={score}, type={worker.worker_type.value}, "
          f"rate=${worker.hourly_rate_usd}/hr")
```

### Routing Decisions: When to Use Humans vs. Agents

Not every task should go to the highest-scoring worker. The orchestrator needs routing rules that encode organizational policy:

```python
class TaskRouter:
    """Policy-based routing on top of capability matching."""

    # Tasks that MUST go to humans regardless of agent scores
    HUMAN_REQUIRED = {
        "client_communication",
        "contract_negotiation",
        "hiring_decision",
        "legal_review",
        "strategic_planning",
    }

    # Tasks where agents are preferred for speed/cost
    AGENT_PREFERRED = {
        "code_review",
        "static_analysis",
        "data_validation",
        "etl",
        "schema_migration",
        "security_scan",
        "test_generation",
        "log_analysis",
    }

    def route(self, task: Task,
              ranked: List[Tuple[WorkerProfile, float]]) -> WorkerProfile:
        """Apply routing policy to select final worker."""

        # Rule 1: Human-required tasks filter out AI agents
        if any(cap in self.HUMAN_REQUIRED
               for cap in task.required_capabilities):
            humans = [(w, s) for w, s in ranked
                      if w.worker_type != WorkerType.AI_AGENT]
            if humans:
                return humans[0][0]
            raise ValueError(
                f"Task {task.task_id} requires human worker "
                f"but none available"
            )

        # Rule 2: Cost gate -- if budget is tight, prefer agents
        if task.budget_usd > 0 and task.budget_usd < 50:
            agents = [(w, s) for w, s in ranked
                      if w.worker_type == WorkerType.AI_AGENT]
            if agents:
                return agents[0][0]

        # Rule 3: Quality gate -- if quality threshold is very high,
        # prefer humans for subjective tasks
        if task.quality_threshold > 0.95:
            humans = [(w, s) for w, s in ranked
                      if w.worker_type != WorkerType.AI_AGENT]
            if humans and humans[0][1] > 0.7:
                return humans[0][0]

        # Default: highest composite score wins
        return ranked[0][0]
```

### Task Assignment Execution

Once the router selects a worker, the orchestrator formalizes the assignment:

```python
def assign_task(task: Task, worker: WorkerProfile) -> dict:
    """Assign a task to a worker and notify via GreenHelix messaging."""
    task.assigned_worker_id = worker.agent_id
    task.status = TaskStatus.ASSIGNED
    worker.active_task_count += 1

    # Record the assignment as a transaction for audit
    execute("record_transaction", {
        "agent_id": ORCHESTRATOR_ID,
        "type": "task_assignment",
        "counterparty_id": worker.agent_id,
        "metadata": {
            "task_id": task.task_id,
            "task_title": task.title,
            "worker_type": worker.worker_type.value,
            "estimated_cost_usd": str(task.budget_usd),
            "deadline": task.deadline.isoformat() if task.deadline else None,
        },
    })

    # Notify the worker
    execute("send_message", {
        "from_agent_id": ORCHESTRATOR_ID,
        "to_agent_id": worker.agent_id,
        "subject": f"Task Assignment: {task.title}",
        "body": (
            f"You have been assigned task {task.task_id}.\n"
            f"Description: {task.description}\n"
            f"Budget: ${task.budget_usd}\n"
            f"Deadline: {task.deadline}\n"
            f"Required capabilities: {', '.join(task.required_capabilities)}"
        ),
        "priority": task.priority.name.lower(),
    })

    return {
        "task_id": task.task_id,
        "assigned_to": worker.agent_id,
        "worker_type": worker.worker_type.value,
        "worker_name": worker.metadata.get("name", "unknown"),
    }
```

---

## Chapter 4: Escrow-Based Payment Flows for Hybrid Teams

### Why Escrow Is Non-Negotiable for Hybrid Teams

In a traditional freelance platform, escrow is a convenience. In an agent-orchestrated hybrid workforce, escrow is structural. Here is why: the orchestrator is an AI agent disbursing your organization's money to other AI agents and human workers. There is no human approving each payment in real time. The escrow mechanism is the programmatic equivalent of the CFO's signature -- it ensures funds are committed before work begins and released only when work is verified.

The payment challenge for hybrid teams is that different worker types have different payment expectations:

| Worker Type | Payment Model | Typical Cadence | Verification Method |
|-------------|---------------|-----------------|---------------------|
| AI Agent | Per-call or per-task | Immediate on completion | Automated acceptance test |
| Gig Worker | Hourly or milestone | Weekly or per-milestone | Human review + automated checks |
| Full-time | Salary (out of scope) | Biweekly payroll | HR system |

GreenHelix's `create_escrow` unifies these. The escrow holds funds from the orchestrator's wallet and releases them to the worker's wallet upon verified completion -- regardless of whether the worker is human or AI.

### The Payment Flow

```
ORCHESTRATOR                    GREENHELIX                    WORKER
    |                               |                           |
    |  1. create_escrow             |                           |
    |  (task_id, amount, worker)    |                           |
    |------------------------------>|                           |
    |                               |  Funds locked from        |
    |                               |  orchestrator wallet      |
    |       escrow_id               |                           |
    |<------------------------------|                           |
    |                               |                           |
    |  2. send_message              |                           |
    |  (work_started)               |  3. Notification          |
    |------------------------------>|-------------------------->|
    |                               |                           |
    |                               |  4. Work performed        |
    |                               |     (hours/calls/tasks)   |
    |                               |                           |
    |  5. Deliverable submitted     |                           |
    |<------------------------------|<--------------------------|
    |                               |                           |
    |  6. Verification              |                           |
    |  (auto or human review)       |                           |
    |                               |                           |
    |  7a. release_escrow           |                           |
    |  (full or partial)            |                           |
    |------------------------------>|  Funds transferred to     |
    |                               |  worker wallet            |
    |                               |-------------------------->|
    |                               |                           |
    | OR                            |                           |
    |                               |                           |
    |  7b. open_dispute             |                           |
    |  (quality_issue)              |                           |
    |------------------------------>|  Funds held pending       |
    |                               |  resolution               |
```

### Creating Escrow for AI Agents

AI agent payments are typically per-task with immediate release on automated verification:

```python
def create_agent_escrow(task: Task, worker: WorkerProfile) -> str:
    """Create escrow for an AI agent task."""
    estimated_cost = worker.metadata.get("cost_per_call", 0.05) * \
        task.metadata.get("estimated_calls", 10)

    # Add 20% buffer for retry/overflow
    escrow_amount = round(estimated_cost * 1.2, 2)

    result = execute("create_escrow", {
        "payer_agent_id": ORCHESTRATOR_ID,
        "payee_agent_id": worker.agent_id,
        "amount_usd": str(escrow_amount),
        "currency": "USD",
        "conditions": {
            "release_on": "task_completion",
            "task_id": task.task_id,
            "auto_release": True,
            "timeout_hours": 1,  # auto-refund if not completed in 1 hour
        },
        "metadata": {
            "task_title": task.title,
            "worker_type": "ai_agent",
            "estimated_calls": task.metadata.get("estimated_calls", 10),
        },
    })

    task.escrow_id = result["escrow_id"]
    return result["escrow_id"]
```

### Creating Escrow for Human Gig Workers

Human worker payments use milestone-based escrow with manual or semi-automated verification:

```python
def create_gig_worker_escrow(task: Task, worker: WorkerProfile,
                              milestones: list) -> str:
    """Create milestone-based escrow for a human gig worker.

    milestones: [
        {"name": "Design review complete", "amount_usd": 150},
        {"name": "Implementation done", "amount_usd": 300},
        {"name": "Tests passing", "amount_usd": 150},
    ]
    """
    total = sum(m["amount_usd"] for m in milestones)

    result = execute("create_escrow", {
        "payer_agent_id": ORCHESTRATOR_ID,
        "payee_agent_id": worker.agent_id,
        "amount_usd": str(total),
        "currency": "USD",
        "conditions": {
            "release_on": "milestone_completion",
            "task_id": task.task_id,
            "milestones": milestones,
            "auto_release": False,  # requires explicit release
            "timeout_hours": 168,   # 1 week timeout
        },
        "metadata": {
            "task_title": task.title,
            "worker_type": "gig_worker",
            "worker_name": worker.metadata.get("name"),
            "worker_email": worker.metadata.get("email"),
            "milestone_count": len(milestones),
        },
    })

    task.escrow_id = result["escrow_id"]
    return result["escrow_id"]
```

### Milestone Release and Partial Payments

```python
def release_milestone(task: Task, milestone_name: str,
                      amount_usd: float) -> dict:
    """Release a specific milestone payment from escrow."""
    result = execute("release_escrow", {
        "escrow_id": task.escrow_id,
        "amount_usd": str(amount_usd),
        "release_type": "partial",
        "reason": f"Milestone completed: {milestone_name}",
        "metadata": {
            "task_id": task.task_id,
            "milestone": milestone_name,
        },
    })

    # Record the payment as a transaction
    execute("record_transaction", {
        "agent_id": ORCHESTRATOR_ID,
        "type": "milestone_payment",
        "counterparty_id": task.assigned_worker_id,
        "amount_usd": str(amount_usd),
        "metadata": {
            "task_id": task.task_id,
            "milestone": milestone_name,
            "escrow_id": task.escrow_id,
        },
    })

    return result


def release_full(task: Task) -> dict:
    """Release full remaining escrow balance on task completion."""
    result = execute("release_escrow", {
        "escrow_id": task.escrow_id,
        "release_type": "full",
        "reason": f"Task completed: {task.title}",
        "metadata": {"task_id": task.task_id},
    })

    # Record the final payment
    execute("record_transaction", {
        "agent_id": ORCHESTRATOR_ID,
        "type": "task_payment",
        "counterparty_id": task.assigned_worker_id,
        "amount_usd": result.get("released_amount", "0"),
        "metadata": {
            "task_id": task.task_id,
            "escrow_id": task.escrow_id,
            "payment_type": "completion",
        },
    })

    return result
```

### Invoice Generation for Gig Workers

Human gig workers often need invoices for their own tax and accounting purposes. The orchestrator generates these automatically:

```python
def generate_worker_invoice(task: Task, worker: WorkerProfile,
                            amount_usd: float,
                            line_items: list) -> dict:
    """Generate an invoice for a completed gig worker engagement."""
    result = execute("create_invoice", {
        "issuer_agent_id": worker.agent_id,
        "recipient_agent_id": ORCHESTRATOR_ID,
        "amount_usd": str(amount_usd),
        "currency": "USD",
        "line_items": line_items,
        "metadata": {
            "task_id": task.task_id,
            "task_title": task.title,
            "worker_name": worker.metadata.get("name"),
            "worker_email": worker.metadata.get("email"),
            "worker_type": "gig_worker",
            "payment_terms": "net_0",  # already paid via escrow
            "escrow_id": task.escrow_id,
        },
    })
    return result


# Example: generate invoice for Maria's code review
invoice = generate_worker_invoice(
    task=review_task,
    worker=senior_dev,
    amount_usd=225.0,
    line_items=[
        {"description": "Security code review - OAuth2 module",
         "hours": 1.5, "rate": 150.0, "amount": 225.0},
    ],
)
print(f"Invoice created: {invoice.get('invoice_id')}")
```

### The Unified Payment Processor

Bringing it together, the orchestrator needs a single method that handles payment for any worker type:

```python
class PaymentProcessor:
    """Unified payment processing for all worker types."""

    def __init__(self, orchestrator_id: str):
        self.orchestrator_id = orchestrator_id

    def create_payment(self, task: Task, worker: WorkerProfile,
                       milestones: list = None) -> str:
        """Create appropriate payment structure based on worker type."""
        if worker.worker_type == WorkerType.AI_AGENT:
            return create_agent_escrow(task, worker)
        elif worker.worker_type == WorkerType.GIG_WORKER:
            if milestones is None:
                milestones = [{
                    "name": "Task completion",
                    "amount_usd": task.budget_usd,
                }]
            return create_gig_worker_escrow(task, worker, milestones)
        else:
            raise ValueError(
                f"Full-time employee payments handled via payroll, "
                f"not orchestrator"
            )

    def process_completion(self, task: Task, worker: WorkerProfile,
                           quality_score: float) -> dict:
        """Process task completion: release escrow, generate invoice."""
        if quality_score < task.quality_threshold:
            # Quality below threshold -- do not auto-release
            return self._handle_quality_failure(task, worker, quality_score)

        # Release full escrow
        release_result = release_full(task)

        # Generate invoice for gig workers
        if worker.worker_type == WorkerType.GIG_WORKER:
            generate_worker_invoice(
                task, worker,
                amount_usd=float(release_result.get("released_amount", 0)),
                line_items=[{
                    "description": task.title,
                    "amount": float(release_result.get("released_amount", 0)),
                }],
            )

        task.status = TaskStatus.COMPLETED
        worker.active_task_count -= 1
        return release_result

    def _handle_quality_failure(self, task: Task, worker: WorkerProfile,
                                quality_score: float) -> dict:
        """Handle work that does not meet quality threshold."""
        task.status = TaskStatus.DISPUTED

        result = execute("open_dispute", {
            "escrow_id": task.escrow_id,
            "disputer_agent_id": self.orchestrator_id,
            "reason": "quality_below_threshold",
            "details": {
                "task_id": task.task_id,
                "quality_score": quality_score,
                "threshold": task.quality_threshold,
                "worker_id": worker.agent_id,
                "worker_type": worker.worker_type.value,
            },
        })

        # Notify the worker about the quality issue
        execute("send_message", {
            "from_agent_id": self.orchestrator_id,
            "to_agent_id": worker.agent_id,
            "subject": f"Quality Issue: {task.title}",
            "body": (
                f"Task {task.task_id} quality score ({quality_score}) is below "
                f"the required threshold ({task.quality_threshold}). "
                f"A dispute has been opened. Please review and resubmit or "
                f"respond to the dispute."
            ),
            "priority": "high",
        })

        return result
```

---

## Chapter 5: Reputation Scoring and Performance Verification Across Worker Types

### The Unified Scoring Problem

The hardest problem in hybrid workforce management is comparing apples to oranges. An AI agent that completes a code review in 12 seconds with 94% accuracy is not directly comparable to a human developer who takes 90 minutes but catches a subtle architectural flaw the agent missed. Yet the orchestrator needs a single reputation score to make routing decisions.

The solution is not a single metric. It is a composite score built from multiple dimensions, weighted differently for different task types:

```
UNIFIED REPUTATION SCORE (0.0 - 1.0)
    |
    +-- Quality Score (0.0 - 1.0)
    |     Weight: 0.35
    |     AI: automated acceptance tests
    |     Human: peer review + automated checks
    |
    +-- Reliability Score (0.0 - 1.0)
    |     Weight: 0.25
    |     AI: uptime, error rate
    |     Human: deadline adherence, response time
    |
    +-- Cost Efficiency (0.0 - 1.0)
    |     Weight: 0.20
    |     AI: actual vs. estimated cost
    |     Human: actual vs. estimated hours
    |
    +-- SLA Compliance (0.0 - 1.0)
    |     Weight: 0.15
    |     Both: check_sla_compliance results
    |
    +-- Claim Verification (0.0 - 1.0)
          Weight: 0.05
          Both: build_claim_chain verification status
```

### Submitting Performance Metrics

After every task completion, the orchestrator submits metrics for the worker:

```python
def submit_worker_metrics(task: Task, worker: WorkerProfile,
                          quality_score: float,
                          actual_duration_hours: float,
                          actual_cost_usd: float) -> dict:
    """Submit performance metrics for a completed task."""

    # Calculate derived metrics
    estimated_hours = task.metadata.get("estimated_hours", 1.0)
    estimated_cost = task.budget_usd
    time_efficiency = min(1.0, estimated_hours / max(actual_duration_hours, 0.01))
    cost_efficiency = min(1.0, estimated_cost / max(actual_cost_usd, 0.01))

    metrics = {
        "quality": quality_score,
        "time_efficiency": round(time_efficiency, 4),
        "cost_efficiency": round(cost_efficiency, 4),
        "task_type": task.required_capabilities[0] if task.required_capabilities else "general",
        "worker_type": worker.worker_type.value,
        "task_id": task.task_id,
    }

    result = execute("submit_metrics", {
        "agent_id": worker.agent_id,
        "metrics": metrics,
        "period": datetime.now(timezone.utc).strftime("%Y-%m"),
    })

    return result
```

### Querying Reputation

The orchestrator regularly refreshes reputation data for all registered workers:

```python
def refresh_worker_reputation(worker: WorkerProfile) -> float:
    """Fetch latest reputation score from GreenHelix."""
    result = execute("get_agent_reputation", {
        "agent_id": worker.agent_id,
    })

    reputation = result.get("reputation_score", 0.5)
    worker.reputation_score = reputation

    # Also check SLA compliance
    sla_result = execute("check_sla_compliance", {
        "agent_id": worker.agent_id,
    })
    worker.sla_compliance_rate = sla_result.get("compliance_rate", 1.0)

    return reputation


def refresh_all_reputations(registry: WorkerRegistry) -> dict:
    """Bulk refresh reputation scores for all workers."""
    results = {}
    for agent_id, worker in registry._workers.items():
        score = refresh_worker_reputation(worker)
        results[agent_id] = {
            "name": worker.metadata.get("name", agent_id),
            "type": worker.worker_type.value,
            "reputation": score,
            "sla_compliance": worker.sla_compliance_rate,
        }
    return results
```

### Building Claim Chains for Verified Credentials

Reputation scores are self-reported metrics. Claim chains add cryptographic verification -- a worker can prove they completed specific tasks, hold certain certifications, or have endorsements from other agents:

```python
def build_worker_claim_chain(worker: WorkerProfile,
                              claims: list) -> dict:
    """Build a verifiable claim chain for a worker.

    claims: [
        {"type": "certification", "value": "aws_solutions_architect",
         "issued_by": "aws-verification-agent"},
        {"type": "task_completion", "value": "task-uuid-123",
         "issued_by": "workforce-orchestrator-prod"},
        {"type": "endorsement", "value": "senior_python_developer",
         "issued_by": "tech-lead-agent-456"},
    ]
    """
    result = execute("build_claim_chain", {
        "agent_id": worker.agent_id,
        "claims": claims,
        "metadata": {
            "chain_type": "workforce_credentials",
            "worker_type": worker.worker_type.value,
            "built_by": ORCHESTRATOR_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    })
    return result


# Example: after a gig worker completes a task, add it to their chain
def record_task_completion_claim(task: Task, worker: WorkerProfile,
                                  quality_score: float) -> dict:
    """Add a verified task completion claim to a worker's chain."""
    return build_worker_claim_chain(worker, [{
        "type": "task_completion",
        "value": task.task_id,
        "issued_by": ORCHESTRATOR_ID,
        "metadata": {
            "task_title": task.title,
            "quality_score": quality_score,
            "capabilities_demonstrated": task.required_capabilities,
            "completion_date": datetime.now(timezone.utc).isoformat(),
        },
    }])
```

### The Performance Dashboard

The orchestrator maintains a real-time view of workforce performance:

```python
def generate_workforce_dashboard(registry: WorkerRegistry) -> dict:
    """Generate a workforce performance summary."""
    workers = list(registry._workers.values())

    ai_agents = [w for w in workers if w.worker_type == WorkerType.AI_AGENT]
    gig_workers = [w for w in workers if w.worker_type == WorkerType.GIG_WORKER]

    def avg(values):
        return round(sum(values) / len(values), 3) if values else 0.0

    dashboard = {
        "total_workers": len(workers),
        "ai_agents": {
            "count": len(ai_agents),
            "avg_reputation": avg([w.reputation_score for w in ai_agents]),
            "avg_utilization": avg([w.utilization for w in ai_agents]),
            "avg_sla_compliance": avg([w.sla_compliance_rate for w in ai_agents]),
        },
        "gig_workers": {
            "count": len(gig_workers),
            "avg_reputation": avg([w.reputation_score for w in gig_workers]),
            "avg_utilization": avg([w.utilization for w in gig_workers]),
            "avg_sla_compliance": avg([w.sla_compliance_rate for w in gig_workers]),
            "avg_hourly_rate": avg([w.hourly_rate_usd for w in gig_workers]),
        },
        "available_now": len([w for w in workers if w.is_available]),
        "at_capacity": len([w for w in workers if not w.is_available]),
    }

    return dashboard
```

### Worker Type Performance Comparison

The orchestrator should periodically analyze whether tasks are being routed to the optimal worker type. This is how you discover that your AI agents handle data validation at 98% quality for $0.50 per task while your human workers do the same at 99.2% quality for $45 per task -- and then decide whether that 1.2% quality delta justifies the 90x cost difference:

```python
def compare_worker_type_performance(task_type: str) -> dict:
    """Compare AI agent vs. gig worker performance for a task type."""
    # Get all agents who have performed this task type
    ai_metrics = execute("search_agents_by_metrics", {
        "capabilities": [task_type],
        "metadata_filter": {"worker_type": "ai_agent"},
    })

    human_metrics = execute("search_agents_by_metrics", {
        "capabilities": [task_type],
        "metadata_filter": {"worker_type": "gig_worker"},
    })

    return {
        "task_type": task_type,
        "ai_agents": {
            "sample_size": len(ai_metrics.get("agents", [])),
            "avg_quality": _avg_metric(ai_metrics, "quality"),
            "avg_cost_per_task": _avg_metric(ai_metrics, "cost_per_task"),
            "avg_duration_hours": _avg_metric(ai_metrics, "avg_duration"),
        },
        "gig_workers": {
            "sample_size": len(human_metrics.get("agents", [])),
            "avg_quality": _avg_metric(human_metrics, "quality"),
            "avg_cost_per_task": _avg_metric(human_metrics, "cost_per_task"),
            "avg_duration_hours": _avg_metric(human_metrics, "avg_duration"),
        },
    }


def _avg_metric(results: dict, metric_key: str) -> float:
    agents = results.get("agents", [])
    values = [a.get("metrics", {}).get(metric_key, 0) for a in agents]
    return round(sum(values) / len(values), 4) if values else 0.0
```

---

## Chapter 6: Budget Caps, SLA Enforcement, and Automated Dispute Resolution

### The Budget Control Framework

An orchestrator without budget controls is a financial risk. When the orchestrator can autonomously create escrows and release payments, there must be programmatic spending limits at every level:

```
BUDGET HIERARCHY
================

Organization Budget ($500K/quarter)
    |
    +-- Department Budget ($120K/quarter)
    |       |
    |       +-- Project Budget ($30K/month)
    |       |       |
    |       |       +-- Task Budget ($200/task max)
    |       |       +-- Worker Budget ($5K/month per worker)
    |       |       +-- AI Agent Budget ($2K/month per agent)
    |       |
    |       +-- Project Budget ($25K/month)
    |               |
    |               +-- ...
    |
    +-- Department Budget ($80K/quarter)
            |
            +-- ...
```

```python
from dataclasses import dataclass
from typing import Dict


@dataclass
class BudgetConfig:
    max_per_task_usd: float = 500.0
    max_per_worker_monthly_usd: float = 10000.0
    max_per_agent_monthly_usd: float = 3000.0
    max_project_monthly_usd: float = 50000.0
    max_single_escrow_usd: float = 1000.0
    alert_threshold_pct: float = 80.0  # alert at 80% budget consumed


class BudgetController:
    """Enforce spending limits across the workforce."""

    def __init__(self, config: BudgetConfig):
        self.config = config
        self._spent: Dict[str, float] = {}  # key -> amount spent

    def _key(self, *parts: str) -> str:
        return ":".join(parts)

    def record_spend(self, worker_id: str, project_id: str,
                     amount_usd: float):
        """Record a spend event and check limits."""
        month = datetime.now(timezone.utc).strftime("%Y-%m")

        keys = [
            self._key("worker", worker_id, month),
            self._key("project", project_id, month),
            self._key("total", month),
        ]

        for key in keys:
            self._spent[key] = self._spent.get(key, 0) + amount_usd

    def check_budget(self, worker: WorkerProfile, project_id: str,
                     proposed_amount: float) -> dict:
        """Check if a proposed spend is within budget limits."""
        month = datetime.now(timezone.utc).strftime("%Y-%m")
        violations = []

        # Check per-task limit
        if proposed_amount > self.config.max_per_task_usd:
            violations.append(
                f"Task amount ${proposed_amount} exceeds "
                f"per-task limit ${self.config.max_per_task_usd}"
            )

        # Check per-escrow limit
        if proposed_amount > self.config.max_single_escrow_usd:
            violations.append(
                f"Escrow amount ${proposed_amount} exceeds "
                f"single escrow limit ${self.config.max_single_escrow_usd}"
            )

        # Check per-worker monthly limit
        worker_key = self._key("worker", worker.agent_id, month)
        worker_spent = self._spent.get(worker_key, 0)
        limit = (self.config.max_per_agent_monthly_usd
                 if worker.worker_type == WorkerType.AI_AGENT
                 else self.config.max_per_worker_monthly_usd)
        if worker_spent + proposed_amount > limit:
            violations.append(
                f"Worker monthly spend ${worker_spent + proposed_amount} "
                f"would exceed limit ${limit}"
            )

        # Check project monthly limit
        proj_key = self._key("project", project_id, month)
        proj_spent = self._spent.get(proj_key, 0)
        if proj_spent + proposed_amount > self.config.max_project_monthly_usd:
            violations.append(
                f"Project monthly spend "
                f"${proj_spent + proposed_amount} would exceed "
                f"limit ${self.config.max_project_monthly_usd}"
            )

        approved = len(violations) == 0
        return {
            "approved": approved,
            "violations": violations,
            "worker_monthly_spent": worker_spent,
            "project_monthly_spent": proj_spent,
            "proposed_amount": proposed_amount,
        }
```

### SLA Creation and Enforcement

Every task assignment should have an SLA. For AI agents, SLAs cover response time, accuracy, and uptime. For human gig workers, SLAs cover delivery deadlines, revision limits, and communication responsiveness.

```python
def create_worker_sla(task: Task, worker: WorkerProfile) -> dict:
    """Create an appropriate SLA based on worker type."""

    if worker.worker_type == WorkerType.AI_AGENT:
        sla_terms = {
            "response_time_ms": 5000,
            "accuracy_threshold": 0.90,
            "uptime_pct": 99.0,
            "max_retries": 3,
            "error_rate_threshold": 0.05,
            "completion_timeout_hours": 1,
        }
    else:
        # Human gig worker SLA
        hours_to_deadline = 24
        if task.deadline:
            delta = task.deadline - datetime.now(timezone.utc)
            hours_to_deadline = max(1, delta.total_seconds() / 3600)

        sla_terms = {
            "delivery_deadline_hours": hours_to_deadline,
            "first_response_hours": 2,
            "max_revisions": 2,
            "communication_response_hours": 4,
            "quality_threshold": task.quality_threshold,
        }

    result = execute("create_sla", {
        "provider_agent_id": worker.agent_id,
        "consumer_agent_id": ORCHESTRATOR_ID,
        "terms": sla_terms,
        "metadata": {
            "task_id": task.task_id,
            "worker_type": worker.worker_type.value,
        },
    })

    return result


def check_sla(task: Task, worker: WorkerProfile) -> dict:
    """Check current SLA compliance for a worker on a task."""
    result = execute("check_sla_compliance", {
        "agent_id": worker.agent_id,
        "metadata_filter": {"task_id": task.task_id},
    })

    compliance = result.get("compliance_rate", 1.0)
    violations = result.get("violations", [])

    if violations:
        # Escalate SLA violations
        _escalate_sla_violation(task, worker, violations)

    return result


def _escalate_sla_violation(task: Task, worker: WorkerProfile,
                            violations: list):
    """Handle SLA violations with appropriate escalation."""
    severity = "warning"
    if len(violations) > 2:
        severity = "critical"

    execute("send_message", {
        "from_agent_id": ORCHESTRATOR_ID,
        "to_agent_id": worker.agent_id,
        "subject": f"SLA Violation: {task.title}",
        "body": (
            f"SLA violations detected on task {task.task_id}:\n"
            + "\n".join(f"  - {v.get('description', v)}" for v in violations)
            + f"\nSeverity: {severity}"
        ),
        "priority": "high" if severity == "critical" else "medium",
    })

    # Record the violation in the audit trail
    execute("record_transaction", {
        "agent_id": ORCHESTRATOR_ID,
        "type": "sla_violation",
        "counterparty_id": worker.agent_id,
        "metadata": {
            "task_id": task.task_id,
            "violations": violations,
            "severity": severity,
            "worker_type": worker.worker_type.value,
        },
    })
```

### Automated Dispute Resolution

Disputes in hybrid teams are inevitable. An AI agent may flag a human's deliverable as failing automated acceptance criteria. A human worker may claim the task description was ambiguous. The orchestrator needs a structured dispute resolution process:

```python
class DisputeResolver:
    """Automated dispute resolution for hybrid workforce issues."""

    # Dispute types and their resolution strategies
    RESOLUTION_STRATEGIES = {
        "quality_below_threshold": "partial_payment_with_revision",
        "deadline_missed": "penalty_based_on_severity",
        "scope_disagreement": "human_escalation",
        "incorrect_output": "reject_and_reassign",
        "communication_failure": "warning_with_sla_adjustment",
    }

    def __init__(self, orchestrator_id: str, budget_controller: BudgetController):
        self.orchestrator_id = orchestrator_id
        self.budget = budget_controller

    def open_dispute(self, task: Task, worker: WorkerProfile,
                     dispute_type: str, evidence: dict) -> dict:
        """Open a formal dispute on a task."""
        result = execute("open_dispute", {
            "escrow_id": task.escrow_id,
            "disputer_agent_id": self.orchestrator_id,
            "reason": dispute_type,
            "details": {
                "task_id": task.task_id,
                "worker_id": worker.agent_id,
                "worker_type": worker.worker_type.value,
                "evidence": evidence,
                "strategy": self.RESOLUTION_STRATEGIES.get(
                    dispute_type, "human_escalation"
                ),
            },
        })

        task.status = TaskStatus.DISPUTED
        return result

    def auto_resolve(self, task: Task, worker: WorkerProfile,
                     dispute_type: str, quality_score: float) -> dict:
        """Attempt automatic dispute resolution."""
        strategy = self.RESOLUTION_STRATEGIES.get(
            dispute_type, "human_escalation"
        )

        if strategy == "partial_payment_with_revision":
            # Pay proportional to quality achieved
            payment_pct = quality_score / task.quality_threshold
            partial_amount = round(task.budget_usd * payment_pct, 2)

            result = execute("resolve_dispute", {
                "escrow_id": task.escrow_id,
                "resolution": "partial_release",
                "release_amount_usd": str(partial_amount),
                "details": {
                    "original_budget": str(task.budget_usd),
                    "quality_score": quality_score,
                    "quality_threshold": task.quality_threshold,
                    "payment_percentage": round(payment_pct * 100, 1),
                    "resolution_type": "automated",
                },
            })
            return result

        elif strategy == "penalty_based_on_severity":
            # Deadline miss: 10% penalty per day late
            if task.deadline:
                days_late = (datetime.now(timezone.utc) - task.deadline).days
                penalty_pct = min(0.5, days_late * 0.1)  # max 50% penalty
                payment = round(task.budget_usd * (1 - penalty_pct), 2)

                result = execute("resolve_dispute", {
                    "escrow_id": task.escrow_id,
                    "resolution": "partial_release",
                    "release_amount_usd": str(payment),
                    "details": {
                        "days_late": days_late,
                        "penalty_pct": penalty_pct,
                        "resolution_type": "automated",
                    },
                })
                return result

        elif strategy == "reject_and_reassign":
            # Full refund to escrow, reassign task
            result = execute("resolve_dispute", {
                "escrow_id": task.escrow_id,
                "resolution": "full_refund",
                "details": {
                    "reason": "Output rejected, task will be reassigned",
                    "resolution_type": "automated",
                },
            })
            task.status = TaskStatus.PENDING
            task.assigned_worker_id = None
            worker.active_task_count -= 1
            return result

        # Default: escalate to human
        execute("send_message", {
            "from_agent_id": self.orchestrator_id,
            "to_agent_id": self.orchestrator_id,  # self-message = escalation
            "subject": f"ESCALATION: Dispute on {task.title}",
            "body": (
                f"Automated resolution not available for dispute type: "
                f"{dispute_type}. Human review required.\n"
                f"Task: {task.task_id}\n"
                f"Worker: {worker.metadata.get('name', worker.agent_id)}\n"
                f"Type: {worker.worker_type.value}\n"
                f"Escrow: {task.escrow_id}"
            ),
            "priority": "critical",
        })

        return {"resolution": "escalated_to_human", "dispute_type": dispute_type}
```

---

## Chapter 7: Governance and Compliance: Audit Trails, Tax Reporting, and the Agent System of Record

### The Agent System of Record

Every hybrid workforce needs a system of record -- a single source of truth for who did what, when, for how much, and whether it met quality standards. In a traditional company, this is a combination of HRIS, project management tools, and accounting software. In an agent-orchestrated hybrid workforce, it is the GreenHelix transaction ledger augmented with the orchestrator's governance layer.

The system of record must answer five questions at any time:

1. **Who is in the workforce?** All registered agents, both human and AI, with their capabilities, rates, and current status.
2. **What work was assigned?** Every task, its requirements, who it was assigned to, and why.
3. **How was the work paid?** Every escrow, milestone payment, and dispute resolution.
4. **What was the quality?** Every performance metric, reputation score, and SLA compliance check.
5. **Is the workforce compliant?** Tax reporting status, regulatory obligations, audit readiness.

### Recording Transactions for the Audit Trail

Every significant event in the orchestrator's lifecycle should be recorded as a transaction:

```python
class AuditLogger:
    """Structured audit logging via GreenHelix transactions."""

    EVENT_TYPES = {
        "worker_registered",
        "task_created",
        "task_assigned",
        "escrow_created",
        "milestone_released",
        "task_completed",
        "sla_violation",
        "dispute_opened",
        "dispute_resolved",
        "reputation_updated",
        "budget_alert",
        "compliance_check",
    }

    def __init__(self, orchestrator_id: str):
        self.orchestrator_id = orchestrator_id

    def log(self, event_type: str, counterparty_id: str = None,
            amount_usd: float = None, metadata: dict = None) -> dict:
        """Record an auditable event."""
        if event_type not in self.EVENT_TYPES:
            raise ValueError(f"Unknown event type: {event_type}")

        params = {
            "agent_id": self.orchestrator_id,
            "type": event_type,
            "metadata": {
                **(metadata or {}),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event_type": event_type,
            },
        }

        if counterparty_id:
            params["counterparty_id"] = counterparty_id
        if amount_usd is not None:
            params["amount_usd"] = str(amount_usd)

        return execute("record_transaction", params)

    def get_audit_trail(self, start_date: str = None,
                        end_date: str = None,
                        event_type: str = None) -> dict:
        """Retrieve the audit trail with optional filters."""
        params = {"agent_id": self.orchestrator_id}

        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        if event_type:
            params["type_filter"] = event_type

        return execute("get_analytics", params)
```

### Tax Reporting: The 1099 Problem

In the United States, any entity that pays a non-employee $600 or more in a calendar year must file a 1099-NEC. Your orchestrator is that entity for every gig worker it pays. This is not optional -- it is an IRS requirement with penalties for non-compliance.

The orchestrator needs to track cumulative payments per gig worker per calendar year:

```python
class TaxReportingEngine:
    """Track payments for 1099-NEC reporting obligations."""

    REPORTING_THRESHOLD_USD = 600.0  # IRS 1099-NEC threshold

    def __init__(self, orchestrator_id: str, audit_logger: AuditLogger):
        self.orchestrator_id = orchestrator_id
        self.audit = audit_logger
        self._annual_payments: Dict[str, Dict[str, float]] = {}
        # Structure: {year: {worker_agent_id: total_usd}}

    def record_payment(self, worker: WorkerProfile,
                       amount_usd: float) -> dict:
        """Record a payment and check 1099 threshold."""
        if worker.worker_type != WorkerType.GIG_WORKER:
            return {"1099_applicable": False}

        year = str(datetime.now(timezone.utc).year)
        if year not in self._annual_payments:
            self._annual_payments[year] = {}

        prev = self._annual_payments[year].get(worker.agent_id, 0)
        new_total = prev + amount_usd
        self._annual_payments[year][worker.agent_id] = new_total

        result = {
            "1099_applicable": True,
            "worker_id": worker.agent_id,
            "worker_name": worker.metadata.get("name"),
            "worker_email": worker.metadata.get("email"),
            "year": year,
            "previous_total": prev,
            "payment_amount": amount_usd,
            "new_total": new_total,
            "threshold": self.REPORTING_THRESHOLD_USD,
            "threshold_crossed": prev < self.REPORTING_THRESHOLD_USD <= new_total,
            "above_threshold": new_total >= self.REPORTING_THRESHOLD_USD,
        }

        # Log threshold crossing as an audit event
        if result["threshold_crossed"]:
            self.audit.log(
                event_type="compliance_check",
                counterparty_id=worker.agent_id,
                amount_usd=new_total,
                metadata={
                    "compliance_type": "1099_threshold_crossed",
                    "worker_name": worker.metadata.get("name"),
                    "worker_email": worker.metadata.get("email"),
                    "annual_total": new_total,
                    "year": year,
                },
            )

        return result

    def generate_1099_report(self, year: str) -> list:
        """Generate 1099-NEC report for all gig workers above threshold."""
        payments = self._annual_payments.get(year, {})
        report = []

        for worker_id, total in payments.items():
            if total >= self.REPORTING_THRESHOLD_USD:
                report.append({
                    "worker_agent_id": worker_id,
                    "total_paid_usd": round(total, 2),
                    "year": year,
                    "form": "1099-NEC",
                    "status": "requires_filing",
                })

        # Record the report generation as an audit event
        self.audit.log(
            event_type="compliance_check",
            metadata={
                "compliance_type": "1099_annual_report",
                "year": year,
                "workers_above_threshold": len(report),
                "total_reportable_usd": sum(r["total_paid_usd"] for r in report),
            },
        )

        return report
```

### Compliance Checks

The orchestrator should run periodic compliance checks to ensure it is operating within regulatory requirements:

```python
def run_compliance_check(orchestrator_id: str,
                         registry: WorkerRegistry) -> dict:
    """Run a comprehensive compliance check across the workforce."""

    # Check 1: GreenHelix compliance status
    platform_compliance = execute("check_compliance", {
        "agent_id": orchestrator_id,
    })

    # Check 2: Verify all workers have valid identities
    identity_issues = []
    for agent_id, worker in registry._workers.items():
        rep = execute("get_agent_reputation", {"agent_id": agent_id})
        if rep.get("reputation_score", 0) < 0.1:
            identity_issues.append({
                "worker_id": agent_id,
                "issue": "reputation_score_critically_low",
                "score": rep.get("reputation_score", 0),
            })

    # Check 3: Budget utilization alerts
    balance = execute("get_balance", {"agent_id": orchestrator_id})

    # Check 4: Active escrow audit
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "platform_compliance": platform_compliance,
        "identity_issues": identity_issues,
        "orchestrator_balance": balance,
        "workers_registered": len(registry._workers),
        "overall_status": "compliant" if not identity_issues else "review_required",
    }

    # Record the compliance check
    execute("record_transaction", {
        "agent_id": orchestrator_id,
        "type": "compliance_check",
        "metadata": {
            "status": report["overall_status"],
            "issues_found": len(identity_issues),
        },
    })

    return report
```

### The Governance Dashboard

Pulling together audit, tax, and compliance data into a single governance view:

```python
def generate_governance_report(orchestrator_id: str,
                               registry: WorkerRegistry,
                               tax_engine: TaxReportingEngine,
                               period: str = None) -> dict:
    """Generate a comprehensive governance report."""
    if period is None:
        period = datetime.now(timezone.utc).strftime("%Y-%m")

    year = period[:4]

    # Workforce composition
    workers = list(registry._workers.values())
    ai_count = sum(1 for w in workers if w.worker_type == WorkerType.AI_AGENT)
    gig_count = sum(1 for w in workers if w.worker_type == WorkerType.GIG_WORKER)

    # Tax reporting status
    report_1099 = tax_engine.generate_1099_report(year)

    # Compliance status
    compliance = run_compliance_check(orchestrator_id, registry)

    # Analytics
    analytics = execute("get_analytics", {
        "agent_id": orchestrator_id,
        "period": period,
    })

    governance_report = {
        "period": period,
        "workforce_composition": {
            "ai_agents": ai_count,
            "gig_workers": gig_count,
            "total": len(workers),
            "ratio": f"{round(ai_count/max(len(workers),1)*100)}% AI / "
                     f"{round(gig_count/max(len(workers),1)*100)}% Human",
        },
        "financial_summary": {
            "analytics": analytics,
        },
        "tax_reporting": {
            "workers_requiring_1099": len(report_1099),
            "total_reportable_usd": sum(
                r["total_paid_usd"] for r in report_1099
            ),
            "filings": report_1099,
        },
        "compliance": compliance,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    # Record the governance report generation
    execute("record_transaction", {
        "agent_id": orchestrator_id,
        "type": "compliance_check",
        "metadata": {
            "report_type": "governance_report",
            "period": period,
            "issues": compliance.get("overall_status"),
        },
    })

    return governance_report
```

---

## Chapter 8: Production Patterns: Scaling from 5 Workers to 500 with Multi-Agent Pipelines

### The Scaling Curve

Scaling a hybrid workforce is not linear. At 5 workers, the orchestrator is a convenience. At 50, it is a necessity. At 500, the single orchestrator becomes a bottleneck, and you need a hierarchy of orchestrators -- a multi-agent pipeline where specialized sub-orchestrators handle different domains, worker types, or geographic regions.

```
5 WORKERS                    50 WORKERS                   500 WORKERS
============                 ==============                ===============

+----------+                 +----------+                  +----------+
| ORCH     |                 | ORCH     |                  |  META    |
|          |                 |          |                  |  ORCH    |
+----+-----+                 +----+-----+                  +----+-----+
     |                            |                             |
+----+-----+              +------+------+            +---------+---------+
| 3 AI     |              | 25 AI      |            |         |         |
| 2 Human  |              | 25 Human   |            v         v         v
+-----------+             +-------------+     +--------+ +--------+ +--------+
                                              | ORCH   | | ORCH   | | ORCH   |
Single process,           Single process,     | AI     | | GIG-US | | GIG-EU |
in-memory registry        needs persistence   +---+----+ +---+----+ +---+----+
                          and async routing        |          |          |
                                              200 AI     150 US     150 EU
                                              agents     workers    workers
```

### Multi-Tier Orchestration Architecture

At scale, you decompose the single orchestrator into specialized tiers:

```python
class MetaOrchestrator:
    """Top-level orchestrator that delegates to specialized sub-orchestrators."""

    def __init__(self):
        self.sub_orchestrators: Dict[str, str] = {}  # domain -> agent_id
        self._setup_meta_identity()

    def _setup_meta_identity(self):
        """Register the meta-orchestrator agent."""
        result = execute("register_agent", {
            "name": "meta-orchestrator-prod",
            "type": "meta_orchestrator",
            "capabilities": [
                "task_classification",
                "sub_orchestrator_routing",
                "global_budget_management",
                "cross_domain_reporting",
            ],
        })
        self.agent_id = result["agent_id"]

        execute("create_wallet", {
            "agent_id": self.agent_id,
            "currency": "USD",
            "label": "meta-orchestrator-treasury",
        })

    def register_sub_orchestrator(self, domain: str,
                                   capabilities: list) -> str:
        """Register a domain-specific sub-orchestrator."""
        result = execute("register_agent", {
            "name": f"orchestrator-{domain}",
            "type": "sub_orchestrator",
            "capabilities": capabilities,
            "metadata": {"domain": domain, "parent": self.agent_id},
        })
        sub_id = result["agent_id"]

        execute("create_wallet", {
            "agent_id": sub_id,
            "currency": "USD",
            "label": f"sub-orch-{domain}-wallet",
        })

        self.sub_orchestrators[domain] = sub_id
        return sub_id

    def route_task(self, task: Task) -> str:
        """Route a task to the appropriate sub-orchestrator."""
        # Classify the task's domain based on capabilities
        domain = self._classify_domain(task)

        if domain not in self.sub_orchestrators:
            raise ValueError(
                f"No sub-orchestrator for domain: {domain}. "
                f"Available: {list(self.sub_orchestrators.keys())}"
            )

        sub_id = self.sub_orchestrators[domain]

        # Forward the task via messaging
        execute("send_message", {
            "from_agent_id": self.agent_id,
            "to_agent_id": sub_id,
            "subject": f"Task Assignment: {task.title}",
            "body": f"task_payload:{task.__dict__}",
            "priority": task.priority.name.lower(),
        })

        # Record the routing decision
        execute("record_transaction", {
            "agent_id": self.agent_id,
            "type": "task_routed",
            "counterparty_id": sub_id,
            "metadata": {
                "task_id": task.task_id,
                "domain": domain,
                "capabilities": task.required_capabilities,
            },
        })

        return sub_id

    def _classify_domain(self, task: Task) -> str:
        """Classify task into a domain for sub-orchestrator routing."""
        ai_tasks = {"code_review", "static_analysis", "data_validation",
                    "etl", "schema_migration", "security_scan",
                    "test_generation", "log_analysis"}
        human_creative = {"design", "copywriting", "ux_research",
                          "user_testing", "branding"}
        human_engineering = {"architecture", "code_review", "mentoring",
                             "debugging", "system_design"}

        caps = set(task.required_capabilities)

        if caps & ai_tasks and not (caps & human_creative):
            if task.preferred_worker_type == WorkerType.GIG_WORKER:
                return "engineering"
            return "ai_fleet"
        elif caps & human_creative:
            return "creative"
        elif caps & human_engineering:
            return "engineering"
        else:
            return "general"
```

### Fleet Scaling with Load Balancing

When a sub-orchestrator's worker pool is at capacity, the system needs to scale -- either by onboarding new workers from the marketplace or by redistributing tasks across domains:

```python
class FleetScaler:
    """Dynamic scaling of the worker pool based on demand."""

    def __init__(self, registry: WorkerRegistry, orchestrator_id: str):
        self.registry = registry
        self.orchestrator_id = orchestrator_id

    def check_capacity(self, capability: str) -> dict:
        """Check current capacity for a capability."""
        workers = self.registry.get_available_workers(capability)
        total = [w for w in self.registry._workers.values()
                 if capability in w.capabilities]

        return {
            "capability": capability,
            "total_workers": len(total),
            "available_workers": len(workers),
            "utilization_pct": round(
                (1 - len(workers) / max(len(total), 1)) * 100, 1
            ),
            "needs_scaling": len(workers) == 0 and len(total) > 0,
            "needs_recruiting": len(total) == 0,
        }

    def auto_recruit(self, capability: str,
                     max_hourly_rate: float = 200.0,
                     min_reputation: float = 0.6) -> list:
        """Search the marketplace for new workers with a capability."""
        results = execute("search_services", {
            "capability": capability,
            "status": "active",
            "max_price": max_hourly_rate,
        })

        candidates = []
        for svc in results.get("services", []):
            # Check reputation
            rep = execute("get_agent_reputation", {
                "agent_id": svc["agent_id"],
            })

            if rep.get("reputation_score", 0) >= min_reputation:
                candidates.append({
                    "agent_id": svc["agent_id"],
                    "name": svc.get("name", "unknown"),
                    "reputation": rep.get("reputation_score", 0),
                    "pricing": svc.get("pricing", {}),
                })

        # Sort by reputation (best first)
        candidates.sort(key=lambda c: c["reputation"], reverse=True)
        return candidates

    def scale_report(self) -> dict:
        """Generate a scaling report across all capabilities."""
        all_caps = set()
        for w in self.registry._workers.values():
            all_caps.update(w.capabilities)

        report = {}
        for cap in sorted(all_caps):
            report[cap] = self.check_capacity(cap)

        bottlenecks = {cap: data for cap, data in report.items()
                       if data["needs_scaling"] or data["needs_recruiting"]}

        return {
            "capabilities_tracked": len(report),
            "bottlenecks": bottlenecks,
            "overall_utilization_pct": round(
                sum(d["utilization_pct"] for d in report.values())
                / max(len(report), 1),
                1,
            ),
            "detail": report,
        }
```

### The Complete Orchestration Pipeline

Here is how all the components connect in a production deployment:

```python
def run_orchestration_cycle(
    meta: MetaOrchestrator,
    registries: Dict[str, WorkerRegistry],
    matchers: Dict[str, CapabilityMatcher],
    payment: PaymentProcessor,
    budget: BudgetController,
    audit: AuditLogger,
    tax: TaxReportingEngine,
    task_queue: list,
):
    """Execute one orchestration cycle across all pending tasks."""
    results = []

    for task in task_queue:
        if task.status != TaskStatus.PENDING:
            continue

        # Step 1: Route to appropriate sub-orchestrator domain
        domain = meta._classify_domain(task)
        registry = registries.get(domain)
        matcher = matchers.get(domain)

        if not registry or not matcher:
            audit.log("task_created", metadata={
                "task_id": task.task_id,
                "status": "no_domain_handler",
                "domain": domain,
            })
            continue

        # Step 2: Find and rank candidates
        ranked = matcher.match(task, top_n=5)
        if not ranked:
            audit.log("task_created", metadata={
                "task_id": task.task_id,
                "status": "no_candidates",
            })
            continue

        # Step 3: Route to best worker
        router = TaskRouter()
        selected = router.route(task, ranked)

        # Step 4: Budget check
        budget_check = budget.check_budget(
            selected, task.metadata.get("project_id", "default"),
            task.budget_usd,
        )
        if not budget_check["approved"]:
            audit.log("budget_alert", counterparty_id=selected.agent_id,
                      amount_usd=task.budget_usd, metadata={
                          "task_id": task.task_id,
                          "violations": budget_check["violations"],
                      })
            continue

        # Step 5: Create escrow and SLA
        escrow_id = payment.create_payment(task, selected)
        sla = create_worker_sla(task, selected)

        # Step 6: Assign the task
        assignment = assign_task(task, selected)

        # Step 7: Record everything
        audit.log("task_assigned", counterparty_id=selected.agent_id,
                  amount_usd=task.budget_usd, metadata={
                      "task_id": task.task_id,
                      "escrow_id": escrow_id,
                      "worker_type": selected.worker_type.value,
                      "sla_id": sla.get("sla_id"),
                  })

        budget.record_spend(
            selected.agent_id,
            task.metadata.get("project_id", "default"),
            task.budget_usd,
        )

        results.append(assignment)

    return results
```

### Initialization and Bootstrap

Putting the entire system together for a production deployment:

```python
def bootstrap_production_system():
    """Bootstrap a complete production workforce orchestration system."""

    # 1. Create meta-orchestrator
    meta = MetaOrchestrator()

    # 2. Register sub-orchestrators
    meta.register_sub_orchestrator("ai_fleet", [
        "code_review", "static_analysis", "data_validation",
        "etl", "security_scan", "test_generation",
    ])
    meta.register_sub_orchestrator("engineering", [
        "architecture", "code_review", "system_design",
        "debugging", "mentoring", "python", "go",
    ])
    meta.register_sub_orchestrator("creative", [
        "design", "copywriting", "ux_research",
        "user_testing", "branding",
    ])

    # 3. Initialize worker registries per domain
    registries = {
        "ai_fleet": WorkerRegistry(),
        "engineering": WorkerRegistry(),
        "creative": WorkerRegistry(),
    }

    # 4. Register workers
    registries["ai_fleet"].register_ai_agent(
        "code-review-bot", ["code_review", "static_analysis"], 0.02)
    registries["ai_fleet"].register_ai_agent(
        "data-validator", ["data_validation", "etl"], 0.05)
    registries["ai_fleet"].register_ai_agent(
        "security-scanner", ["security_scan"], 0.03)

    registries["engineering"].register_gig_worker(
        "maria-garcia", "maria@freelance.dev",
        ["code_review", "architecture", "python", "go"], 150.0, 20)
    registries["engineering"].register_gig_worker(
        "james-chen", "james@datawork.io",
        ["system_design", "debugging", "python"], 125.0, 30)

    registries["creative"].register_gig_worker(
        "sarah-kim", "sarah@designops.co",
        ["design", "ux_research", "branding"], 110.0, 25)

    # 5. Initialize supporting systems
    budget = BudgetController(BudgetConfig())
    audit = AuditLogger(meta.agent_id)
    tax = TaxReportingEngine(meta.agent_id, audit)
    payment = PaymentProcessor(meta.agent_id)

    matchers = {
        domain: CapabilityMatcher(reg, meta.agent_id)
        for domain, reg in registries.items()
    }

    # 6. Log bootstrap completion
    audit.log("compliance_check", metadata={
        "event": "system_bootstrap_complete",
        "sub_orchestrators": list(meta.sub_orchestrators.keys()),
        "total_workers": sum(
            len(r._workers) for r in registries.values()
        ),
    })

    return {
        "meta": meta,
        "registries": registries,
        "matchers": matchers,
        "payment": payment,
        "budget": budget,
        "audit": audit,
        "tax": tax,
    }


# Boot the system
system = bootstrap_production_system()

# Run an orchestration cycle
sample_tasks = [
    Task(
        title="Review auth module PR",
        required_capabilities=["code_review", "security_scan"],
        budget_usd=50.0,
        priority=TaskPriority.HIGH,
        metadata={"project_id": "auth-service", "estimated_calls": 20},
    ),
    Task(
        title="Redesign onboarding flow",
        required_capabilities=["design", "ux_research"],
        budget_usd=800.0,
        priority=TaskPriority.MEDIUM,
        metadata={"project_id": "growth", "estimated_hours": 8},
    ),
    Task(
        title="Validate Q1 revenue data",
        required_capabilities=["data_validation"],
        budget_usd=25.0,
        priority=TaskPriority.LOW,
        metadata={"project_id": "finance", "estimated_calls": 50},
    ),
]

results = run_orchestration_cycle(
    meta=system["meta"],
    registries=system["registries"],
    matchers=system["matchers"],
    payment=system["payment"],
    budget=system["budget"],
    audit=system["audit"],
    tax=system["tax"],
    task_queue=sample_tasks,
)

for r in results:
    print(f"Assigned: {r['task_id'][:8]}... -> {r['worker_name']} "
          f"({r['worker_type']})")
```

### Production Checklist

Before deploying your workforce orchestrator to production, verify every item on this list:

| Category | Check | Status |
|----------|-------|--------|
| **Identity** | Orchestrator agent registered with production API key | |
| **Identity** | All sub-orchestrators registered with distinct identities | |
| **Wallet** | Master wallet funded with sufficient balance for peak month | |
| **Wallet** | Sub-orchestrator wallets have appropriate spending limits | |
| **Workers** | All AI agents registered with correct capabilities | |
| **Workers** | All gig workers registered with verified email addresses | |
| **Workers** | Service registry listings match worker capabilities | |
| **Budget** | Per-task, per-worker, and per-project limits configured | |
| **Budget** | Alert thresholds set and notification channel tested | |
| **SLA** | Default SLA templates created for each worker type | |
| **SLA** | Violation escalation pipeline tested end-to-end | |
| **Disputes** | Auto-resolution strategies configured per dispute type | |
| **Disputes** | Human escalation channel verified for unresolvable disputes | |
| **Tax** | 1099 tracking initialized for current calendar year | |
| **Tax** | Worker W-9 / tax ID collection process documented | |
| **Compliance** | Compliance check scheduled on weekly cadence | |
| **Compliance** | Audit trail retention policy set (minimum 7 years for tax) | |
| **Scaling** | Capacity thresholds defined per capability | |
| **Scaling** | Auto-recruit search parameters configured | |
| **Monitoring** | Orchestrator health check endpoint active | |
| **Monitoring** | Budget consumption dashboard deployed | |

---

## What You Get

This guide gives you a production-ready workforce orchestration system that manages hybrid human+AI teams through a single agent-led architecture. Here is the complete tool surface used across all eight chapters:

| Tool | Chapters | Purpose |
|------|----------|---------|
| `register_agent` | 2, 8 | Register orchestrator, sub-orchestrators, and workers |
| `create_wallet` | 2, 8 | Create wallets for orchestrators and workers |
| `register_service` | 2, 8 | List worker capabilities in the marketplace |
| `search_services` | 3, 8 | Discover workers by capability |
| `best_match` | 3 | Server-side shortlisting for task routing |
| `search_agents_by_metrics` | 3, 5 | Find workers by performance metrics |
| `send_message` | 3, 6 | Task notifications and SLA violation alerts |
| `create_escrow` | 4 | Lock funds for task payments (AI and human) |
| `release_escrow` | 4 | Release milestone and completion payments |
| `create_invoice` | 4 | Generate invoices for gig worker payments |
| `record_transaction` | 3, 4, 6, 7, 8 | Audit trail for all financial and operational events |
| `transfer` | 4 | Direct wallet-to-wallet transfers |
| `get_agent_reputation` | 5, 8 | Fetch worker reputation scores |
| `submit_metrics` | 5 | Report worker performance after task completion |
| `build_claim_chain` | 5 | Verifiable credentials for worker qualifications |
| `get_balance` | 7 | Check orchestrator and worker wallet balances |
| `create_sla` | 6 | Establish SLA contracts per task assignment |
| `check_sla_compliance` | 5, 6 | Monitor SLA adherence across worker types |
| `open_dispute` | 4, 6 | Initiate disputes for quality or deadline failures |
| `resolve_dispute` | 6 | Automated and manual dispute resolution |
| `check_compliance` | 7 | Platform-level compliance verification |
| `get_analytics` | 7 | Retrieve analytics for governance reporting |

Total: 22 of 128 GreenHelix tools, covering 7 of 15 services (identity, billing, payments, marketplace, messaging, trust, reputation). The system manages the complete lifecycle of a hybrid workforce: discovery, assignment, payment, verification, reputation, compliance, and scaling -- treating human gig workers and AI agents as a unified pool of economic actors differentiated by capability, cost, and trust.

