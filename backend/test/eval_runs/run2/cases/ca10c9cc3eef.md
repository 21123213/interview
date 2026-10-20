# Case `ca10c9cc3eef`

- index: 188
- file_key: `Model%20NDA%20(recommended%20by%20SWA).txt`
- file_id: 154
- file_mapped: True
- correct: **True**
- error_type: `none`
- latency_ms: 21553.18

## Query

Consider SWA's Non-Disclosure Agreement; Does the document require the Receiving Party to notify the Disclosing Party if they are required by law, regulation, or judicial process to disclose any Confidential Information?

## Gold

2. Notwithstanding any other provision of this Agreement, the Parties acknowledge that Confidential information shall not include any information that:
c) Is required to be disclosed under any relevant law, regulation or order of court, provided the affected Party is given prompt notice of such requirement or such order and (where possible) and provided the opportunity to contest it as per applicable law, and the scope of such disclosure is limited to the extent possible

## RAG Answer

Yes, effectively. Under Clause 2(c) of the SWA Model NDA, information that is required to be disclosed under a relevant law, regulation, or court order is excluded from “Confidential Information” only if the affected Party is given **prompt notice** of that requirement or order and, where possible, an opportunity to contest it under applicable law, with the disclosure limited as far as possible.

So, if the Receiving Party is compelled by law, regulation, or judicial process to disclose Confidential Information, the document requires prompt notice to the affected Party—typically the Disclosing Party—before/when making such disclosure.

## Judge

- correct: True
- error_type: none
- gold_summary: 若信息因法律、法规或法院命令必须披露，则不属于保密信息，但前提是受影响方获得及时通知，并在可能情况下有机会依法抗辩，且披露范围尽可能受限。
- answer_summary: 系统回答指出根据 Clause 2(c)，因法律、法规或法院命令必须披露的信息只有在受影响方获得 prompt notice、有机会 contest、并限制披露范围时才被排除；并进一步说明接收方被迫披露时需通知受影响方，通常是披露方。
- gap: 无
- reason: 系统回答覆盖了金标关键要点：法定/监管/法院命令强制披露、及时通知受影响方、可能情况下抗辩机会、披露范围受限，并回答了是否需要通知披露方，未与金标矛盾。
