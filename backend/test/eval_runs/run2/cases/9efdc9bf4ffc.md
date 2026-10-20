# Case `9efdc9bf4ffc`

- index: 235
- file_key: `NDA-Artop-Inno-2017.txt`
- file_id: 163
- file_mapped: True
- correct: **True**
- error_type: `none`
- latency_ms: 17502.11

## Query

Consider the Non-Disclosure Agreement between Artop and Inno; Does the document allow the Receiving Party to acquire information similar to the Confidential Information from a third party?

## Gold

The following items are not covered by the concept of this Confidential Information:
(iii) Information that the Recipient has obtained from a third party without any obligation to keep the information secret.

## RAG Answer

Yes, but only in a limited sense.

The NDA excludes from “Confidential Information” information that the Recipient “has obtained from a third party without any obligation to keep the information secret.” Therefore, if the Receiving Party acquires similar information from a third party and that third-party information was not subject to a confidentiality obligation, it would not be treated as Confidential Information under the agreement.

However, this does not permit the Receiving Party to disclose, use, or copy the actual Confidential Information received from the other party without written consent.

## Judge

- correct: True
- error_type: none
- gold_summary: 接收方从第三方获得的、且不负有保密义务的信息不属于保密信息。
- answer_summary: 系统回答指出 NDA 排除接收方从第三方获得的、无保密义务的信息，并说明此类信息不被视为 Confidential Information。
- gap: 无
- reason: 系统回答覆盖了金标关键信息，即第三方获得且无保密义务的信息不属于保密信息；虽然回答有额外限制说明，但与金标不矛盾且关键点已命中。
