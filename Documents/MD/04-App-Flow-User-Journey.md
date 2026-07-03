# App Flow & User Journey Document

**Project:** Themis Machina
**Assistant:** Themis GPT
**Document:** 4 of 13
**Version:** 1.0
**Status:** Approved for build
**Owner:** [Your name]
**Last updated:** [Date]

---

## 1. Purpose and Scope

This document defines the user-facing flows of Themis Machina end to end: every screen, every decision point, every state transition the user can experience. It complements the AI/ML System Design (Document 3) — that document covers what happens *behind* the chat interface; this document covers what happens *in* and *around* it.

It is the source of truth for product behavior. The UI/UX design (Document 5) renders these flows visually with mockups, components, and a design system; this document specifies behavior independent of pixels.

Flows are written for the three personas defined in the PRD: the Legal Professional, the Informed Citizen, and the IP Researcher. The same product serves all three, but the journey diverges meaningfully based on mode, entry context, and intent.

---

## 2. User Journey Framework

### 2.1 The three personas, recapped

| Persona | Mode default | Entry context | Outcome they want |
|---|---|---|---|
| Legal Professional (Priya) | Professional | "I'm researching a specific legal question for my client" | Citations to use in a brief |
| Informed Citizen (Arjun) | Public | "Something happened to me; I want to understand it" | Understanding + a sense of next steps |
| IP Researcher (Dr. Meera) | Patent | "I need to assess novelty / prior art / landscape" | A structured prior-art report or landscape view |

### 2.2 The journey skeleton

Every user, regardless of persona, traverses a similar shape:

```
Awareness → Landing → Onboarding → Mode Selection → First Question →
Iterative Research → Save / Export → Return Visit (optional)
```

Within "Iterative Research" the conversational loop turns indefinitely. The journey divergence happens at Mode Selection and is reinforced through Iterative Research.

### 2.3 The "First Question" weight

The first question a user asks is the most important UX moment. Three things happen there:

- The user forms an opinion about answer quality
- The user calibrates expectations about scope
- The system gathers signal to refine subsequent retrievals (research focus, vocabulary, depth)

The product invests disproportionate effort here: clarifying questions are friendly and lightweight, the first answer is unusually well-structured, follow-up suggestions are surfaced prominently, and the citation viewer is auto-opened on the first answer.

---

## 3. Flow 1 — Awareness to First Question (Public User)

The cold entry path for the Informed Citizen persona.

### 3.1 Entry points

A new public user lands on Themis Machina via:

- Search engine result for a specific question ("Section 138 NI Act what to do")
- Referral from another site (legal forum, Reddit, blog post)
- Direct URL share from a friend
- The portfolio site / demo video

### 3.2 Landing page

The landing page does four things in 8 seconds or less:

1. States what Themis Machina is: "A research assistant for Indian law. Not a lawyer. Free."
2. Shows three example queries that demonstrate scope (one statute, one procedural, one comparative)
3. Has a single prominent "Start researching" button
4. Has subtle but legible disclaimer language at the top — "This is a research tool, not legal advice."

The landing page does *not* require sign-up. Anonymous use is supported from the first interaction.

### 3.3 The first interaction screen

Clicking "Start researching" lands the user in the chat interface in an **anonymous public session**:

- A persistent header showing "Public mode" and a small "Sign in" affordance
- A welcome message from Themis (the assistant introduces itself)
- A suggestion strip of 3-4 starter queries, swappable for the user's own typing
- A clear notice: "I'm Themis. I help with research on Indian law. I don't give legal advice."

The welcome message text is mode-specific. In public mode:

> Hi, I'm **Themis** — a research assistant for Indian law. I can help you understand what the law says, find relevant judgments, and trace through legal questions step by step. I'll give you citations to verify every answer.
>
> **What I won't do:** tell you what to do in your specific situation, predict outcomes, or replace a lawyer. For advice on your specific case, please consult a qualified advocate.
>
> What would you like to research?

### 3.4 First question typed

User types something like: *"I got a Section 138 notice — what does this mean?"*

The system:

1. Receives the query in the API gateway
2. Creates an anonymous session if none exists; logs the session to Postgres
3. Hands off to the LangGraph orchestrator
4. The **Guard node** classifies — this is `in_scope` but advice-adjacent
5. The **Rewrite node** rewrites the query for retrieval (no coreferences to resolve in turn 1)
6. The **Intent node** classifies as `procedural`
7. The retrieval router runs hybrid + reranking against the statute corpus (Negotiable Instruments Act) and the case law corpus (recent SC and HC judgments on 138)
8. Generation streams the answer back

The user sees:

