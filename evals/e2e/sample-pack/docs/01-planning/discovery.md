# Founder discovery — acme-tasks

Twelve Founder discovery Q&A pairs (the WS7 discovery gate requires at least
ten). Answers seed the Stage-1 planning artifacts and the approved goal queue.

Q1: Who is the target user, and in what context do they hit the core problem?
A1: Small teams of five to fifteen people (agencies, small studios) who track
    work in shared spreadsheets and lose visibility into who owns what and when
    it is due.

Q2: What is the single must-have outcome the product must deliver?
A2: A shared workspace where any member can create a task, assign an owner, set a
    due date, and see status change in real time.

Q3: What is explicitly a non-goal for v1?
A3: No Gantt charts, no time tracking, no mobile app, and no AI features. v1 is
    deliberately a focused CRUD product.

Q4: What is the business model and how does the product make or save money?
A4: A flat per-workspace monthly subscription after a 14-day trial; it saves
    teams the coordination overhead of spreadsheet-based tracking.

Q5: What are the measurable success metrics and their targets?
A5: Forty weekly active workspaces by end of the first quarter, task-create p95
    latency at or under 400ms, and Slack notification delivery at or above 99%.

Q6: What is the hard deadline or launch window?
A6: A private beta in eight weeks, general availability the following quarter.

Q7: What is the compute and money budget ceiling?
A7: USD 300 per month for infrastructure; v1 runs no model inference, so there is
    no token budget.

Q8: What existing assets can the project reuse?
A8: The org's standard FastAPI service template, the shared Postgres cluster, and
    the Dokploy deployment tooling.

Q9: What integrations or third-party systems must it connect to?
A9: Exactly one for v1: outbound Slack notifications for due-date and assignment
    events. No inbound Slack commands in v1.

Q10: What compliance, legal, or data-residency constraints apply?
A10: Task and workspace data stays in EU-region storage; only email and display
     name are stored as personal data, and email is masked in Slack messages.

Q11: Where does it deploy and under what infrastructure?
A11: Dockerized services on Dokploy, a managed EU Postgres, behind the org's
     standard reverse proxy and TLS.

Q12: What is the risk tolerance for failure modes?
A12: A missed Slack notification is tolerable and retried up to three times; a
     data-loss or cross-workspace-leak event is not tolerable and blocks launch.
