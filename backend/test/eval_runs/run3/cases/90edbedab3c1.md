# Case `90edbedab3c1`

- index: 54
- file_key: `QuickBooks-NDA-template.txt`
- file_id: 180
- file_mapped: True
- correct: **True**
- error_type: `none`
- latency_ms: 12683.62

## Query

Consider QuickBooks's Non-Disclosure Agreement; Does the document mention that some obligations of the Agreement may survive the termination of the Agreement?

## Gold

This Agreement may be terminated at all times with a 30 daysʼ prior written notice provided, however, that the confidentiality obligations herein shall terminate ____________ years following the date of termination of this Agreement.

## RAG Answer

Yes. The QuickBooks NDA template addresses survival of obligations in Section 8 (“Term”). It states that although the Agreement may be terminated with 30 days’ prior written notice, the confidentiality obligations “shall terminate ____ years following the date of termination of this Agreement.” This means the confidentiality obligations continue for a specified period after termination, even though the exact number of years is left blank.

## Judge

- correct: True
- error_type: none
- gold_summary: 协议可提前30天书面通知终止，但保密义务在协议终止后仍存续一定年限。
- answer_summary: 系统回答指出 QuickBooks NDA 提到协议可提前30天书面通知终止，并且保密义务在终止后一定年限才终止，因此义务会在协议终止后继续存在。
- gap: 无
- reason: 系统回答覆盖了金标的关键信息，即终止通知期以及保密义务在终止后存续一定年限；额外提及条款编号不影响命中判定。