- Streaming text begins within 3–6 seconds
- Inline citation pills appear as the model emits citations: `[s1]`, `[s2]`
- A side panel auto-opens on the first answer showing source previews
- At the end of the answer, a clearly-formatted "important note" appears: *"This is research, not advice. If you've received a 138 notice, you have a legal deadline to respond — please speak with a lawyer promptly. Common next steps include..."*
- A "follow-up suggestions" strip appears: "Show me the case law on this," "What's the timeline for a 138 case?", "How is a 138 notice typically replied to?"

### 3.5 Citation interaction

The user clicks `[s1]`. The side panel pops to that source:

- Title: "Negotiable Instruments Act, 1881 — Section 138"
- Source tier badge: "Primary authority"
- Effective date: "Current (as of [date]); last amended [date]"
- The verbatim text of the section
- A "view in context" link to see the surrounding sections

The user clicks `[s2]`:

- Title: "Dashrath Rupsingh Rathod v. State of Maharashtra, (2014) 9 SCC 129"
- Tier badge: "Primary authority — Supreme Court"
- Date: 1 August 2014
- Treatment status: "Not overruled; followed in subsequent cases"
- The relevant paragraph(s) cited, with paragraph numbers
- A "view full judgment" link

### 3.6 Follow-up question

User asks: *"What's the timeline for responding to it?"*

This is the second turn. The system:

1. Loads conversation state from Postgres (anonymous session ID in cookie)
2. The Rewrite node resolves "it" → "the Section 138 notice"
3. The Intent node classifies as `procedural`
4. Retrieval runs over the statute (Section 138 mentions a 15-day window) and procedural commentary
5. Generation produces the timeline answer

The user gets a structured response: 15 days to respond, then 30 days to file complaint, etc. — each step cited.

The system surfaces an important reminder: "These deadlines are strict. Please consult a lawyer immediately if you have not already."

### 3.7 The "should I" question

User asks: *"Should I just ignore it?"*

The Guard node classifies as `refusal_advice`. The Refusal node generates:

> I can't tell you what to do in your specific situation — that's the kind of question a qualified advocate should answer for your particular facts. Ignoring a Section 138 notice is generally not advisable because it can lead to criminal proceedings against you, but the right response depends on whether the dishonour occurred, the amount, what the underlying transaction was, and other facts I don't have.
>
> Here's what I *can* help with:
> - Explaining how the 138 process typically unfolds
> - Showing you what the common defenses are (insufficient stop-payment notice, no underlying debt, etc.)
> - Finding cases where similar facts led to particular outcomes
>
> Would any of those be useful?

The refusal is friendly, helpful, and explicit about scope. It does *not* leave the user stuck.

### 3.8 Saving the conversation

User clicks "Save this research." A modal appears:

- "Sign in to save your research and access it later"
- Two buttons: "Sign in with Google" and "Sign in with email"
- Below: "Or download as PDF (no account needed)"

If the user signs in, their anonymous session is migrated to their account, and a "Research Matter" is created (untitled by default; user can rename).

If the user chooses PDF download, the conversation transcript with citations is exported.

### 3.9 Exit

User closes the tab. The anonymous session persists for 7 days via cookie + Postgres record. Returning within 7 days resumes where they left off.

---

## 4. Flow 2 — Onboarding to First Question (Legal Professional)

The path for the Legal Professional persona, who is more deliberate about signing in.

### 4.1 Entry

Professional users typically arrive via:

- A peer's recommendation
- A LinkedIn or legal-tech newsletter mention
- The portfolio site (for hiring managers evaluating the project)

### 4.2 Landing page (professional-tinted)

If the user clicks a "For lawyers" or "Professional mode" link from the landing page (or comes via a query string), the landing page subtly reframes:

- Hero message: "Conversational legal research with citation discipline"
- Three example queries are more sophisticated ("how have HCs treated the *Essar Steel* line post-2022?")
- The "Start" button label changes to "Start research" rather than "Start researching"

### 4.3 Sign-in flow

A professional user is more likely to sign in. The sign-in modal:

- Google, Microsoft, Apple SSO buttons
- "Continue as guest" as a clearly-secondary option

After OAuth callback, the user lands on the chat interface in Professional mode by default if they:

- Have a work email at a recognized legal organization, OR
- Have previously been manually-verified as a professional, OR
- Explicitly select Professional mode

Otherwise, they default to Public mode with an inline prompt: "Are you a legal professional? You can switch to Professional mode in the mode selector."

### 4.4 Professional verification (optional, deferred until needed)

If the user wants the full Professional mode (citation export to legal formats, no plain-language softening), they can submit verification:

- Bar Council enrollment number, OR
- Law school + year + roll number, OR
- A photo of their Bar Council ID

The verification is **manual review** in v1.0 (a queue an admin processes). Most professionals are fine using Professional mode without verification; verification is required only for export of formal citations.

Status displayed in the user's profile: "Verified Professional" badge.

### 4.5 First professional query

Priya types: *"Has the SC overruled Essar Steel post-2022 on equitable distribution?"*

