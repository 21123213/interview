# Case `b7becdc9a57a`

- index: 166
- file_key: `lti-two-way-cda-template.txt`
- file_id: 152
- file_mapped: True
- correct: **True**
- error_type: `none`
- latency_ms: 24593.58

## Query

Consider LTI's Two-Way Confidential Disclosure Agreement; Does the document allow the Receiving Party to share some Confidential Information with third parties, including consultants, agents, and professional advisors?

## Gold

3) Each Party covenants and agrees that it will, during the term of this Non-Disclosure Agreement, keep in confidence, and prevent the disclosure of Proprietary Information to any third party other than those of receiving Party’s (i) employees, agents, representatives, directors or officers (collectively, “Representatives”) who need to know such Proprietary Information for the Purpose.

## RAG Answer

Yes, but only to a limited extent.

Under Section 3 of the LTI two-way Non-Disclosure Agreement, the Receiving Party may disclose Proprietary Information to its own **employees, agents, representatives, directors, or officers** — collectively defined as “Representatives” — but only if those persons **need to know** the information for the stated business Purpose. The Receiving Party is responsible for any breach by its Representatives.

The agreement does **not expressly list “consultants” or “professional advisors.”** They may be covered only if they qualify as the Receiving Party’s **agents or representatives** and satisfy the need-to-know requirement. Otherwise, disclosure to third parties is generally prohibited unless it falls within an exception, such as disclosure with the other Party’s written approval or as required by law.

## Judge

- correct: True
- error_type: none
- gold_summary: 接收方可向第三方披露保密信息的例外仅限其员工、代理、代表、董事或高管（统称“Representatives”），且必须是因约定目的而需要知悉该信息的人。
- answer_summary: 系统回答指出根据 Section 3，接收方可向自己的 employees、agents、representatives、directors、officers（即 Representatives）披露，但仅限 need to know；并说明 consultants/professional advisors 未被明确列出，可能仅在构成 agents/representatives 时才可覆盖。
- gap: 无
- reason: 系统回答已覆盖金标的关键要点：允许披露的对象限于接收方的员工、代理、代表、董事或高管，且需满足 need-to-know 要求。虽然问题提到 consultants 和 professional advisors，金标本身未明确包含这些类别，系统回答对此做了限定性说明，不与金标矛盾。
