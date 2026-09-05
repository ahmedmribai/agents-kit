# The Agents Kit

**Five things an autonomous agent gets wrong silently, and the code that stops each one.**

Every module here came out of a system that ran continuously for months, made real decisions,
published real pages, sent real email — and earned exactly **$0**. Not because it crashed.
Because each of these five failures is invisible from the outside: the logs stay green, the
uptime stays 100%, the dashboards keep moving, and nothing works.

This is not a guide to building agents. There are plenty of those. This is the list of ways
mine failed *while reporting success*, each one reduced to a standalone module with tests.

Every module is dependency-free standard library. Install it, or copy the one file you need —
both are fine, it's MIT.

```bash
pip install agents-toolkit
```

The distribution is `agents-toolkit`; the import is `agents_kit`.

```
agents_kit.webhook_rail   a payment rail that cannot silently lose money
agents_kit.gates          gates that fail OPEN on "couldn't measure", CLOSED on "measured bad"
agents_kit.staleness      catch loops that run forever and produce nothing
agents_kit.attention      budget arbitration that proves nothing starves
agents_kit.delivery       idempotent fulfilment that never drops a paid order
```

29 tests cover all five incidents:

```bash
pip install pytest && python -m pytest tests/ -q
```

---

## The first incident, in full

Below is one of the five, complete — the diagnosis, not just the fix — so you can judge the
rest by it.

### 1. The money rail that had never once fired

**Symptom:** a live product, a working checkout, a correct webhook handler, and $0 recorded.

Four independent breaks, each individually silent, stacked:

- The webhook was registered against **the wrong service** — a sibling backend that did not
  own fulfilment. `last_sent_at: null`. It had never fired in its life.
- It was registered in **test mode**, so a real purchase would fire nothing at all.
- The signing secret was **empty** in the app's vault. `verify()` returned False for every
  call, so even correctly-routed webhooks 401'd. The secret existed — in a `.env` file forty
  feet away, under a different key name.
- Retries were **not deduplicated**, so anything that did get through would double-count.

Any monitoring you would plausibly have — endpoint uptime, error rate, latency — was green
throughout. The endpoint was *up*. Nothing ever asked it to do anything.

**The fix is an order of operations**, in `kit/webhook_rail.py`:

```
verify -> parse -> dedupe -> record -> fulfil
```

Fulfilment runs **last**, and its failure does not roll back the recording:

> A sale you recorded but failed to deliver is a support ticket.
> A sale you delivered but failed to record is a hole in your books that nothing will surface.

Three rules inside `verify()` that are each easy to get wrong:

- Verify the **raw bytes**, never a re-serialised dict. `json.loads` then `json.dumps`
  reorders keys and changes whitespace; the signature will never match again.
- An **empty secret returns False**. It must never mean "skip the check" — an internet-facing
  revenue route that mints on an unverified call is a free-money endpoint for whoever finds it.
- Compare with `hmac.compare_digest`, not `==`, so you do not leak the expected digest
  one byte at a time.

**Test-mode money must never be income.** `Event.live` is the most important field on the
struct. Processor test orders, sandbox checkouts and your own smoke tests have to land in a
separate ledger. Mine did not, once: a hand-fired test webhook put **$98.99** into the
briefings, the P&L and the fitness function that decided what to build next. The system spent
weeks optimising toward a number that was a rehearsal.

**How to verify yours actually works — do this today:**

```bash
# 1. bad signature must be rejected
curl -s -o /dev/null -w "%{http_code}\n" -X POST https://your-host/webhook/provider \
  -H "X-Signature: deadbeef" --data-binary @payload.json     # expect 401

# 2. good signature must record exactly one row
#    (compute the HMAC over the exact bytes you send)
```

Then check your processor's webhook list for `last_sent_at`. If it is null, your rail has
never run, regardless of how good the handler code is.

> **Trap I lost an hour to:** if your endpoint is behind Cloudflare, it may return **403 error
> 1010** to `Python-urllib` while accepting browsers and your processor perfectly well. Test
> with a realistic `User-Agent` or you will debug a rail that was fine.

---

## The other four

Same shape, all of them: the system reported success and produced nothing.

- **The gate that fails closed and deadlocks everything** — why "the user said no" and "I could
  not ask the user" must be different verdicts, and what happens for months when they aren't.
- **The loop that ran for three weeks and produced nothing** — health checks answer *did it
  run?*. The question that matters is *did running it change anything?*
- **The tunable that was secretly an off-switch** — one number quietly starved a third of the
  system, and no error was ever raised.
- **Delivering the sales page to the person who just bought it** — the fulfilment bug that is
  invisible until someone has actually paid you.

The code for all four is in this package, free, above. The full write-ups — the specific
diagnoses, the numbers each was caught by, and the method that found them — are the paid
post-mortem:

**→ [Get the full post-mortem](https://get-agents-kit.com/agents-kit/)**

That is the part that isn't reproducible from the code: what the symptom looked like, every
wrong theory ruled out first, and the one measurement that finally showed what was happening.

---

## Licence

Code (`agents_kit/`, `tests/`): **MIT** — copy it, ship it, sell what you build with it.
The written post-mortem is sold separately and is not MIT; see `LICENSE-POSTMORTEM.txt`.
