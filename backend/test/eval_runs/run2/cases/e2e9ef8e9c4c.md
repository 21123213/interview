# Case `e2e9ef8e9c4c`

- index: 48
- file_key: `IPTK-CO-MutualNon-DisclosureAgreement.txt`
- file_id: 145
- file_mapped: True
- correct: **True**
- error_type: `none`
- latency_ms: 19586.73

## Query

Consider the Mutual Non-Disclosure Agreement between IPTK and CO; Does the document require the Receiving Party to notify the Disclosing Party if they are required by law, regulation, or judicial process to disclose any Confidential Information?

## Gold

If the Recipient is required by order of any court or other government or regulatory agency to disclose any Confidential Information belonging to any Dis-closer, it shall provide all Parties with prompt written notice within 3 business days of any such requirement so that the Parties whose Confidential Information is at risk may seek a protective order or take other appropriate action.

## RAG Answer

Yes. Under Section 5 (“Exception”) of the Mutual Non-Disclosure Agreement, if the Recipient is required by order of any court or other government or regulatory agency to disclose Confidential Information belonging to a Discloser, the Recipient must provide all Parties with prompt written notice within 3 business days of such requirement. This allows the affected Discloser to seek a protective order or take other appropriate action.

## Judge

- correct: True
- error_type: none
- gold_summary: 若接收方因法院或政府/监管机构命令被要求披露保密信息，须在3个工作日内向所有方提供及时书面通知，以便相关方寻求保护令或采取其他适当行动。
- answer_summary: 系统回答确认存在该义务，并说明接收方须在3个工作日内提供及时书面通知，以便受影响披露方寻求保护令或采取其他适当行动。
- gap: 无
- reason: 系统回答覆盖了金标的关键信息：法律/监管/司法要求触发通知义务、3个工作日内书面通知、以及通知目的为寻求保护令或采取其他行动，未出现矛盾或遗漏。
