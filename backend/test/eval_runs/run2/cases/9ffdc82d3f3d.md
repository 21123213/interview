# Case `9ffdc82d3f3d`

- index: 162
- file_key: `lti-two-way-cda-template.txt`
- file_id: 152
- file_mapped: True
- correct: **True**
- error_type: `none`
- latency_ms: 44692.65

## Query

Consider LTI's Two-Way Confidential Disclosure Agreement; Does the document mention that some obligations of the Agreement may survive the termination of the Agreement?

## Gold

7) Notwithstanding the termination or expiration of any other agreement executed in conjunction with this Agreement, the obligations of the Parties with respect to Proprietary Information shall continue to be governed by this Non-Disclosure Agreement.

## RAG Answer

Yes, but with a nuance.

The document states that the parties’ obligations with respect to Proprietary Information continue to be governed by the Non-Disclosure Agreement notwithstanding the termination or expiration of **any other agreement executed in conjunction with this Agreement**:

> “Notwithstanding the termination or expiration of any other agreement executed in conjunction with this Agreement, the obligations of the Parties with respect to Proprietary Information shall continue to be governed by this Non-Disclosure Agreement.”

It also states that confidentiality and non-use obligations remain in effect for five years from the effective date:

> “Receiving Party’s confidentiality and non-use obligations under this Non-Disclosure Agreement will be in effect for a period of five (5) years, starting on the effective date.”

So the document supports survival of Proprietary Information obligations, but the express survival language refers to termination of another related agreement, not necessarily a general survival clause for termination of the NDA itself.

## Judge

- correct: True
- error_type: none
- gold_summary: 文档规定，即使与本协议一起签署的其他协议终止或到期，双方关于专有信息的义务仍继续受本保密协议约束。
- answer_summary: 系统回答确认文档包含相关存续条款，并引用金标原文，说明专有信息义务在其他相关协议终止或到期后仍继续受保密协议约束；同时补充说明该表述更偏向其他相关协议终止后的存续，而非保密协议自身终止的一般存续条款。
- gap: 无
- reason: 系统回答完整覆盖了金标关键信息，即专有信息义务在相关协议终止或到期后继续受保密协议约束，并准确引用了金标内容；额外解释与补充不构成矛盾。
