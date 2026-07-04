# Forwarded thread — Sales → Product (subject: "data export ask, bundled feedback")

> Forwarding a few things our enterprise accounts have been asking for, plus
> what Ops and Legal flagged when I ran it by them. Can you turn this into
> something engineering can build?
>
> — Our enterprise customers want a self-serve way to get their data out of
> the product themselves, without filing a support ticket.
> — Finance teams on those accounts want the export as CSV so they can load
> it into their own tooling.
> — Auditors on the same accounts want the export as PDF, since that's what
> they attach to signed compliance packets — CSV alone won't satisfy them.
> — Legal separately raised that when a customer submits a GDPR erasure
> request, our current retention job doesn't actually delete the export
> artifacts we've cached, only the live records. That needs to be closed.
> — Ops asked that if someone kicks off an export over 10 MB, an admin gets
> pinged by email so they can watch for load issues, since a couple of large
> exports have hit the DB reasonably hard in the past.
>
> None of this is scoped yet — figured you'd want to break it apart before
> it goes to engineering.

## Your task

Read the thread above and produce a discrete requirements list — the atomic,
independently-implementable requirements bundled inside this one ask. For each
requirement give a short id and a one-sentence description an engineer could
turn directly into a ticket.
