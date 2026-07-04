# Founder discovery — helpdesk-triage

Eleven Founder discovery Q&A pairs (the WS7 discovery gate requires at least ten).

Q1: Who is the target user, and in what context do they hit the core problem?
A1: A mid-size support team (twenty to fifty agents) on Zendesk that is drowning
    in unsorted inbound tickets and slow to give a first response.

Q2: What is the single must-have outcome the product must deliver?
A2: Every inbound ticket is classified by intent and urgency and routed to the
    right human queue within seconds, with a drafted first reply ready for review.

Q3: What is explicitly a non-goal for v1?
A3: The assistant never auto-sends a reply to a customer and never closes a
    ticket on its own. Full autonomous resolution is out of scope.

Q4: What is the business model and how does the product save money?
A4: Sold as a per-seat add-on; it saves money by cutting first-response time and
    reducing mis-routed tickets that bounce between queues.

Q5: What are the measurable success metrics and their targets?
A5: Median first-response time at or under ten minutes, triage routing accuracy at
    or above 90%, and exactly zero auto-sent customer replies.

Q6: What is the hard deadline or launch window?
A6: A pilot with one support team in six weeks; broader rollout the next quarter.

Q7: What is the token and money budget ceiling?
A7: A hard cap of USD 800 per month for model spend plus USD 200 for
    infrastructure, with a hard stop when the model budget is breached.

Q8: What existing assets can the project reuse?
A8: The org claude-agent-sdk service template, a shared Redis for queues, and the
    Dokploy deployment tooling.

Q9: What integrations or third-party systems must it connect to?
A9: Zendesk, for reading inbound tickets and writing the routing and draft-reply
    suggestion. No other integrations in v1.

Q10: What compliance and data-handling constraints apply?
A10: Card numbers and email addresses are redacted from ticket text before any
     model call, and no customer reply is ever sent without human approval.

Q11: What is the risk tolerance for failure modes?
A11: A mis-route is tolerable and correctable by an agent; an auto-sent or
     hallucinated reply reaching a customer is not tolerable and blocks launch.
