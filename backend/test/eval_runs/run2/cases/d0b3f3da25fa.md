# Case `d0b3f3da25fa`

- index: 121
- file_key: `LiiON%20NDA%202-27-2015%20v1.0.txt`
- file_id: 151
- file_mapped: True
- correct: **True**
- error_type: `none`
- latency_ms: 14860.43

## Query

Consider LiiON's Non-Disclosure Agreement; Does the document permit the Receiving Party to create a copy of some Confidential Information under certain circumstances?

## Gold

Receiving Party shall not alter or remove any confidentiality or proprietary marking on the Confidential Information and, subject to the forego-ing, may make such limited number of copies of Disclosing Party's Confidential Information to the extent necessary to achieve the Purpose.

## RAG Answer

Yes. The LiiON Non-Disclosure Agreement permits the Receiving Party to make a limited number of copies of the Disclosing Party’s Confidential Information to the extent necessary to achieve the Purpose, provided it does not alter or remove any confidentiality or proprietary markings. It also allows the Receiving Party to retain one copy in a confidential file for archival purposes.

## Judge

- correct: True
- error_type: none
- gold_summary: 接收方不得更改或移除机密信息上的保密/专有标记；在此前提下，可以为实现目的所需制作有限数量的机密信息副本。
- answer_summary: 系统回答称允许接收方为实现目的所需制作有限数量的机密信息副本，前提是不更改或移除保密/专有标记。
- gap: 无
- reason: 系统回答覆盖了金标的关键结论：允许在特定情况下制作有限数量的机密信息副本，并包含不得更改或移除保密/专有标记这一前提。额外提到的存档保留副本虽未在标准答案中出现，但不影响关键点命中。
