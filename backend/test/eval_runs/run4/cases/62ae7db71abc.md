# Case `62ae7db71abc`

- index: 218
- file_key: `NDA_Street_Stream_Franchise.txt`
- file_id: 162
- file_mapped: True
- correct: **True**
- error_type: `none`
- latency_ms: 14760.38

## Query

Consider Street Stream's Non-Disclosure Agreement; Does the document require the Receiving Party to notify the Disclosing Party if they are required by law, regulation, or judicial process to disclose any Confidential Information?

## Gold

The Recipient shall not be in breach of its obligations under this Agreement to the extent that any Confidential Information received by it may be required by law or regulation having force of law; or the rules of any court or other body of competent jurisdiction; or any governmental body to be disclosed, provided in each case the Recipient, to the extent permitted by the foregoing requirement, immediately notifies the Disclosers in writing of any request or requirement for disclosure and of all relevant surrounding circumstances prior to disclosure and takes into account any representations made by the Disclosers in relation to the disclosure.

## RAG Answer

Yes. Under clause 4.2 of Street Stream’s Non-Disclosure Agreement, if the Receiving Party is required by law, regulation, court rules, or a competent governmental/judicial body to disclose Confidential Information, it must, to the extent permitted, immediately notify the Disclosing Party in writing of the disclosure request and all relevant surrounding circumstances before disclosure, and must also use its best endeavours to resist the disclosure and assist the Disclosing Party in resisting it.

## Judge

- correct: True
- error_type: none
- gold_summary: 若接收方依法、法规、法院规则或有权机关要求必须披露保密信息，只要其在允许范围内立即以书面形式通知披露方披露要求及相关情况，并在披露前考虑披露方的相关陈述，则不构成违约。
- answer_summary: 系统回答指出：在依法、法规、法院规则或有权机关要求披露时，接收方须在允许范围内立即书面通知披露方披露请求及相关情况，且需在披露前通知。
- gap: 无
- reason: 系统回答覆盖了金标的关键要点：存在法定/监管/司法披露要求时，接收方需在允许范围内立即书面通知披露方，并在披露前告知相关请求与情况；额外扩写不影响命中。
