# Case `7b9dcfd0e9f8`

- index: 83
- file_key: `JBF_NDA_rev-2017033-1.txt`
- file_id: 146
- file_mapped: True
- correct: **True**
- error_type: `none`
- latency_ms: 22468.66

## Query

Consider JBF's Non-Disclosure Agreement; Does the document require the Receiving Party to notify the Disclosing Party if they are required by law, regulation, or judicial process to disclose any Confidential Information?

## Gold

5. In the event that the Receiving Party is required to disclose Confidential Information pursuant to any applicable law or an order from a court of competent jurisdiction, the Receiving Party shall only disclose such portion of the Confidential Information that it is legally required to disclose, and shall use all reasonable efforts to obtain confidential treatment for any Confidential Information so disclosed. The Receiving Party shall promptly notify the Disclosing Party of the required disclosure and any relevant information in respect thereto so that the Disclosing Party may take appropriate steps to protect such Confidential Information from such disclosure.

## RAG Answer

Yes. Under Section 5 of JBF’s NDA, if the Receiving Party is required to disclose Confidential Information pursuant to applicable law or an order from a court of competent jurisdiction, the Receiving Party must promptly notify the Disclosing Party of the required disclosure and provide relevant information so the Disclosing Party can take protective steps. The document specifically mentions law and court order; “regulation” is not expressly stated, but judicial process is covered by the court-order requirement.

## Judge

- correct: True
- error_type: none
- gold_summary: 金标规定：若接收方依据适用法律或有管辖权法院命令被要求披露保密信息，接收方应及时通知披露方并提供相关信息，以便披露方采取保护措施。
- answer_summary: 系统回答指出根据第5条，接收方因适用法律或法院命令被要求披露时，必须及时通知披露方并提供相关信息以便保护；并补充说明法规未明确提及，但司法程序可由法院命令覆盖。
- gap: 无
- reason: 系统回答已覆盖金标关键要点：接收方在依法或依法院命令必须披露保密信息时，应及时通知披露方。其关于‘regulation’未明确说明的补充不构成与金标矛盾，也不影响对金标核心结论的命中。
