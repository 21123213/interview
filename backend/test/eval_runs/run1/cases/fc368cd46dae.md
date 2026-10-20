# Case `fc368cd46dae`

- index: 127
- file_key: `eulerhermes-nda.txt`
- file_id: 130
- file_mapped: True
- correct: **True**
- error_type: `none`
- latency_ms: 35482.6

## Query

Consider Euler Hermes's Non-Disclosure Agreement; Does the document allow the Receiving Party to share some Confidential Information with third parties, including consultants, agents, and professional advisors?

## Gold

WHEREAS “Affiliates” shall mean any person or entity directly or indirectly controlling, controlled by, or under common control with Euler Hermes, where control means the legal power to direct or cause the direction of the general management of the company, partnership, or other legal entity; and
1. Euler Hermes shall keep the Confidential Information confidential and may disclose the Confidential Information only to its Affiliates, employees, contractors, or consultants for the Purpose described above and no other purpose.

## RAG Answer

Yes, but only in a limited way.

Under Paragraph 1 of the Euler Hermes NDA, Euler Hermes may disclose Confidential Information only to its **Affiliates, employees, contractors, or consultants**, and only for the purposes stated in the Agreement. It may not disclose the information to any other firm or individual except as authorized in Paragraph 1.

The document expressly allows sharing with **consultants**, but it does **not expressly list “agents” or “professional advisors.”** Therefore, disclosure to agents or professional advisors would generally not be permitted unless they fall within the authorized categories, such as contractors or consultants, and the disclosure is for the permitted purpose. Euler Hermes must also instruct those recipients to keep the information confidential and remains liable for any breach by them.

## Judge

- correct: True
- error_type: none
- gold_summary: 金标规定保密信息仅可披露给 Euler Hermes 的 Affiliates、employees、contractors 或 consultants，且仅限约定目的。
- answer_summary: 系统回答指出 NDA 仅允许向 Affiliates、employees、contractors 或 consultants 披露，且仅限约定目的；明确包含 consultants，并说明 agents 和 professional advisors 未被明确列入，除非属于允许类别。
- gap: 无
- reason: 系统回答覆盖了金标的关键限制：可披露对象仅限 Affiliates、employees、contractors、consultants，且仅限目的；对 consultants 允许、对 agents/professional advisors 未明确允许的判断也与金标一致。
