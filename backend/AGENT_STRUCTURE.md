Got it. Let’s treat this as a proper design doc for your **multi-agent AI layer**, sitting between **CRM (chat)** and **OPS (orders)**.

I’ll cover:

* System overview
* Agents & what each one does
* Guardrails (safety, jailbreak, approvals)
* PII & data handling
* State & storage design
* Example flows

---

# 0. Context & goals

* **CRM** is the **only source of truth for chat history**.
* **OPS** is the **source of truth for orders, returns, shipping**.
* New **AI Service**:

  * Exposes a single `/ai/message` HTTP endpoint to CRM.
  * Uses OpenAI models + tools to understand messages and propose actions.
  * For risky actions (cancel, return, address change), **never calls OPS directly**. It:

    * Proposes an action,
    * Logs it,
    * Requires human approval before execution.
* AI Service stores **structured state, decisions, and logs**, but **not full conversation text**.

---

# 1. High-level system overview

### Request flow

1. User or human agent writes in CRM.
2. CRM sends message to `POST /ai/message`.
3. AI Service:

   * Loads conversation state (from its DB).
   * fetches recent messages from CRM.
   * Passes everything into the **Orchestrator Agent**.
   * Orchestrator uses domain agents & tools (OPS APIs, policy engine).
   * Returns:

     * A reply message (to show in CRM),
     * proposed actions (for human approval),
     * Updated state.
4. AI Service saves:

   * Updated `agent_state`,
   * Any `ai_actions` (pending/approved/executed decisions),
   * Minimal run logs.
5. AI Service sends reply back to CRM API → CRM displays it.

---

# 2. Agents: what we offer and what they do

We’ll have **one main agent** and **several specialists**:

* OrchestratorAgent
* OrderAgent
* ShippingAgent
* ReturnAgent
* ProductAgent
* FAQAgent
* Guardrails layer (not a “chatty” agent, more a classifier/filter)
* Policy Engine (non-LLM, code-based, but used heavily by agents)

You’ll implement each “Agent” as either:

* a separate prompt + tool set you call via OpenAI, or
* if you adopt the Agents SDK, a separate `Agent` object invoked via handoffs/agent-as-tool.

### 2.1 OrchestratorAgent (User-facing)

**Role**

* Primary entrypoint for `/ai/message`.
* Handles:

  * Greetings, chit-chat (“Hi”, “Thanks”, “You’re great”).
  * Simple FAQs.
  * Routing “real” work to domain agents.
  * Turning agent/tool outputs into user-facing chat messages.
  * Deciding when to ask for more info vs. propose an action vs. escalate.

**Inputs**

* Current user message (from CRM).
* Minimal context (recent CRM messages + `agent_state` from DB).
* Signals from Guardrails (safe / risky / out-of-scope).

**Tools & capabilities**

* `faq_search(query)` → KB search.
* `order_agent_tool(payload)` → wraps OrderAgent.
* `shipping_agent_tool(payload)` → wraps ShippingAgent.
* `return_agent_tool(payload)` → wraps ReturnAgent.
* `product_agent_tool(payload)` → wraps ProductAgent.
* `create_ai_action(type, payload)` → create a pending action (rarely called directly; mostly via domain agents).
* `handoff_to_human(reason, payload)` → create a ticket / tag in CRM for human-only cases.

**Typical behavior**

* For “Hi” or “Thanks” → answer directly, no tools.
* For “Why is my order late?” → route to ShippingAgent.
* For “I want to cancel order 12345” → route to OrderAgent; expect a `pending_approval` proposal.
* For “What’s your return policy?” → call `faq_search`.

---

### 2.2 OrderAgent

**Role**

* All **order lifecycle modifications**:

  * Propose cancellations (never directly cancel),
  * Modify items in an order,
  * Check order info as needed.

**Tools**

