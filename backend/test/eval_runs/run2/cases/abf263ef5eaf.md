# Case `abf263ef5eaf`

- index: 341
- file_key: `New_York_City_Bar_Association_Model_Form_of_Non-Disclosure_Agreement_2015.txt`
- file_id: 174
- file_mapped: True
- correct: **True**
- error_type: `none`
- latency_ms: 27952.88

## Query

Consider New York City Bar Association's Non-Disclosure Agreement; Does the document include a clause that prohibits the Receiving Party from soliciting some of the Disclosing Party's representatives?

## Gold

Buyer agrees that, except with the prior written consent of the Company, it will not, and it will not permit any of its controlled Affiliates to, directly or indirectly, solicit for employment or hire any [employees/officers/senior management of the Company [first introduced to Buyer or any of its controlled Affiliates in connection with the evaluation of the Transaction][that first become known to Buyer or any of its controlled Affiliates in connection with Buyer’s evaluation of the Transaction][listed on Exhibit A]] for a period of [___] year[s] after the date of this Agreement; provided that this Section 7 shall not restrict Buyer or any of its controlled Affiliates from (i) making any general solicitation for employment that is not specifically directed at any such Persons, including through use of a recruiting website or employment search firm (so long as the firm is not instructed to solicit such Persons) or from hiring any Person as a result thereof or (ii) soliciting or hiring any such Person who [has left the employment of the Company][was terminated by the Company] at least [___] months prior to such solicitation or being hired.

## RAG Answer

Yes. The document includes such a clause in **Section 7 (“No Solicitation or Hiring”)**.

That section provides that **Buyer**—the receiving party of Evaluation Material—agrees that, except with the Company’s prior written consent, it will not directly or indirectly **solicit for employment or hire** certain Company personnel, such as **[employees/officers/senior management]** of the Company, including those first introduced to or known to Buyer in connection with the Transaction evaluation or listed on an exhibit, for a specified period.

The clause also contains carve-outs, including that it does not restrict:

- general employment solicitations not specifically directed at those persons; or  
- soliciting or hiring persons who left or were terminated by the Company at least a specified number of months earlier.

## Judge

- correct: True
- error_type: none
- gold_summary: 金标规定 Buyer/Receiving Party 未经 Company/Disclosing Party 事先书面同意，不得直接或间接 solicit for employment or hire Company 的某些人员（如 employees/officers/senior management），并包含一般招聘和离职/被解雇人员等例外。
- answer_summary: 系统回答确认存在禁止 soliciting/hiring 的 Section 7，说明 Buyer 未经 Company 同意不得直接或间接 solicit for employment or hire Company 的 employees/officers/senior management 等人员，并提及一般招聘和离职/被解雇人员的 carve-outs。
- gap: 无
- reason: 系统回答覆盖了金标的关键要点：禁止 Receiving Party/Buyer 未经同意 soliciting 或 hiring Disclosing Party/Company 的某些代表人员，并提到了相关例外；措辞不同不影响命中。
