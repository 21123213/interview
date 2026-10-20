# Case `ecf4caf2afd7`

- index: 212
- file_key: `NCDG_Non-disclosure-agreement.txt`
- file_id: 157
- file_mapped: True
- correct: **True**
- error_type: `none`
- latency_ms: 15685.28

## Query

Consider NCDG's Non-Disclosure Agreement; Does the document allow the Receiving Party to independently develop information that is similar to the Confidential Information?

## Gold

e) Such Confidential Information shall not include any information which:is, at the time of disclosure, publicly known; or
i) the Receiving Party can demonstrate to the satisfaction of the Disclosing Party, has been developed independently of its obligations under this Agreement and without access to the Confidential Information.

## RAG Answer

Yes, but only if the Receiving Party can demonstrate that the information was developed independently of its obligations under the NDA and without access to the Confidential Information.

Under the definition of Confidential Information in the NCDG Non-Disclosure Agreement, Confidential Information does not include information that:

> “the Receiving Party can demonstrate to the satisfaction of the Disclosing Party, has been developed independently of its obligations under this Agreement and without access to the Confidential Information.”

Therefore, the Receiving Party may independently develop information similar to Confidential Information, provided it did not use or access the Confidential Information and can satisfy the Disclosing Party of the independent development.

## Judge

- correct: True
- error_type: none
- gold_summary: 机密信息不包括接收方能证明系独立于协议义务且未接触机密信息而开发的信息。
- answer_summary: 回答指出允许接收方独立开发类似机密信息，但前提是其能证明该信息是在未接触机密信息且独立于协议义务下开发，并引用了相同关键条款。
- gap: 无
- reason: 系统回答覆盖了金标关键要点：独立开发、未接触机密信息、可证明/满足披露方；与金标一致，未出现矛盾。