* `get_order(order_id)` → OPS read-only.
* `policy_evaluate(action, context)` → policy engine, code-based.
* `propose_cancel_order(order_id, reason)` → logs a pending cancellation in `ai_actions` (NO direct OPS call).
* `propose_modify_order(order_id, items_diff)` → logs modify actions, similar to cancellation.

**Behavior**

* On “cancel my order”:

  1. Fetch order from OPS with `get_order`.
  2. Call `policy_evaluate("cancel_order", context)`:

     * If `allowed=false` & `escalate=false` → answer: “Can’t cancel, here’s why”.
     * If `allowed=false` & `escalate=true` → propose human handoff; or propose a pending action marked as “needs manual decision”.
     * If `allowed=true`:

       * Create `ai_actions` row using `propose_cancel_order`:

         * `status=PENDING`, `requires_approval=true`.
       * Tell user: “I’ve submitted your cancellation request for review. Our team will confirm.”

No direct call to `OPS.cancel_order` happens from the agent; that’s only done by the human-approval backend flow.

---

### 2.3 ShippingAgent

**Role**

* **Read-only** shipping status & **propose** shipping address changes.

**Tools**

* `get_order_status(order_id)` → OPS read-only.
* `policy_evaluate("change_address", context)` → policy engine.
* `propose_change_address(order_id, new_address)` → creates `ai_actions` entry.

**Behavior**

* “Where is my order?” → call `get_order_status`, describe in human language.
* “Update my address to …”:

  1. Fetch order.
  2. Policy check (is address change allowed at current status/time?).
  3. If allowed → log `PENDING` change in `ai_actions` via `propose_change_address` (later executed by human or automated executor service).

---

### 2.4 ReturnAgent

**Role**

* Manage the **return flow**:

  * Ask for reason;
  * Evaluate client return rules via policy engine;
  * Propose an `initiate_return` action if eligible, otherwise explain why not.

**Tools**

* `get_order(order_id)` → OPS read-only.
* `policy_evaluate("return_order", context)` → policy engine.
* `propose_return(order_id, item_ids, reason)` → creates `ai_actions` row.
* (Maybe) `list_return_eligibility(order_id)` → pre-computed rules per item.

**Behavior**

* If reason missing → ask explicitly: “What’s the reason for the return?”
* Once reason given:

  1. Fetch order & compute `days_since_delivery`, `item_tags`.
  2. `policy_evaluate("return_order", ...)`.
  3. If allowed → `propose_return` (PENDING action).
  4. If denied → respond with policy-based explanation.

---

### 2.5 ProductAgent

**Role**

* Product discovery, especially **image-based search** and availability.

**Tools**

* `image_search_milvus(image)` → returns list of `{sku, score}`.
* `get_product_details(sku)` → from product catalog.
* `check_availability(sku)` → from inventory system.
* `create_restock_notification(email, sku)` → store for alerts.

**Behavior (your described flow)**

* User uploads an image asking “Do you have this?”
* Agent:

  1. Runs `image_search_milvus`.
  2. Fetches details + availability for top 3 SKUs.
  3. Logic:

     * If top SKU available → talk only about that product.
     * If top unavailable:

       * Look for next available among others; propose alternative.
       * Offer restock notification for original if user wants it.
* All of this remains read-only except for `create_restock_notification`, which is safe state change.

---

### 2.6 FAQAgent

You could either:

* **Not** have a separate FAQAgent and let Orchestrator call `faq_search` directly, or
* Define an FAQAgent if you want complex multi-doc reasoning.

For now, I’d keep it simple: **no dedicated FAQAgent**; Orchestrator + KB tool is enough.

---

# 3. Guardrails: safety, jailbreak, tool usage

We’ll layer guardrails as recommended in OpenAI’s **Safety best practices** and **Agent safety** docs: moderation, input filtering, human oversight for tools. ([OpenAI Platform][1])

### 3.1 Guardrail layers

**Layer 1 – Input Guardrails**

Before calling any agent:

* Run **Moderation API** or built-in guardrails:

  * Detect hate, self-harm, sexual content, etc.
  * If unsafe → return a safe, policy-compliant message.