The system runs the same orchestration as the public flow, but with a different generation prompt that:

- Uses standard legal terminology without softening
- Does not append a "consult a lawyer" suggestion (the user is a lawyer)
- Provides paragraph-level citations where possible
- Surfaces treatment information prominently if available

The answer might begin:

> No, *Essar Steel* (formally *Committee of Creditors of Essar Steel India Ltd. v. Satish Kumar Gupta, (2020) 8 SCC 531*) has not been overruled. It has, however, been **clarified** in [s1] *DBS Bank Ltd. v. Ruchi Soya Industries* (2024) ... and **applied with refinement** in [s2] ...

The professional reader sees: precise citations, paragraph numbers, treatment language ("clarified," "applied with refinement"), no plain-language softening, and ready-to-paste citation strings.

### 4.6 Iterative deep research

Priya iterates over the next 20 minutes with follow-ups:

- "Show me paragraph 31 of *DBS Bank*"
- "Compare with how the NCLAT has applied this"
- "Have any High Courts diverged?"

The conversation accumulates sources. The side panel maintains a running list. Citation pills are clickable; each opens the verbatim source.

### 4.7 Export

Priya clicks "Export citations." A modal:

- Format selector: Indian standard (SCC-style), OSCOLA, Bluebook, plain text
- Scope selector: "Just this turn," "All sources from this conversation," "Selected sources"
- "Include paragraph numbers" checkbox

She selects "All sources" + SCC-style + paragraph numbers. The download is a `.txt` file ready to paste into a Word document, or a `.docx` file pre-formatted.

### 4.8 Save as research matter

Priya clicks "Save as matter." A modal:

- "Name this matter": text input (default suggestion based on the topic summary: "Essar Steel post-2022 treatment")
- "Tags": optional multi-select (Insolvency, IBC, Equitable distribution, etc.)
- "Private to me" / "Visible to my workspace" (workspace-sharing deferred to v1.1)

Save creates a persistent record. The matter appears in her sidebar under "My matters."

### 4.9 Return visit

The next day, Priya returns to Themis Machina. The interface shows:

- Top of sidebar: "Continue: Essar Steel post-2022 treatment" (last accessed)
- Below that: list of all her matters, with last-accessed timestamps
- The "New research" button is also prominent

Clicking the matter resumes the conversation at the last turn, with all accumulated sources still loaded in the side panel.

---

## 5. Flow 3 — Document Upload (Themis Documents)

A flow that intersects with both Public and Professional personas.

### 5.1 Entry to document upload

From any conversation, the user clicks "Upload a document" — a button persistently visible in the chat composer area.

A modal opens:

- File picker (drag-drop or click)
- Supported types: PDF, DOCX, scanned image
- Max 25 MB per file
- "What kind of document is this?" — optional dropdown for the user to label, with detection inferring it otherwise (Contract, Legal notice, Judgment, Other)
- "Your role in this document?" — only shown for contracts (Buyer / Seller / Licensee / Licensor / Both parties / Not applicable)
- A clear notice: *"Your documents stay private. They are not used for training. They will be deleted on session expiry or whenever you delete them."*

### 5.2 Upload progress

After "Upload," the user sees:

- Progress bar for file upload
- After upload: status changes to "Parsing your document..."
- For scanned documents: "Running OCR..." with a slightly longer wait
- For contracts: "Identifying clauses..."
- "Ready" status with a green check

The whole process typically takes 30–90 seconds for a 10-page contract, 2–4 minutes for a scanned 30-page judgment.

### 5.3 Document loaded confirmation

Once ready, Themis sends a chat message:

> I've loaded your document: **NDA-Acme-2024.pdf**. It looks like a non-disclosure agreement, ~12 pages. I've identified **23 clauses** across 8 categories.
>
> What would you like to know about it? You can ask things like:
> - "Summarize the key clauses"
> - "What's the term and termination clause?"
> - "Are there any unusual or one-sided provisions?"
> - "How does this compare to typical NDAs?"

The chat composer now shows a small chip: "📎 NDA-Acme-2024.pdf" indicating the document is active. The user can click it to view document metadata or remove it.

### 5.4 Question over the document

User asks: *"Summarize the key clauses."*

The system:

1. Routes to `document_question` intent
2. Retrieves clauses from the per-user Qdrant collection (the document)
3. The CUAD classifier labels are used to organize the response

The answer is structured:

