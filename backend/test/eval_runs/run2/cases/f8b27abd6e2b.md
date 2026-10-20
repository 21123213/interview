# Case `f8b27abd6e2b`

- index: 331
- file_key: `nda_gtl_inria.txt`
- file_id: 160
- file_mapped: True
- correct: **True**
- error_type: `none`
- latency_ms: 11376.02

## Query

Consider the Non-Disclosure Agreement between GTL and Inria; Does the document mention that some obligations of the Agreement may survive the termination of the Agreement?

## Gold

The obligation of confidentiality will remain until the GTL data are released to public or have fallen into public domain.

## RAG Answer

Yes. The document states that upon expiration or termination of the Agreement, the user must cease using all GTL Data and return or destroy all originals and copies, with certification. It also states that the obligation of confidentiality will remain until the GTL Data are released to the public or fall into the public domain.

## Judge

- correct: True
- error_type: none
- gold_summary: 协议终止后保密义务仍持续，直到GTL数据公开或进入公共领域。
- answer_summary: 系统回答确认存在存续义务，并指出保密义务将持续至GTL数据公开或进入公共领域。
- gap: 无
- reason: 系统回答覆盖了金标关键信息，即保密义务在数据公开前持续；额外扩写不影响判定。
