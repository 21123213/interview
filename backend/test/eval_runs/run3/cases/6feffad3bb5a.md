# Case `6feffad3bb5a`

- index: 130
- file_key: `Standard%20NDA%20by%20Axial.txt`
- file_id: 189
- file_mapped: True
- correct: **True**
- error_type: `none`
- latency_ms: 19229.05

## Query

Consider Axial's Non-Disclosure Agreement; Does the document mention that some obligations of the Agreement may survive the termination of the Agreement?

## Gold

Notwithstanding anything to the contrary herein, each Party's rights and obligations under this Agreement, irrespective of termination of this Agreement, shall survive until the 18 month anniversary of this Agreement, even after the return or destruction of Confidential Information by the Recipient (the "Confidential Period"), provided that for any and all trade secrets of the Disclosing Party, the Confidential Period shall last for as long as such Confidential Information qualifies as a trade secret under applicable federal, state and/or local law.

## RAG Answer

Yes. Axial’s NDA expressly states that certain rights and obligations survive termination.

- **Section 6 (Term and Termination)** says that, notwithstanding anything to the contrary, each Party’s rights and obligations under the Agreement “shall survive until the 18 month anniversary of this Agreement,” even after the return or destruction of Confidential Information. For trade secrets, the confidentiality period continues for as long as the information qualifies as a trade secret under applicable law.

- **Section 10 (Non-Solicitation and Non-Circumvention)** also imposes obligations that survive termination, applying for **12 months after expiration or termination** of the Agreement.

## Judge

- correct: True
- error_type: none
- gold_summary: Axial NDA规定各方的权利和义务不因协议终止而立即结束，而是存续至协议18个月周年日，即使机密信息已归还或销毁；对于商业秘密，保密义务持续至其仍构成法律意义上的商业秘密。
- answer_summary: 系统回答确认NDA规定某些权利义务在终止后存续，并准确提到18个月存续期、即使归还或销毁机密信息仍适用，以及商业秘密持续受保护；另外补充了Section 10的12个月非招揽/规避义务。
- gap: 无
- reason: 系统回答覆盖了金标中的关键信息：协议终止后权利义务仍存续、18个月期限、归还/销毁机密信息不影响、商业秘密例外存续。额外内容不影响命中判定。
