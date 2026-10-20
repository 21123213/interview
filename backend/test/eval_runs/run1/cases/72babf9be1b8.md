# Case `72babf9be1b8`

- index: 96
- file_key: `FNHA-2019RFP-02-NDA-form.txt`
- file_id: 133
- file_mapped: True
- correct: **True**
- error_type: `none`
- latency_ms: 21327.74

## Query

Consider FNHA's Non-Disclosure Agreement; Does the document allow the Receiving Party to share some Confidential Information with third parties, including consultants, agents, and professional advisors?

## Gold

2. Non-Disclosure. Company will not make copies of, disclose, discuss, publish or disseminate Confidential Information any third person or entity.

## RAG Answer

No. The document does not give the Receiving Party a general right to share Confidential Information with third parties such as consultants, agents, or professional advisors.

It prohibits disclosure to “any third person or entity,” except that it does not preclude discussions with FNHA staff or with “any other persons identified by FNHA as having undertaken this Agreement,” or with other persons if “expressly permitted by staff of FNHA” and conducted on FNHA’s directed terms.

## Judge

- correct: True
- error_type: none
- gold_summary: Non-Disclosure条款规定接收方/公司不得向任何第三方人员或实体披露、讨论、发布或传播机密信息。
- answer_summary: 系统回答称文档不赋予接收方与顾问、代理、专业顾问等第三方分享机密信息的一般权利，并指出禁止向任何第三方披露，仅存在与FNHA人员或经FNHA明确许可的有限例外。
- gap: 无
- reason: 系统回答覆盖了金标的关键结论，即文档不允许接收方向第三方披露机密信息；其补充的例外说明不影响对核心要点的命中。