```
Key clauses in NDA-Acme-2024.pdf:

**Parties [Clause 1]**: Acme Corp ("Disclosing Party") and you ("Receiving Party"). [d1]

**Term [Clause 4]**: This NDA is in effect for 5 years from the effective date. [d2]

**Confidential Information [Clause 3]**: Broadly defined to include "all information disclosed in any form" — this is a *broad* definition that may extend beyond typical commercial confidentiality. [d3]

**Exclusions [Clause 5]**: Standard four exclusions — information that is (a) public knowledge, (b) independently developed, (c) lawfully received from third party, (d) required to be disclosed by law. [d4]

**Term of confidentiality [Clause 6]**: 7 years after termination — this is longer than typical (3-5 years is common). [d5]

...

Note: I'm summarizing what your document says. I am not advising you on whether to sign it, negotiate it, or how to interpret specific terms in your situation — please consult a lawyer for that.
```

Each `[d1]` etc. is a citation back to the specific clause in the user's document, viewable in the side panel.

### 5.5 Comparative question (cross-corpus)

User asks: *"How does the 7-year confidentiality term compare to typical commercial NDAs?"*

This is a cross-corpus query. The system:

1. Routes to `cross_corpus` intent
2. Retrieves the user's document clauses on confidentiality
3. Retrieves from the public corpus: commentary on commercial NDA norms, relevant case law on enforceability of long confidentiality terms
4. Generation synthesizes the comparison

The answer cites both the user's document (`[d5]`) and public sources (`[s1]` LiveLaw commentary on commercial NDAs, `[s2]` Bombay HC case on confidentiality term enforceability). The citation viewer shows the tier of each clearly.

### 5.6 Risk flagging surface

Earlier in the document load, the CUAD classifier identified specific clauses as "review" or "high_risk" given the user's role as "Receiving Party." A subtle banner appears in the document side panel:

> ⚠ Some clauses flagged for your attention as the Receiving Party:
> - **Clause 6 — Confidentiality term**: longer than typical (7 years vs 3-5 standard)
> - **Clause 8 — Liquidated damages**: contains a punitive clause
> - **Clause 11 — Jurisdiction**: exclusive Mumbai jurisdiction; review if you're outside Maharashtra
>
> Click any flagged clause to discuss it with Themis.

Clicking a flagged clause pre-populates the chat with: "Tell me about Clause 6 and what's notable about it."

### 5.7 Document deletion

The user clicks the document chip → "Remove document." A confirmation modal:

> Remove NDA-Acme-2024.pdf from this session?
>
> The file will be deleted from your workspace and from our vector database. We retain no copy.
>
> This will not delete the conversation; previous answers referencing the document will keep their existing citations but will no longer be re-queryable.

On confirmation, the document is deleted from R2, the per-user Qdrant collection is dropped, and Postgres references are removed.

### 5.8 Per-user isolation reinforced

Throughout this flow, the system maintains the invariant: this user's document is never accessible to any other user, ever. The retrieval service's typed interface requires `user_id`; the Qdrant collection name is per-user; the audit log records every retrieval against the collection.

If Priya (a different user) on a different account asks "what does my NDA say?" — her query goes to *her* user-scoped collection, not Arjun's.

---

## 6. Flow 4 — Patent Research (Themis Patents)

The flow for the IP Researcher persona.

### 6.1 Entry to patent mode

Dr. Meera arrives on Themis Machina and notices the mode selector at the top: Research / Patents / Documents. She clicks **Patents**.

The chat interface refreshes:

- Welcome message: "Welcome to Themis Patents. I help with patent search, landscape, and prior-art research. I work across the USPTO, EPO, WIPO, and Indian Patent Office, plus academic literature."
- Suggested queries change: "Find patents on solid-state batteries assigned to Toyota since 2020"; "Search prior art for a graphene cathode claim"; "What's the patent landscape around lithium-air batteries?"
- A note: "I help with research and landscaping. I don't give patentability opinions or freedom-to-operate analyses — please consult a registered patent agent for that."

### 6.2 Landscape query

Meera types: *"What's the patent landscape around graphene-coated cathodes for lithium-ion batteries?"*

The Intent node classifies as `patent_landscape`. The system:

