# Case `2ee7307babbf`

- index: 152
- file_key: `TSE-TSE-OK-WHK-Mutual-NDA-Fill-in-Blanks-4-29-2019.txt`
- file_id: 196
- file_mapped: True
- correct: **True**
- error_type: `none`
- latency_ms: 17424.65

## Query

Consider the Mutual Non-Disclosure Agreement between TSE, OK, and WHK; Does the document mention whether or not the Receiving Party is allowed to reverse engineer any objects which embody the Disclosing Party's Confidential Information?

## Gold

Neither party shall attempt to reverse engineer, analyze or disassemble, or cause to be reverse engineered, analyzed or disassembled any product, formulation, process technology, sample or other technology provided by the other party, either directly or indirectly.

## RAG Answer

Yes. The document expressly addresses reverse engineering in Section 4 (“Reverse Engineering”).

It states that **neither party** may attempt to reverse engineer, analyze, or disassemble—nor cause to be reverse engineered, analyzed, or disassembled—any **product, formulation, process technology, sample, or other technology** provided by the other party, either directly or indirectly.

Therefore, under this Mutual NDA, the Receiving Party is **not allowed** to reverse engineer objects or technology embodying the Disclosing Party’s Confidential Information.

## Judge

- correct: True
- error_type: none
- gold_summary: 金标规定任何一方不得直接或间接对对方提供的产品、配方、工艺技术、样品或其他技术进行逆向工程、分析或拆解，也不得导致他人进行上述行为。
- answer_summary: 系统回答指出文档明确涉及逆向工程，并说明任何一方不得对对方提供的产品、配方、工艺技术、样品或其他技术进行逆向工程、分析或拆解，也不得导致他人进行上述行为；同时明确接收方不允许逆向工程体现披露方机密信息的对象或技术。
- gap: 无
- reason: 系统回答完整覆盖了金标关于禁止逆向工程、分析、拆解及其间接责任的关键要点，并基于此正确回答了用户问题；额外提及章节编号不影响命中判定。
