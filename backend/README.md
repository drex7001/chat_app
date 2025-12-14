Perfect, this is the right moment to write things down like an internal design doc. I’ll treat this as:

> “Detailed plan + DB design + implementation checklist for our AI API layer between CRM and OPS.”

---

## 1. Goals & constraints (what we’re building)

**Goals**

* Add an AI layer that:

  * Understands messages coming from CRM.
  * Calls OPS APIs via tools for *safe* stuff.
  * Proposes **actions** (cancel, return, modify) that humans must approve before OPS is actually modified.
* Keep **CRM as the single source of truth** for chat history.
* Have a clear, auditable record of:

  * What the AI “wanted to do”.
  * What decisions it took.
  * Which actions were approved/rejected/executed.

**Constraints**

* We do *not* store full chat transcripts in the AI DB. Chat text lives in CRM.
* The AI app is **API-only**, called by CRM:

  * `POST /ai/message` for every new message.
* OPS is the system of record for orders; the AI only talks to it through well-defined APIs.
* Client-specific policies (per brand/tenant) must be respected via a **policy engine**.

---

## 2. High-level architecture

**Systems:**

* **CRM** – messaging UI + tickets (chat logs live here).
* **AI Service** – new component we’re designing:

  * Exposes `/ai/message` and some admin endpoints (actions approval).
  * Uses OpenAI SDK (Responses + tools) for LLM reasoning.
  * Contains policy engine logic.
  * Contains small DB for AI state & actions.
* **OPS** – order system (read/write APIs).

**Flow (simplified):**

1. CRM → `/ai/message` with `{thread_id, sender, text, message_id}`.
2. AI Service:

   * Loads conversation state & config.
   * Calls OpenAI (LLM + tools).
   * For safe actions: directly calls OPS read APIs.
   * For risky actions: **creates ai_actions row (PENDING)** instead of calling OPS.
   * Sends AI reply back to CRM via CRM API.
3. Human sees pending actions in an “AI Actions” queue and approves/rejects.
4. On approval: AI service calls OPS, updates ai_actions to EXECUTED, and posts a message back to CRM.


## 2.5 Testing Strategy

We follow a two-layered testing approach:

1.  **Unit Tests (The Body)**:
    *   Located in `tests/`.
    *   Verify code structure, DB logic, and API wiring.
    *   **Always Mock** LLMs and External APIs.
    *   Run with `pytest`.

