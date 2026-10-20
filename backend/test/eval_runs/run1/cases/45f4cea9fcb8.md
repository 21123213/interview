# Case `45f4cea9fcb8`

- index: 45
- file_key: `EFCAConfidentialityAgreement.txt`
- file_id: 126
- file_mapped: True
- correct: **True**
- error_type: `none`
- latency_ms: 13360.69

## Query

Consider EFCA's Non-Disclosure Agreement; Does the document allow the Receiving Party to share some Confidential Information with their employees?

## Gold

EFCA shall ensure that disclosure of such Confidential Information is restricted to those employees or directors of EFCA and EFCA’s principals having the need to know the same.

## RAG Answer

Yes. Under Clause 2, EFCA may disclose Confidential Information only to employees or directors of EFCA and EFCA’s principals who have a need to know it, and copies may be made only to the extent reasonably necessary.

## Judge

- correct: True
- error_type: none
- gold_summary: 保密信息的披露必须限制在 EFCA 及其 principals 中确有知悉需要的员工或董事范围内。
- answer_summary: 系统回答称 EFCA 可以仅向确有知悉需要的员工或董事（包括 EFCA 及其 principals）披露保密信息，并补充了复制限制。
- gap: 无
- reason: 系统回答已覆盖金标的关键要点，即披露需限制在 EFCA 及其 principals 中有需要知悉的员工或董事范围内；额外说明不影响命中。