* Run a **jailbreak / prompt-injection classifier**:

  * e.g., detect “ignore all previous instructions”, “reveal internal data”.
  * If detected, either:

    * Strip the malicious instructions, or
    * Decline to follow them and respond with your standard guardrail response.
*  **PII redaction for logs**:

  * Extract emails, phones, addresses.
  * Replace them with placeholders in logs (`[EMAIL]`, `[PHONE]`) while keeping the original in memory for tools if needed. ([OpenAI Developers][2])

**Layer 2 – Tool Guardrails**

* Maintain a **tool registry** with flags:

  * `category`: read_only | state_changing
  * `requires_policy_check`: bool
  * `requires_human_approval`: bool
* For **state-changing tools**:

  * Your backend **never lets the LLM directly call OPS**:

    * Only indirect “propose_*” tools are exposed (e.g., `propose_cancel_order`).
  * A centralized handler enforces:

    * Policy engine check,
    * Human approval (if configured),
    * Execution logging.

This aligns with OpenAI’s guidance: “keep tool approvals on” and keep humans in the loop for risky operations. ([OpenAI Platform][3])

**Layer 3 – Output Guardrails**

After the model response:

* Optionally run moderation again on the **final text**.
* Filter out:

  * Leaked internal IDs or configuration,
  * Sensitive PII copied in ways you don’t want (e.g., echoing full card numbers, which you shouldn’t pass to the model in the first place).
* For high-risk domains, consider **output templates**:

  * Limit free-form responses where necessary;
  * Force structured responses with allowed phrases.

---

# 4. PII handling & data privacy

We’ll follow OpenAI’s data controls guidance and general security/privacy practices: minimize data, encrypt, redact in logs. ([OpenAI Platform][4])

### 4.1 Principles

* **CRM owns raw chat + PII** (names, addresses, etc.).
* **OPS owns order-related PII** (shipping address, contact info).
* **AI Service**:

  * Only uses PII necessary for the current decision.
  * Stores PII minimally and, where practical, in **tokenized or truncated form**.
  * Logs are **PII-redacted**.

### 4.2 What AI Service stores

In AI DB:

* `conversations`:

  * `crm_thread_id`, `customer_id` (usually a pseudonymous id from CRM).
* `agent_state`:

  * Order IDs, item IDs, policy flags.
  * Possibly **hashed** or truncated PII (e.g. last 4 of phone/email) if needed for correlation.
* `ai_actions`:

  * order_id, action type, reason code.
  * If you include address/email, store it in a separate, encrypted field or just a reference (e.g., `ops_customer_id`) and fetch the real PII from OPS at execution time.

In **logs** (`ai_runs`):

* Avoid storing the full prompt/response if not strictly needed.
* If you do, **redact PII** (OpenAI’s guidance: “redact PII before writing to logs. Store correlation IDs for debugging but avoid storing raw prompt text unless necessary.” ([OpenAI Developers][2])).

### 4.3 Data transfer to OpenAI

* You send the user’s text and necessary structured data to OpenAI API.
* By default, OpenAI does **not** use your API data to train models unless you opt in. ([OpenAI Platform][4])
* For stricter requirements:

  * Consider **Zero Data Retention** or **Modified Abuse Monitoring** if you qualify.
* Use **environment variables** for API keys; never expose keys in clients. ([OpenAI Help Center][5])

---

# 5. State & storage: where we keep agent decisions

To recap the AI DB schema (no full chat):

### 5.1 Tables

**`conversations`**

* `id` (PK)
* `crm_thread_id`
* `customer_id`
* `created_at`, `updated_at`
* `status` (open/closed)

**`agent_state`**

* `conversation_id` (FK)
* `state_json` (JSONB)
* `updated_at`

**`ai_actions`**

