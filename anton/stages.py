"""Stage templates: default tasks and gate criteria for each commercialization phase."""

from __future__ import annotations

from dataclasses import dataclass

from .models import StageName, TaskPriority


@dataclass
class TaskTemplate:
    title: str
    description: str
    priority: TaskPriority = TaskPriority.MEDIUM


@dataclass
class StageTemplate:
    name: StageName
    description: str
    tasks: list[TaskTemplate]
    gate_criteria: list[str]


STAGE_TEMPLATES: list[StageTemplate] = [
    StageTemplate(
        name=StageName.IDEATION,
        description=(
            "Capture the initial product concept, define the problem statement, "
            "and assess strategic fit."
        ),
        tasks=[
            TaskTemplate(
                "Define problem statement",
                "Clearly articulate the customer problem or market gap being addressed.",
                TaskPriority.HIGH,
            ),
            TaskTemplate(
                "Draft initial product concept",
                "Describe the proposed solution at a high level.",
                TaskPriority.HIGH,
            ),
            TaskTemplate(
                "Identify target customer segment",
                "Define the primary buyer persona and end-user.",
                TaskPriority.HIGH,
            ),
            TaskTemplate(
                "Assess strategic alignment",
                "Confirm the concept aligns with company strategy and product roadmap.",
                TaskPriority.MEDIUM,
            ),
            TaskTemplate(
                "Document preliminary assumptions",
                "List key assumptions about market, pricing, and feasibility.",
                TaskPriority.MEDIUM,
            ),
            TaskTemplate(
                "Identify key stakeholders",
                "List internal and external stakeholders who need to be involved.",
                TaskPriority.LOW,
            ),
        ],
        gate_criteria=[
            "Problem statement is clearly defined and documented",
            "Product concept has received initial sponsor/executive approval",
            "Target customer segment is identified",
            "No blocking strategic conflicts identified",
        ],
    ),
    StageTemplate(
        name=StageName.MARKET_RESEARCH,
        description=(
            "Validate the opportunity through customer discovery, competitive analysis, "
            "and market sizing."
        ),
        tasks=[
            TaskTemplate(
                "Conduct customer discovery interviews",
                "Interview at least 10 target customers to validate the problem and solution.",
                TaskPriority.CRITICAL,
            ),
            TaskTemplate(
                "Complete competitive landscape analysis",
                "Map direct and indirect competitors, their strengths, weaknesses, and pricing.",
                TaskPriority.HIGH,
            ),
            TaskTemplate(
                "Estimate total addressable market (TAM/SAM/SOM)",
                "Size the market opportunity using top-down and bottom-up methods.",
                TaskPriority.HIGH,
            ),
            TaskTemplate(
                "Identify regulatory and compliance requirements",
                "Document any applicable regulations, certifications, or legal constraints.",
                TaskPriority.HIGH,
            ),
            TaskTemplate(
                "Define unique value proposition",
                "Articulate what makes this product distinctly better for target customers.",
                TaskPriority.HIGH,
            ),
            TaskTemplate(
                "Assess distribution and channel options",
                "Identify potential go-to-market channels: direct, reseller, online, etc.",
                TaskPriority.MEDIUM,
            ),
            TaskTemplate(
                "Conduct win/loss analysis on related products",
                "Review past deals to understand what drives customer decisions.",
                TaskPriority.MEDIUM,
            ),
        ],
        gate_criteria=[
            "Customer discovery interviews completed and findings documented",
            "Competitive analysis approved by product leadership",
            "Market size estimate reviewed and validated",
            "Unique value proposition defined and differentiated",
            "No blocking regulatory issues identified",
        ],
    ),
    StageTemplate(
        name=StageName.BUSINESS_CASE,
        description=(
            "Build and validate the financial model, pricing strategy, and investment requirements."
        ),
        tasks=[
            TaskTemplate(
                "Develop financial model (P&L projection)",
                "Build a 3-year P&L including revenue, COGS, gross margin, and operating expenses.",
                TaskPriority.CRITICAL,
            ),
            TaskTemplate(
                "Define pricing strategy",
                "Determine pricing model (subscription, one-time, usage-based) and price points.",
                TaskPriority.HIGH,
            ),
            TaskTemplate(
                "Estimate investment requirements",
                "Quantify R&D, marketing, sales, and operational investment needed.",
                TaskPriority.HIGH,
            ),
            TaskTemplate(
                "Calculate ROI and payback period",
                "Model expected return on investment and time to payback.",
                TaskPriority.HIGH,
            ),
            TaskTemplate(
                "Identify key risks and mitigation plans",
                "Document top 5 business risks and proposed mitigations.",
                TaskPriority.HIGH,
            ),
            TaskTemplate(
                "Define success metrics and KPIs",
                "Set measurable goals for revenue, market share, adoption, and customer satisfaction.",
                TaskPriority.HIGH,
            ),
            TaskTemplate(
                "Obtain executive sponsorship and budget approval",
                "Present business case to leadership and secure funding commitment.",
                TaskPriority.CRITICAL,
            ),
        ],
        gate_criteria=[
            "Financial model reviewed and approved by Finance",
            "Pricing strategy approved by product and sales leadership",
            "Investment budget formally approved",
            "KPIs and success criteria defined and agreed upon",
            "Key risks documented with mitigation plans",
        ],
    ),
    StageTemplate(
        name=StageName.PRODUCT_DEVELOPMENT,
        description=(
            "Build, test, and validate the product against requirements and quality standards."
        ),
        tasks=[
            TaskTemplate(
                "Finalize product requirements document (PRD)",
                "Complete detailed requirements including functional, non-functional, and UX specs.",
                TaskPriority.CRITICAL,
            ),
            TaskTemplate(
                "Complete technical architecture design",
                "Document system architecture, integrations, and infrastructure requirements.",
                TaskPriority.HIGH,
            ),
            TaskTemplate(
                "Execute development sprints",
                "Build the product according to the PRD through iterative development cycles.",
                TaskPriority.HIGH,
            ),
            TaskTemplate(
                "Conduct internal quality assurance (QA) testing",
                "Run functional, regression, performance, and security tests.",
                TaskPriority.HIGH,
            ),
            TaskTemplate(
                "Run beta / pilot customer program",
                "Engage 3-5 pilot customers for real-world validation and feedback.",
                TaskPriority.HIGH,
            ),
            TaskTemplate(
                "Collect and incorporate pilot feedback",
                "Review pilot findings and prioritize improvements before launch.",
                TaskPriority.HIGH,
            ),
            TaskTemplate(
                "Complete security and compliance review",
                "Pass security audit and verify regulatory compliance.",
                TaskPriority.CRITICAL,
            ),
            TaskTemplate(
                "Create technical documentation",
                "Write API docs, integration guides, and internal runbooks.",
                TaskPriority.MEDIUM,
            ),
        ],
        gate_criteria=[
            "All critical and high-priority PRD requirements implemented",
            "QA sign-off with no open critical or high-severity bugs",
            "Pilot customer feedback reviewed and top issues resolved",
            "Security review passed with no unmitigated critical findings",
            "Technical documentation complete",
        ],
    ),
    StageTemplate(
        name=StageName.LAUNCH_PREPARATION,
        description=(
            "Prepare all go-to-market assets, enablement materials, and operational "
            "readiness before launch."
        ),
        tasks=[
            TaskTemplate(
                "Develop go-to-market messaging and positioning",
                "Create core messaging framework, value prop statements, and elevator pitch.",
                TaskPriority.HIGH,
            ),
            TaskTemplate(
                "Create marketing collateral",
                "Produce datasheets, website content, case studies, and demo assets.",
                TaskPriority.HIGH,
            ),
            TaskTemplate(
                "Build sales playbook",
                "Document ICP, discovery questions, objection handling, and competitive battlecards.",
                TaskPriority.HIGH,
            ),
            TaskTemplate(
                "Conduct sales and customer success training",
                "Train all customer-facing teams on the product, positioning, and demo.",
                TaskPriority.CRITICAL,
            ),
            TaskTemplate(
                "Set up pricing and packaging in billing systems",
                "Configure SKUs, pricing tiers, and contract templates.",
                TaskPriority.HIGH,
            ),
            TaskTemplate(
                "Prepare customer support resources",
                "Create FAQ, knowledge base articles, and support escalation runbook.",
                TaskPriority.HIGH,
            ),
            TaskTemplate(
                "Establish onboarding process",
                "Design and document the customer onboarding journey.",
                TaskPriority.HIGH,
            ),
            TaskTemplate(
                "Plan launch event / announcement",
                "Coordinate press release, blog post, social media, and any launch events.",
                TaskPriority.MEDIUM,
            ),
            TaskTemplate(
                "Set up analytics and monitoring dashboards",
                "Configure product usage tracking, sales pipeline dashboards, and alerts.",
                TaskPriority.MEDIUM,
            ),
        ],
        gate_criteria=[
            "Sales training completed with >90% attendance",
            "Marketing collateral reviewed and approved",
            "Pricing configured in all billing systems",
            "Support knowledge base articles published",
            "Customer onboarding process documented and tested",
            "Launch announcement content approved by marketing and legal",
        ],
    ),
    StageTemplate(
        name=StageName.GO_TO_MARKET,
        description=(
            "Execute the launch, activate channels, and begin revenue generation."
        ),
        tasks=[
            TaskTemplate(
                "Execute launch announcement",
                "Publish press release, blog post, and social media campaign.",
                TaskPriority.HIGH,
            ),
            TaskTemplate(
                "Activate sales pipeline",
                "Begin outreach to target accounts and convert pipeline to opportunities.",
                TaskPriority.CRITICAL,
            ),
            TaskTemplate(
                "Onboard first wave of customers",
                "Complete onboarding for initial customers and track time-to-value.",
                TaskPriority.HIGH,
            ),
            TaskTemplate(
                "Monitor product adoption metrics",
                "Track daily active users, feature adoption, and activation rates.",
                TaskPriority.HIGH,
            ),
            TaskTemplate(
                "Conduct weekly cross-functional launch reviews",
                "Hold weekly syncs across product, sales, marketing, and support.",
                TaskPriority.HIGH,
            ),
            TaskTemplate(
                "Address launch-critical issues",
                "Triage and resolve any customer-facing bugs or operational issues.",
                TaskPriority.CRITICAL,
            ),
            TaskTemplate(
                "Gather initial customer feedback",
                "Conduct NPS/CSAT surveys and qualitative interviews with early adopters.",
                TaskPriority.MEDIUM,
            ),
        ],
        gate_criteria=[
            "Launch announcement published",
            "First paying customer onboarded",
            "No unresolved critical product issues blocking sales",
            "Sales pipeline has sufficient coverage (3x quota)",
        ],
    ),
    StageTemplate(
        name=StageName.POST_LAUNCH_REVIEW,
        description=(
            "Evaluate launch performance against KPIs, capture learnings, and plan next iteration."
        ),
        tasks=[
            TaskTemplate(
                "Measure KPIs vs targets at 30/60/90 days",
                "Report on revenue, adoption, customer satisfaction, and pipeline vs. goals.",
                TaskPriority.HIGH,
            ),
            TaskTemplate(
                "Conduct win/loss analysis on early deals",
                "Interview sales reps and customers on won and lost deals.",
                TaskPriority.HIGH,
            ),
            TaskTemplate(
                "Aggregate customer feedback and NPS",
                "Compile and theme all qualitative and quantitative customer feedback.",
                TaskPriority.HIGH,
            ),
            TaskTemplate(
                "Identify top product improvement opportunities",
                "Prioritize a backlog of enhancements based on customer data.",
                TaskPriority.HIGH,
            ),
            TaskTemplate(
                "Conduct internal launch retrospective",
                "Run a team retrospective to capture what went well and what to improve.",
                TaskPriority.MEDIUM,
            ),
            TaskTemplate(
                "Publish post-launch report to leadership",
                "Present results, learnings, and recommended next steps to executives.",
                TaskPriority.HIGH,
            ),
            TaskTemplate(
                "Plan v2 roadmap based on learnings",
                "Define the next product iteration priorities informed by launch data.",
                TaskPriority.MEDIUM,
            ),
        ],
        gate_criteria=[
            "30/60/90-day KPI report published",
            "Post-launch retrospective completed",
            "Top improvement backlog items prioritized",
            "Leadership review meeting held",
        ],
    ),
]

STAGE_TEMPLATE_MAP: dict[StageName, StageTemplate] = {t.name: t for t in STAGE_TEMPLATES}