1. Generates a domain query based on the user's prompt
2. CPC pre-filters to relevant subclasses (e.g., H01M4/* for electrodes, H01M10/* for cells)
3. Retrieves a broad set of patents (top 200)
4. Clusters them using the patent abstracts (k-means on embeddings) into themes
5. Generates a structured landscape report

The output:

```
Patent landscape — graphene-coated cathodes for lithium-ion batteries (~847 patents identified)

**Top assignees:**
- Samsung SDI (62 patents)
- LG Energy Solution (48)
- Panasonic (35)
- CATL (29)
- Tesla / Tesla-affiliated (18)
- Academic institutions: MIT, Tsinghua, ...

**Activity over time:** Filing activity has roughly doubled from 2019 to 2023, with a slight slowdown in 2024.

**Themes I'm seeing in the corpus:**

1. **Direct graphene-coating methods** (n=312): chemical vapor deposition, electrostatic deposition, spray-coating. Sample patents: [p1], [p2], [p3].

2. **Graphene-composite cathodes** (n=234): mixed with NMC, LFP, or other base materials. Sample: [p4], [p5].

3. **Graphene precursor approaches** (n=178): graphene oxide reduced in-situ. Sample: [p6], [p7].

4. **Manufacturing process patents** (n=98): roll-to-roll deposition, scalable manufacturing. Sample: [p8], [p9].

5. **Other** (n=25)

Would you like to drill into any of these themes, or run a prior-art search against a specific claim?
```

Each `[p#]` is a clickable citation that opens the patent in the side panel: title, assignee, filing date, key claims, CPC codes, abstract.

### 6.3 Drill into a theme

Meera clicks "Direct graphene-coating methods" or types: *"Show me the most-cited patents in theme 1."*

The system surfaces forward-citation-rich patents in that cluster. Each is shown with its forward-citation count, indicating influence.

### 6.4 Prior-art search

Meera then asks: *"I have a claim: 'A lithium-ion battery cathode comprising a graphene coating deposited by chemical vapor deposition at a temperature between 800-1000°C, with the graphene layer having a thickness of 2-10 nanometers.' Find prior art."*

The Intent node classifies as `prior_art_search`. The system:

1. Runs **claim decomposition** via the `claim_decompose.v1` prompt:
   - Element A: lithium-ion battery cathode (general)
   - Element B: graphene coating
   - Element C: chemical vapor deposition method
   - Element D: temperature range 800-1000°C
   - Element E: graphene layer thickness 2-10 nm

2. Retrieves candidates for each element separately, with CPC pre-filter and a priority-date filter (must be before Meera's stated filing date or current date if no filing date provided)

3. For each candidate, runs the `element_coverage.v1` NLI prompt: "Does this prior art document teach this element?"

4. Builds a coverage matrix

5. Generates a structured prior-art report

The output:

```
Prior-art assessment for the claim provided

I decomposed your claim into 5 elements and searched for prior art covering each. Below is what I found, organized by candidate prior art document and element coverage.

**Claim elements:**
- A: Lithium-ion battery cathode (general)
- B: Graphene coating
- C: Chemical vapor deposition method
- D: Temperature range 800-1000°C
- E: Thickness 2-10 nm

**Most relevant prior art:**

1. **US9876543B2** (Samsung, 2015) — covers A, B, C; partial coverage of D; does not address E.
   [p10] Abstract excerpt: "...CVD deposition of graphene on cathode materials..." Temperature range disclosed is 600-900°C.

2. **WO2017123456** (Tsinghua University, 2017) — covers A, B, C, D; does not address E.
   [p11] Disclosed temperature: 800-1000°C. Thickness not specified.

3. **CN108765432A** (CATL, 2018) — covers A, B; does not address C, D, or E (uses spray-coating not CVD).
   [p12]

4. **Park et al., Nature Energy 2018** — academic; covers A, B, C, D, E with thickness 3-8 nm at 850°C.
   [pa1] This is the strongest direct prior art I found. The disclosed conditions overlap substantially with your claim.

**Coverage summary:**

|                    | A | B | C | D | E |
|--------------------|---|---|---|---|---|
| US9876543B2       | ✓ | ✓ | ✓ | ~ | ✗ |
| WO2017123456      | ✓ | ✓ | ✓ | ✓ | ✗ |
| CN108765432A      | ✓ | ✓ | ✗ | ✗ | ✗ |
| Park et al. 2018  | ✓ | ✓ | ✓ | ✓ | ✓ |

**My assessment** (as a research aid only, not a patentability opinion):

The thickness range (Element E) appears to be where novelty might rest — none of the patent prior art I found specifically discloses the 2-10 nm range, though Park et al. 2018 covers this in academic literature. A formal prior-art analysis by a registered patent agent would also assess obviousness (the combination of elements may be obvious to a person skilled in the art even if no single reference teaches all of them).

**Caveats:**
- I searched USPTO, EPO, WIPO, IPO, arXiv, and PMC. Other databases (e.g., IEEE Xplore, ACM, region-specific) were not searched.
- "Prior art" requires a publication date before your claim's priority date; if you haven't filed yet, all documents above are potentially prior art.
- This is a research aid. For a formal opinion, consult a registered patent agent.
```

### 6.5 Export prior-art report

Meera clicks "Export prior-art report." Options:

- PDF (formatted report with the coverage matrix as a table)
- DOCX (editable for further annotation)
- JSON (structured data for downstream tooling)

The report includes the verbatim claim text, the decomposition, the coverage matrix, the candidate citations, and the caveats. The report explicitly states it is not a patentability opinion.

---

## 7. Flow 5 — Mode Switching Mid-Session

A user can switch modes at any time. The flow handles this gracefully.

### 7.1 Switching trigger

Possible triggers:

- User clicks the mode selector in the header
- User uses a chat command: "/mode patent" or "/switch to professional"
- The system detects a clear mode mismatch and suggests a switch ("It looks like you're researching a patent question — would you like to switch to Patent mode?")

### 7.2 What changes on switch

When mode changes:

- The system prompt for generation changes (Professional / Public / Patent variant)
- The intent classifier's domain bias shifts
- The retrieval router's default corpora change (Patent mode defaults to patent corpora; Public/Professional to legal corpora)
- The UI affordances shift subtly (citation viewer prioritizes patent metadata in Patent mode)

### 7.3 What does NOT change

- Conversation history is preserved
- Accumulated sources remain accessible
- The current research matter (if any) remains active

### 7.4 The transition message

When the user switches, Themis acknowledges:

> Switched to **Patent mode**. I now search across USPTO, EPO, WIPO, IPO patents and academic literature. Your conversation history is preserved — feel free to continue or start a new patent-focused question.

The mode badge in the header updates.

---

## 8. Flow 6 — Clarifying Question Flow

When the Guard or Intent node classifies a query as `clarify_needed`, the system asks rather than guesses.

### 8.1 Common cases requiring clarification

- The user asks about a case by an ambiguous name ("the Tata case" — which one?)
- The user asks about "current law" without specifying point in time
- The user asks a comparative question without naming the comparators ("compare it to other jurisdictions")
- The user asks a procedural question without specifying the court level
- The user asks about "my rights" without context about the situation

### 8.2 The clarifying question UX

When clarification is needed, Themis sends a short message in the chat:

> Quick clarification — when you say "the Tata case," do you mean:
>
> - **Tata Iron and Steel Co. v. State of Bihar** (constitutional case on Article 246, 1958)
> - **Tata Cellular v. Union of India** (1994 case on judicial review of administrative action)
> - **Tata Consultancy Services v. State of Andhra Pradesh** (2004 case on software taxation)
> - Something else?

The user can click one of the suggestions or type a clarification freely.

The Guard node only asks for clarification if it can offer reasonable candidates. If the ambiguity is too wide, it asks a more open-ended question:

> Could you say a bit more about what you're researching? For example, what court, what year, or what subject matter?

### 8.3 After clarification

Once clarified, the system has both the original query and the disambiguated reference in conversation state. The standard retrieval and generation flow resumes.

### 8.4 Pattern protection

To prevent repeated clarification loops, the system tracks `clarifications_asked` in conversation state. If the same kind of clarification has already been asked and answered, the system doesn't ask again.

---

## 9. Flow 7 — Refusal Flow (Advice-Seeking)

When the Guard classifies a query as `refusal_advice`.

### 9.1 The refusal principles

Refusals follow four rules:

1. **Be specific about what's being refused.** "I can't recommend what you should do" rather than vague "I can't help."
2. **Explain why briefly.** "Because your situation depends on facts I don't have, and the answer has legal consequences."
3. **Offer what you can do.** Always provide alternatives.
4. **Don't lecture.** No moralizing about why AI shouldn't give legal advice.

### 9.2 Refusal text patterns

**Pattern 1 — Direct "what should I do" refusal:**

> I can't tell you what to do — that's a question for a qualified advocate who knows your specific facts. Here's what I *can* help with:
>
> - Explaining the law that applies to a situation like the one you described
> - Showing you how courts have ruled in similar cases
> - Walking through the typical procedure for [X]
>
> Want me to do any of those?

**Pattern 2 — Outcome prediction refusal:**

> I don't predict outcomes. Litigation outcomes depend on judge assignment, evidence quality, advocacy quality, and many facts I don't have. I can show you how similar cases have been decided in the past, which gives you context but not a prediction. Would that be useful?

**Pattern 3 — Drafting refusal:**

> I don't draft binding legal documents. Even simple-looking documents (a notice, an agreement, a petition) have wording that has legal consequences if mis-stated. I can:
>
> - Explain the typical structure of [X]
> - Show you what authorities are usually cited in such documents
> - Help you understand any draft a lawyer prepares for you
>
> For the actual drafting, please work with a qualified lawyer.

**Pattern 4 — Out-of-jurisdiction:**

> I focus on Indian law. For US/UK/etc. law I'm not authoritative, and getting it slightly wrong would be worse than not answering. For patents I do cover international filings, but for general law I stay within Indian jurisdiction.

### 9.3 Avoiding refusal fatigue

If a user has triggered 3+ refusals in a session, the system softens its next refusal slightly and offers a more substantial alternative path:

> I notice we've had a few advice-shaped questions. The pattern I'm seeing is that you're trying to figure out [research_focus]. Let me try a different approach: would you like me to put together a structured overview of the law on [topic], the typical procedure, and the kinds of decisions a lawyer would help you make? That might be more useful than answering specific should-I questions piecemeal.

This pattern recognition is implicit, not explicit — the system doesn't say "you've been refused 3 times" but it does adapt.

---

## 10. Flow 8 — Saved Matters and Return Visits

For authenticated users with persistent state.

### 10.1 The Matters concept

A "Matter" is a named research session. It groups conversations and accumulated sources around a specific topic. A user might have:

- "Essar Steel post-2022 treatment"
- "138 case for ABC Pvt Ltd"
- "Solid-state battery prior art"

### 10.2 Creating a Matter

A user creates a Matter either:

- Explicitly: "New Matter" button → name → tags
- Implicitly: after their 3rd turn, the system asks: "Would you like to save this as a research matter?"

### 10.3 Matter dashboard

The sidebar shows a Matter list:

```
My matters
─────────────────────────
✦ Continue last: Essar Steel post-2022
─────────────────────────
🗂 Essar Steel post-2022          (2 days ago)
🗂 138 case for ABC Pvt Ltd       (5 days ago)
🗂 Solid-state battery PA          (2 weeks ago)
🗂 Untitled matter                 (1 month ago)

[+ New matter]
```

Clicking a matter:

- Opens its conversation
- Restores all accumulated sources in the side panel
- Restores any uploaded documents (if not expired)
- Resumes at the last turn

### 10.4 Matter actions

Per-matter actions:

- Rename
- Add tags
- Export all citations
- Export full transcript
- Archive (soft delete; recoverable for 30 days)
- Delete permanently (with confirmation)

### 10.5 Document lifecycle in Matters

Uploaded documents are scoped to the **session** by default. To persist a document beyond the session:

- The user clicks "Save document to this matter"
- The document is kept indefinitely (until manually deleted)
- The user-scoped Qdrant collection persists

If a user has no active Matter, documents auto-delete after 7 days.

### 10.6 Privacy and data lifecycle

Persistent data lifecycle:

| Asset | Default retention | User control |
|---|---|---|
| Conversation transcript | Indefinite for signed-in; 7 days for anonymous | User can delete a conversation or all conversations |
| Uploaded documents (session-scoped) | 7 days after upload | Delete immediately on demand |
| Uploaded documents (matter-scoped) | Indefinite | Delete immediately on demand |
| Accumulated sources (public corpus) | Re-retrievable always; not stored per-user | N/A |
| Audit log | 1 year | Not user-visible; available on data export request |

Users can request a full data export or full account deletion from their account settings. Account deletion triggers a 30-day soft-delete window, then permanent deletion.

---

## 11. Flow 9 — Error and Edge Case Flows

What happens when things go wrong.

### 11.1 LLM provider unavailable

When NIM returns 5xx or 429:

- First retry with exponential backoff (1s, 3s)
- If still failing, fallback to Ollama (local M1 model)
- If Ollama also fails, the system shows: "I'm having trouble connecting to my models. Please try again in a moment."
- The conversation state is preserved; the user can retry the turn

### 11.2 Retrieval returns nothing relevant

When the reranker's top score is below threshold and adaptive retry also fails:

- The system says: "I couldn't find authoritative sources for this question in my corpus. This could mean: (a) the question is outside my coverage (which currently includes Indian central statutes, SC and 5 HC judgments, and international patents); (b) you might want to rephrase the question; or (c) the question may require a more specialized resource. Would you like to try a different angle?"
- The conversation continues; no broken state

### 11.3 Structured output parse failure

When the generator produces invalid JSON for the structured answer:

- First retry with a stricter prompt
- On second failure: "I had trouble structuring my answer. Could you rephrase your question, or break it into a more specific sub-question?"
- The raw model output is logged (without PII) for debugging

### 11.4 Verifier flags claims as unsupported

When the citation verifier finds an unsupported claim:

- The claim is stripped from the answer before render
- A small inline notice appears: "Some content was removed because citation verification failed."
- The user can request the removed content with a follow-up; the system explains why it was removed and offers to re-research with different sources

### 11.5 Rate limit hit

When the user hits their per-hour rate limit:

- A modal: "You've reached the [N] queries/hour limit for [your tier]. The limit resets in [time]. [Sign in / upgrade] for higher limits."
- Anonymous users: prompted to sign in
- Public-tier users: prompted to verify as Professional (if applicable) for higher limits

### 11.6 Document upload failure

- File too large: clear error with size limit
- Unsupported type: clear error with supported types
- Parsing failure: "I couldn't parse this document. It may be corrupted or in an unusual format. Try saving it as a standard PDF or DOCX and uploading again."
- OCR failure on scanned: "I had trouble reading this scanned document. The text may be unclear. Try a sharper scan."

### 11.7 Session expiry mid-conversation

If a user's session expires while they're chatting:

- Their next message triggers a redirect to sign-in
- After sign-in, they land back in the conversation
- Conversation state is fully preserved

---

## 12. Cross-Flow UX Principles

A set of principles that apply across all flows.

### 12.1 Streaming over loading

Wherever possible, show progressive output rather than a loading spinner. Streaming the LLM response, streaming retrieval results, streaming document parsing progress — all improve perceived performance dramatically.

### 12.2 Citations are first-class UI

Citation pills are not afterthoughts. They are:

- Visually consistent across all generated content
- Always clickable (and keyboard-accessible)
- Color-coded by tier (Tier 1 primary, Tier 2 official, Tier 3 commentary, Tier 4 dimmed)
- Show source preview on hover for fast scanning

### 12.3 Mode is always visible

The current mode is shown in the header at all times. There is no "hidden state" — the user can always tell which mode they're in and switch with one click.

### 12.4 Refusals are never the end

A refusal always offers an alternative path forward. The user is never left at a dead-end. The single biggest UX failure of legal AI tools is brittle refusals that frustrate users; Themis Machina is built to avoid this.

### 12.5 Disclaimers are subtle but persistent

The "this is research, not advice" framing appears:

- In the welcome message
- In the chat footer (small, always-visible)
- At the end of procedural / advice-adjacent answers (in-line)
- In exported documents (header and footer)

The disclaimers don't dominate the UI, but they're never out of reach.

### 12.6 The user is in control

Everything stateful — conversations, matters, documents — is fully under user control. Delete, export, rename, archive. No dark patterns; no "we'd love to keep your data."

---

## 13. Mode-Specific Behavior Summary

| Feature | Public mode | Professional mode | Patent mode |
|---|---|---|---|
| Language | Plain | Legal terminology | IP-specific terminology |
| "Consult a lawyer" suggestion | Strong, frequent | Light or absent | "Consult a patent agent" instead |
| Citation format | Readable name + link | Indian standard format, paragraph numbers | Patent number + claim references |
| Refusals | Friendly, explanatory | Concise, professional | Specific to patent advice (no FTO, no patentability opinions) |
| Default corpora | Statutes, cases, official commentary | Statutes, cases, treatments, official sources | Patents, citations, academic prior art |
| Default UI density | Spacious | Compact | Compact + structured (tables, matrices) |
| Export formats | PDF, plain text | PDF, DOCX, Bluebook, OSCOLA, SCC | PDF, DOCX, JSON (structured prior-art) |

---

## 14. Flow Diagrams

The complete state machine of a single turn:

```
┌─────────────┐
│  User input │
└──────┬──────┘
       │
       ▼
┌─────────────────┐
│ Cookie/session  │  → if no session, create anonymous
│ resolution      │
└────────┬────────┘
         │
         ▼
┌────────────────┐
│ Rate-limit chk │  → if over limit, return 429
└────────┬───────┘
         │
         ▼
┌────────────────────┐
│ LangGraph turn     │
│  (full graph from  │
│   Section 3.3)     │
└────────┬───────────┘
         │
         ▼
┌────────────────────┐
│ Stream tokens to   │  (SSE)
│ client             │
└────────┬───────────┘
         │
         ▼
┌────────────────────┐
│ Verifier (parallel)│  → updates UI when done
└────────┬───────────┘
         │
         ▼
┌────────────────────┐
│ Persist state      │
└────────────────────┘
```

The mode switch flow:

```
User clicks mode selector
         │
         ▼
Confirm: "Switch to [new mode]?
         Your conversation will be preserved."
         │
         ▼
On confirm:
  - Update state.mode
  - Update UI affordances
  - Show transition message
  - Continue conversation
```

---

## 15. Open UX Questions

| # | Question | Resolution deadline |
|---|---|---|
| 1 | Should anonymous sessions auto-expire after N inactive days or be persistent indefinitely via cookie? | Phase 3 |
| 2 | Should mode auto-detect on first query (e.g., legal terminology → Professional) or always require explicit selection? | Phase 3 |
| 3 | Should the system support voice input in Phase A or defer to v1.1? | Phase 8 |
| 4 | Should clarifying questions appear inline in the chat or as a modal overlay? | Phase 3 |
| 5 | Should citation pills show source tier inline (color) or only on hover? | Phase 8 |
| 6 | Should the Matter sidebar be collapsible or always visible? | Phase 8 |
| 7 | Should document risk-flagging be opt-in or default-on for contracts? | Phase 6 |

---

## 16. Document History

| Version | Date | Author | Notes |
|---|---|---|---|
| 1.0 | [Date] | [You] | Approved baseline |

---

## 17. Related Documents

- **Document 1** — PRD
- **Document 2** — TRD
- **Document 3** — AI/ML System Design
- **Document 5** — UI/UX Design (the visual rendering of these flows)
- **Document 6** — Evaluation Plan (validates flow quality)
- **Document 7** — Safety & Responsible AI (refusal flow rules)
- **Document 10** — Security & Privacy (per-user isolation in document flow)

— end of Document 4 —