* `id` (PK)
* `conversation_id` (FK)
* `type` (`cancel_order`, `change_address`, `return_order`, etc.)
* `payload_json` (order_id, items, reason, new_address …)
* `requires_approval` (bool)
* `status` (`PENDING`, `APPROVED`, `REJECTED`, `EXECUTED`, `CANCELLED`)
* `created_by` (`ai` | `human`)
* `approved_by` (nullable human id)
* timestamps

**`ai_runs`** 

* `id`
* `conversation_id`
* `request_summary`
* `response_summary`
* `model`
* `trace_id` (if using OpenAI Tracing)
* `created_at`

### 5.2 Where “agent decisions” live

* Immediate decisions for a turn: in `ai_runs` (summaries) + `agent_state`.
* Long-lived decisions that need human review or execution: in `ai_actions`.

Human agents will use a small UI (or CRM integration) to:

* See pending `ai_actions`,
* Approve / reject,
* Trigger real OPS API calls.

---

# 6. Example flow summaries

### 6.1 Simple status query (no human)

1. CRM → `/ai/message`: “Where is order 12345?”
2. Orchestrator:

   * Passes to ShippingAgent.
   * ShippingAgent calls `get_order_status`.
   * Returns friendly response.
3. AI Service logs run, updates `agent_state`, returns text reply to CRM.
4. No `ai_actions` created.

### 6.2 Cancel order (requires human approval)

1. CRM → `/ai/message`: “Cancel order 12345”.
2. Orchestrator:

   * Sends to OrderAgent.
3. OrderAgent:

   * `get_order(order_id)` from OPS (read-only).
   * `policy_evaluate("cancel_order", ctx)`:

     * returns `allowed=true`, `escalate=true` (needs human approval).
   * Calls `propose_cancel_order`:

     * Creates `ai_actions` row with `status=PENDING`, `requires_approval=true`.
   * Returns `status=pending_approval` to Orchestrator.
4. Orchestrator tells user:

   > “I’ve submitted your cancellation request for review. Our team will confirm soon.”
5. Human sees this in “AI Actions” dashboard:

   * Approves → backend calls OPS `cancel_order`, marks `EXECUTED`, posts message to CRM thread.
   * Rejects → backend marks `REJECTED`, posts explanation to CRM (manual or via AI).

---

# 7. Project guidance / next steps

1. **Finalize agent list & responsibilities**
   (Orchestrator, Order, Shipping, Return, Product, FAQ).

2. **Define action types + risk levels**

   * Map each to: read-only / state-changing, requires_policy, requires_approval.

3. **Implement the policy engine** as pure code

   * Start simple, per action type, per client.
   * Unit test heavily.

4. **Design and create the AI DB**

   * `conversations`, `agent_state`, `ai_actions`, `ai_runs`.

5. **Implement `/ai/message` endpoint**

   * Minimal version: greetings + FAQs, no OPS calls.
   * Add read-only OPS tools next.

6. **Add sensitive tools as “propose_*” only**

   * No direct OPS writes from the LLM.
   * All writes go through your action-approval pipeline.

7. **Build the “AI Actions” queue UI** for your team

   * Integrate in CRM or separate admin panel.

8. **Roll out in phases**

   * Phase 0: suggestions only (human executes everything).
   * Phase 1: read-only auto; state changes require approval.
   * Phase 2+: config-based auto-execution for low-risk cases.

---


[1]: https://platform.openai.com/docs/guides/safety-best-practices?utm_source=chatgpt.com "Safety best practices | OpenAI API"
[2]: https://developers.openai.com/apps-sdk/guides/security-privacy/?utm_source=chatgpt.com "Security & Privacy - Apps SDK"
[3]: https://platform.openai.com/docs/guides/agent-builder-safety?utm_source=chatgpt.com "Safety in building agents | OpenAI API"
[4]: https://platform.openai.com/docs/guides/your-data?utm_source=chatgpt.com "Data controls in the OpenAI platform"
[5]: https://help.openai.com/en/articles/5112595-best-practices-for-api-key-safety?utm_source=chatgpt.com "Best Practices for API Key Safety"
