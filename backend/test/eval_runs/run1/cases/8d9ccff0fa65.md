# Case `8d9ccff0fa65`

- index: 90
- file_key: `ExcelerateStandardNDAFormat.txt`
- file_id: 132
- file_mapped: True
- correct: **True**
- error_type: `none`
- latency_ms: 16403.15

## Query

Consider Excelerate's Non-Disclosure Agreement; Does the document restrict the use of Confidential Information to the purposes stated in the Agreement?

## Gold

4. Except as provided in Paragraphs 6 and 7 hereof, Proprietary Information disclosed to a receiving Party shall for a period of three (3) years from the effective date of this Agreement be held in confidence by the receiving Party and not be disclosed to others or used except for the purposes set forth above, without the prior written approval of the disclosing Party.
This Agreement may not be modified in any manner except by written amendment executed by both Parties.

## RAG Answer

Yes. Under Paragraph 4 of the Excelerate NDA, Proprietary Information “shall not be disclosed to others or used except for the purposes set forth above,” subject to the exceptions in Paragraphs 6 and 7 and prior written approval of the disclosing party.

## Judge

- correct: True
- error_type: none
- gold_summary: 金标表明，除第6和第7段规定外，接收方对专有信息应保密，且不得向他人披露或用于协议所述目的以外，除非获得披露方事先书面同意。
- answer_summary: 系统回答称根据第4段，专有信息不得向他人披露或用于上述目的以外，并指出受第6、7段例外及披露方事先书面批准限制。
- gap: 未提及金标中的三年保密期限及协议修改条款，但这些不是回答该问题所需的关键点。
- reason: 系统回答准确覆盖了金标关于信息只能用于协议所述目的的核心限制，因此判定命中。
