# Case `81cabecd10fe`

- index: 295
- file_key: `NDA-Seeed.txt`
- file_id: 171
- file_mapped: True
- correct: **True**
- error_type: `none`
- latency_ms: 17531.37

## Query

Consider Seeed's Non-Disclosure Agreement; Does the document allow the Receiving Party to share some Confidential Information with their employees?

## Gold

The Parties hereby agree that they shall not use, commercialize or disclose any Confidential Information to any person or entity, except to their own employees having a “need to know” (and who themselves bound by similar non-disclosure restrictions), and to such other recipients as each Party may approve in writing, provided that such recipients shall have first executed a Confidentiality Agreement in a form acceptable to the Party interested.
The Receiving Party shall use its best efforts to limit dissemination of Disclosing Party’s “Confidential Information” to such of its employees or sub-contractor(s) who have a need to know for the aforesaid evaluation and/or development purposes.

## RAG Answer

Yes. Under the NDA, the Receiving Party may share Confidential Information with its own employees who have a “need to know,” provided those employees are bound by similar non-disclosure restrictions. The Receiving Party is also expected to use best efforts to limit dissemination to employees or subcontractors who need the information for the relevant evaluation/development purposes.

## Judge

- correct: True
- error_type: none
- gold_summary: NDA允许接收方将保密信息分享给有“need to know”的自身员工，且这些员工须受类似保密限制约束；接收方应尽力限制披露范围，仅向需要用于评估/开发目的的员工或分包商披露。
- answer_summary: 系统回答称允许，接收方可向有“need to know”的自身员工分享保密信息，前提是员工受类似保密限制约束，并提到应尽力限制向员工或分包商披露用于相关评估/开发目的。
- gap: 无
- reason: 系统回答覆盖了金标关于允许与有“need to know”的自身员工分享保密信息、员工需受类似保密限制、以及限制披露范围等关键要点，虽未展开“经书面批准的其他接收方”条款，但不影响对员工分享问题的命中。
