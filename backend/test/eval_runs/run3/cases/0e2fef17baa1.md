# Case `0e2fef17baa1`

- index: 117
- file_key: `Sony%20Pictures%20Television%20NDA%20(Executed).txt`
- file_id: 188
- file_mapped: True
- correct: **True**
- error_type: `none`
- latency_ms: 20908.43

## Query

Consider Sony Pictures Television's Non-Disclosure Agreement; Does the document allow the Receiving Party to independently develop information that is similar to the Confidential Information?

## Gold

Notwithstanding any other provision of this Agreement, "Confidential Information" does not include information which:
(c) is or was developed independently by or for the Receiving Party, without use of or reference to any Confidential Information of the Disclosing Party and without violation of any obligation contained herein.
Each Disclosing Party understands and agrees that (x) the Receiving Party and its affiliates and their respective Representatives is currently or may become engaged in lines of business the same as or similar to those of the Disclosing Party and that, wholly independent of the information provided hereunder, the Receiving Party and its affiliates and their respective Representatives may currently or in the future be developing internally, or receiving from third parties, information that coincidentally may be similar to portions of the information provided hereunder and/or otherwise competitive with the Disclosing Party's actual or future projects or business, and (y) wholly independent development by the Receiving Party and its affiliates and their respective Representatives of media content, products, programs, services, goods, concepts, opportunities, documents or information that are coincidentally similar to (but not, in whole or part, based upon) any information provided hereunder will not be deemed to violate this Agreement. For the avoidance of doubt, nothing in this Section 8 is intended to relieve either party from any of its obligations of confidentiality contained in this Agreement.

## RAG Answer

Yes. The NDA allows independent development of similar information, provided it is developed wholly independently and is not based upon the Confidential Information.

- **Section 8 (Concurrent/Future Development)** states that wholly independent development by the Receiving Party, its affiliates, and their Representatives of content, products, programs, services, goods, concepts, opportunities, documents, or information that are coincidentally similar to—but not based upon—information provided under the Agreement will not violate the NDA.
- **Section 2(c)** also excludes from “Confidential Information” any information developed independently by or for the Receiving Party without use of or reference to the Disclosing Party’s Confidential Information and without violating the Agreement.

However, the Receiving Party must still comply with its confidentiality obligations; the allowance applies only to genuinely independent development, not to use or derivation of Confidential Information.

## Judge

- correct: True
- error_type: none
- gold_summary: NDA明确将独立开发且不基于、不参考保密信息的信息排除在保密信息之外；同时约定接收方完全独立开发的内容即使偶然相似也不构成违约，但保密义务仍适用。
- answer_summary: 系统回答指出NDA允许接收方完全独立开发与保密信息偶然相似的信息，只要不基于或参考保密信息；并引用了独立开发排除条款和Section 8，同时强调保密义务仍须遵守。
- gap: 无
- reason: 系统回答覆盖了金标的关键要点：独立开发信息不属于保密信息、偶然相似但不基于保密信息的开发不违反协议、以及保密义务仍保留。虽然措辞和结构不同，但核心结论一致。