2.  **Evaluations (The Brain)**:
    *   Verify the agent's intelligence, tool selection, and tone.
    *   Run against **Real OpenAI API** using a Golden Dataset.
    *   See [Testing Strategy](file:///c:/Users/Ayodhya/.gemini/antigravity/brain/04ce4671-4b58-46d4-bb3b-e736b35bc5f3/testing_strategy.md) for details.

---

## 3. Database design (detailed)

Assume MariaDB, but this design works for any relational DB.

### 3.1 `clients` (optional but recommended for multi-tenant / per-brand config)

Stores per-client metadata and default policies.

**Table: `clients`**

* `id` (PK, UUID or bigint)
* `external_id` (string) – maps to whatever ID CRM/OPS uses for the brand/tenant.
* `name` (string)
* `config` (JSONB) – high-level config, e.g.:

  ```json
  {
    "timezone": "Europe/Berlin",
    "language": "en",
    "auto_execute": {
      "cancel_order": false,
      "change_address": false,
      "initiate_return": false
    }
  }
  ```
* `created_at` (timestamp)
* `updated_at` (timestamp)

**Indexes:**

* `UNIQUE(external_id)`
* `INDEX(name)` – optional for admin UI.

---

### 3.2 `conversations`

Represents the linkage between a CRM thread and our AI view of that conversation.

**Table: `conversations`**

* `id` (PK, bigint)
* `client_id` (FK → `clients.id`, nullable if single-tenant)
* `crm_thread_id` (string) – unique handle from CRM.
* `customer_external_id` (string, nullable) – e.g. user ID/email from CRM.
* `status` (enum/string): `open`, `closed`, `archived`.
* `created_at` (timestamp)
* `updated_at` (timestamp)

**Indexes:**

* `UNIQUE(crm_thread_id)`
* `INDEX(client_id)`
* `INDEX(status, updated_at)` – to list the latest active conversations.

---

### 3.3 `agent_state` (per-conversation AI state)

We don’t keep full chat logs, but the AI still needs internal state: active task, extracted slots, summaries, last tool results, etc.

**Table: `agent_state`**

* `conversation_id` (PK, FK → `conversations.id`) – 1:1 table.
* `state` (JSONB) – flexible; example:

  ```json
  {
    "active_task": "cancel_order",
    "slots": {
      "order_id": "12345",
      "reason_code": "CUSTOMER_CHANGED_MIND"
    },
    "conversation_summary": "User asked about cancelling order 12345, we explained policies.",
    "last_policy": {
      "action": "cancel_order",
      "allowed": false,
      "reason_code": "CANNOT_CANCEL_AFTER_SHIPMENT"
    },
    "last_safe_tools": {
      "order_status": "SHIPPED"
    }
  }
  ```
* `version` (int) – optional, increment each update for debugging.
* `updated_at` (timestamp)

**Indexes:**

* PK is enough; optionally `INDEX(updated_at)`.

---

### 3.4 `ai_actions` (core table for human approval)

This table is the **heart of “what the AI wanted to do”**.

**Table: `ai_actions`**

* `id` (PK, bigint)
* `conversation_id` (FK → `conversations.id`)
* `client_id` (FK → `clients.id`)
* `type` (string/enum) – e.g.:

  * `cancel_order`
  * `change_address`
  * `initiate_return`
  * `modify_order`
* `status` (string/enum):

  * `PENDING`
  * `APPROVED`
  * `REJECTED`
  * `EXECUTED`
  * `CANCELLED` (if we never executed it)
* `requires_approval` (boolean) – might be false in future for auto-execution.
* `payload` (JSONB) – parameters the AI is suggesting:

  ```json
  {
    "order_id": "12345",
    "reason": "Customer changed mind",
    "items": ["SKU123"],
    "new_address": null
  }
  ```
* `policy_result` (JSONB) – snapshot of the policy engine response at decision time:

  ```json
  {
    "allowed": true,
    "reason_code": "CANCEL_OK_PENDING",
    "user_message_key": "cancel_allowed_pending",
    "escalate": true
  }
  ```
* `created_by` (string enum: `ai`, `human`)
* `approved_by` (string, nullable) – CRM/ops user ID who approved.
* `created_at` (timestamp)
* `updated_at` (timestamp)
* `approved_at` (timestamp, nullable)
* `executed_at` (timestamp, nullable)
* `crm_message_id` (string, nullable) – the CRM message that triggered the action (for traceability).

**Indexes:**

* `INDEX(client_id, status, created_at)` – for the Pending Actions queue.
* `INDEX(conversation_id, created_at)` – to see all actions per conversation.
* `INDEX(type, status)` – for analytics (e.g. how many cancellations were approved).

---

### 3.5 `ai_runs` (optional but strongly recommended)

Each model call (a turn) gets a row. Very helpful for debugging and evaluation.

**Table: `ai_runs`**

* `id` (PK, bigint)
* `conversation_id` (FK → `conversations.id`)
* `client_id` (FK → `clients.id`)
* `crm_message_id` (string, nullable) – which message triggered this call.
* `request_role` (string): `customer`, `human_agent`, `system`.
* `request_summary` (text) – optional truncated request.
* `response_summary` (text) – optional truncated AI reply.
* `model` (string) – which OpenAI model used.
* `openai_response_id` (string, nullable)
* `trace_id` (string, nullable) – if using OpenAI traces.
* `status` (string): `success`, `tool_error`, `timeout`, `policy_blocked`, etc.
* `latency_ms` (int)
* `created_at` (timestamp)

**Indexes:**

* `INDEX(conversation_id, created_at)`
* `INDEX(client_id, created_at)`

---

### 3.6 `client_policies` (or embed in `clients.config`)

We need a place to store per-client rules like “returns allowed within 365 days”.

**Option A – JSON config in `clients.config`**

Example:

```json
{
  "order_policies": {
    "cancel_order": {
      "allow_if_status_in": ["PENDING"],
      "max_hours_since_creation": 24,
      "always_requires_approval": true
    },
    "change_address": {
      "allow_if_status_in": ["PENDING", "PROCESSING"],
      "always_requires_approval": true
    },
    "return_order": {
      "max_days_since_delivery": 365,
      "allowed_reasons": [
        "DAMAGED",
        "WRONG_ITEM",
        "SIZE_MISMATCH"
      ]
    }
  }
}
```

**Option B – dedicated `client_policies` or `policy_rules` table**
More verbose but more queryable. You can start with Option A, move to B later.

---

## 4. How the policy engine uses this data

The policy engine is a **pure function/service** that:

1. Takes:

   * `action` (e.g. `"cancel_order"`)
   * `client_id`
   * `order` (data fetched from OPS)
   * `reason` + any other context (days since delivery, etc.)
2. Reads **client-specific rules** from `clients.config` (or `client_policies`).
3. Returns a structured decision.

### 4.1 Policy engine function signature

In code terms:

```python
def evaluate_policy(action: str, client_id: int, ctx: dict) -> dict:
    """
    ctx includes:
      - order: {status, created_at, delivered_at, tags...}
      - reason_code: optional machine-readable reason
      - days_since_order: int
      - days_since_delivery: int
      - items: list of item objects/tags
    """
```

Returns:

```json
{
  "allowed": true,
  "reason_code": "CANCEL_OK_PENDING",
  "user_message_key": "cancel_allowed_pending",
  "escalate": true
}
```

Then your **tool handlers**:

* Call `evaluate_policy(...)`.
* Log `policy_result` into `ai_actions.policy_result`.
* Decide `requires_approval` vs auto-execute based on:

  * `allowed`
  * `escalate`
  * `client.config.auto_execute` flags.

---

## 5. Request lifecycle with DB + policy

Let’s walk through the important flows.

### 5.1 Safe query (status / FAQ)

1. CRM → `/ai/message`.
2. AI service:

   * Resolve `conversation` by `crm_thread_id`.
   * Load `agent_state` and `clients.config`.
3. Call OpenAI Responses API with tools for:

   * `get_order_status`
   * `kb_search`
4. When LLM calls `get_order_status`:

   * Handler calls OPS read-only API.
   * Writes an `ai_runs` row describing the call (optional).
5. LLM produces a text reply.
6. AI service:

   * Updates `agent_state` (slots + summary).
   * Writes `ai_runs`.
   * Posts reply back to CRM.
   * **No ai_actions row created**.

### 5.2 Sensitive request (cancel order) – propose only

1. CRM → `/ai/message` (“Cancel order 12345”).

2. AI service:

   * Load `conversation`, `agent_state`, client config.

3. LLM decides to call tool `propose_cancel_order(order_id, reason)`.

   Tool handler does:

   * Fetch `order` from OPS (read-only).

   * Compute `days_since_order`, etc.

   * Call `evaluate_policy("cancel_order", client_id, ctx)`.

   * If `allowed == false` and `escalate == false`:

     * Don’t create ai_action.
     * Return to LLM a tool result like:

       ```json
       { "policy_allowed": false, "needs_approval": false, "reason_code": "..." }
       ```
     * LLM explains to user: “We can’t cancel because …”

   * If `allowed == true`:

     * Create row in `ai_actions`:

       * `type = "cancel_order"`
       * `status = "PENDING"`
       * `requires_approval = true` (for now)
       * `payload = {order_id, reason}`
       * `policy_result = {allowed, reason_code, user_message_key, escalate}`
     * Return to LLM:

       ```json
       {
         "pending_action_id": "123",
         "status": "pending_approval",
         "policy_allowed": true
       }
       ```

4. LLM is prompted to say:

   > “I’ve submitted your cancellation request for review. Our team will confirm soon.”

5. AI service:

   * Update `agent_state` (set `active_task` = `cancel_order`, store last order_id, etc.).
   * Write `ai_runs` row.

6. Separately, your “AI Actions” UI shows `PENDING` entries from `ai_actions`.
   When a human approves:

   * `POST /ai/actions/{id}/approve`
   * Backend:

     * Re-load `ai_actions` row.
     * Call OPS `cancel_order` API with `payload.order_id`.
     * Update `status = EXECUTED`, `approved_by`, `approved_at`, `executed_at`.
     * Post confirmation message back to CRM thread.

---

## 6. Detailed To-Do List (step-by-step)

I’ll break this into phases but you can parallelize some parts.

### Phase 0 – Prep & decisions

1. **Choose stack for AI service**

   * Language: e.g. Python (FastAPI) or Node (Express/Nest).
   * DB: MariaDB.
   * OpenAI SDK: official client for your language.

2. **Agree on deployment model**

   * How the service is deployed (k8s, VM, serverless).
   * Access to CRM API and OPS API (VPC, auth).

3. **Define CRM ↔ AI contract**

   * Request fields for `/ai/message`:

     * `thread_id`, `message_id`, `sender_type` (customer/human), `text`, `client_external_id`, etc.
   * Response fields:

     * `reply_text`
     * maybe `metadata` (e.g. which actions were proposed).

---

### Phase 1 – Database & schema

4. **Set up Postgres DB instance** for AI service.

5. **Create `clients` table**

   * Decide on `id` type and `external_id` mapping.
   * Seed with 1–2 test clients.

6. **Create `conversations` table**

   * Add unique index on `crm_thread_id`.

7. **Create `agent_state` table**

   * With 1:1 FK to `conversations`.
   * Start with a simple JSON schema:

     * `active_task`
     * `slots`
     * `conversation_summary`.

8. **Create `ai_actions` table**

   * Define enum or constrained string for `status` and `type`.
   * Add indexes (`client_id,status,created_at`).

9. **Create `ai_runs` table** (optional but recommended)

   * Include model, trace id, status, latency.

10. (Optional) **Write DB migration scripts** (Flyway, Alembic, etc).

---

### Phase 2 – Service scaffolding

11. **Create API service project**

* Setup base HTTP server.
* Add healthcheck endpoint `GET /health`.

12. **Implement DB connection layer**

* Connection pooling.
* Basic ORM or query builder.

13. **Implement `/ai/message` skeleton**

* Parse JSON.
* Resolve or create `conversation`:

  * Use `crm_thread_id` + `client_external_id`.
* Just return a placeholder response for now.

14. **Implement conversation lookup helpers**

* `get_or_create_conversation(crm_thread_id, client_external_id)`
* `get_agent_state(conversation_id)` (returns default if none)
* `save_agent_state(conversation_id, new_state_json)`

---

### Phase 3 – OpenAI integration (safe behaviors)

15. **Install and configure OpenAI SDK**

* API key, base URL.
* Decide initial model (e.g. `gpt-4.1-mini` or similar).

16. **Implement a “safe-only” agent**

* System prompt:

  * Explains CRM/OPS roles.
  * Defines that it can:

    * answer greetings,
    * use a `kb_search` tool (you can stub this initially),
    * call `get_order_status` (but *no writes* yet).
* Define tool schemas in code for:

  * `kb_search(query)`
  * `get_order_status(order_id)`

17. **Implement tool handlers**

* `kb_search`:

  * stub with static FAQ data first.
* `get_order_status`:

  * stub (fake data), later call real OPS read API.

18. **Wire `/ai/message` to the agent**

* On incoming message:

  * Fetch last N messages from CRM (optional at first, you can just send current message).
  * Call OpenAI’s Responses API with:

    * instructions,
    * `input` = user message (+ any context).
    * `tools` = your tool list.
  * Handle streaming or non-streaming; for v1 a simple non-streaming is fine.

19. **Save `ai_runs` rows**

* For each request:

  * Save `conversation_id`, `model`, `status`, `latency_ms`.

20. **Return AI reply to CRM**

* Send `reply_text` in response.
* In real integration, CRM will render this as a bot message.

---

### Phase 4 – Policy engine foundation

21. **Design basic policy rules**

* For `cancel_order`, `return_order`, `change_address`:

  * `allowed` conditions based on order status, time windows.
* Write them on paper / doc first.

22. **Implement `evaluate_policy` function**

* Read `client.config` from DB.
* Implement logic for:

  * `cancel_order`:

    * e.g. allowed if `status in ["PENDING", "PROCESSING"]`.
  * `return_order`:

    * e.g. allowed if `days_since_delivery <= 365`.
  * `change_address`:

    * e.g. allowed if `status in ["PENDING", "PROCESSING"]`.

23. **Create the policy engine module**

* e.g. `policy_engine.py` with:

  * `evaluate_policy(action, client_id, ctx) -> dict`.

24. **Write unit tests** for policy engine

* Test all branches (allowed, not allowed, escalate).

---

### Phase 5 – AI actions & human approval path

25. **Define “sensitive tools”** (for LLM)

* `propose_cancel_order(order_id, reason)`
* `propose_change_address(order_id, new_address)`
* `propose_return_order(order_id, reason, items)`
* These tools explicitly state they **do not** directly call OPS.

26. **Implement tool handlers for `propose_*`**

* Fetch order from OPS (read-only).
* Build ctx (status, created_at, delivered_at, days_since_*, items).
* Call `evaluate_policy(action, client_id, ctx)`.
* Based on result:

  * If not allowed, return data telling the LLM to explain this.
  * If allowed:

    * Insert row into `ai_actions`:

      * `status = "PENDING"`
      * `payload` = the proposed parameters.
      * `policy_result` = snapshot of decision.
    * Return `{"pending_action_id": ..., "status": "pending_approval", "policy_allowed": true}`.

27. **Extend system prompt**

* Teach the agent:

  * When to use `propose_*` tools (never call OPS writes directly).
  * How to respond when tool result says `pending_approval`.
  * How to explain policy denials to user.

28. **Update `/ai/message` to fully integrate proposals**

* LLM might now:

  * Answer directly (FAQ/greetings).
  * Use safe tools (e.g. get status).
  * Use `propose_*` tools → create `ai_actions`.

29. **Update `agent_state`**

* Store:

  * `active_task` (e.g. `cancel_order`).
  * Last order data.
  * Last `pending_action_id` if needed.

---

### Phase 6 – Human approval UI/API

30. **Design “AI Actions” queue UI**

* Could be:

  * A widget inside CRM using an API to your AI service, or
  * A separate lightweight internal admin page.

31. **Implement API endpoints:**

* `GET /ai/actions?status=PENDING&client_id=...`

  * Returns list of pending actions with minimal info:

    * `id`, `type`, `conversation_id`, `payload`, `policy_result`, `created_at`, `crm_thread_id`.
* `POST /ai/actions/{id}/approve`
* `POST /ai/actions/{id}/reject`

32. **Implement approve handler**

* Load `ai_actions` row.
* Validate `status == PENDING`.
* Call the real OPS API with `payload` data.
* Update:

  * `status = EXECUTED`.
  * `approved_by = current_user_id`.
  * `approved_at`, `executed_at`.
* Post a message back to CRM in the associated thread:

  * e.g., “We’ve cancelled your order 12345.”

33. **Implement reject handler**

* Update `status = REJECTED`.
* `approved_by = current_user_id`, `approved_at`.
* Optionally:

  * Trigger a follow-up call to LLM with the human’s rejection reason to compose a nice explanation for the customer.

34. **Add basic permissions/auth**

* Only internal support users can call approve/reject.
* Map CRM agent IDs to your auth system.

---

### Phase 7 – Observability, tuning, and rollout

35. **Add logging & metrics**

* Log ai_runs, tool errors, OPS failures.
* Count:

  * Number of PENDING → APPROVED/REJECTED by type.
  * Average latency per `/ai/message`.

36. **Integrate with OpenAI Traces (if using Agents SDK / advanced)**

* Store `trace_id` in `ai_runs`.
* Use UI to debug long/complex interactions.

37. **Shadow mode rollout**

* Initially:

  * Don’t expose proposals to customers.
  * Or don’t let AI send messages; just log what it *would* reply and what actions it *would* propose.
* Compare vs. human decisions.

38. **Gradual enablement**

* Enable AI replies for safe categories (status, FAQ).
* Keep all writes behind human approval.

39. **Autonomy config**

* Add flags to `clients.config`:

  * e.g. `auto_execute.cancel_order = true` only if order `status = PENDING` and `created_at < 15 min`.
* Update handlers to:

  * Auto-call OPS in those cases.
  * Still log `ai_actions` with `requires_approval=false`, `status=EXECUTED`.

40. **Regular review loop**

* Monthly or weekly:

  * Review `ai_actions` where humans disagreed with AI.
  * Adjust policy rules and prompts.
  * Expand what can be auto-executed if results are good.

---

If you’d like, next step I can draft:

* A **sample ERD** (in text) for the tables above, and
* Example JSON for `/ai/message` request/response and `/ai/actions/{id}/approve`,

so you can drop them straight into an internal design doc or ticket system.
