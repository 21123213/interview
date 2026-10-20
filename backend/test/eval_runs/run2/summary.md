# RAG Eval Summary

- overall n=345
- answer_acc=0.9826  （LLM：金标 vs RAG 回答）
- failures=6

> hit@20 不在主评测里计算；对失败题运行 `review_failures` 时会重新提问并写入该指标。

## Per file

| file_key | n | answer_acc |
|---|---:|---:|
| helpjuice_production%2Fuploads%2Fupload%2Fimage%2F2329%2Fdirect%2F1526996160411-FullStory+Mutual+Non-Disclosure+Agreement+2018.txt | 16 | 1.0 |
| NDA-Fintricity-Blank.txt | 15 | 0.9333 |
| INFOMAGNET%20NDA.txt | 14 | 1.0 |
| Kenway-NDA-Form-Blank.txt | 14 | 1.0 |
| MutualNDA_The_Knights_of_Unity.txt | 14 | 1.0 |
| NCDG_Non-disclosure-agreement.txt | 14 | 1.0 |
| IBC-PMS-NDA-agreement.txt | 13 | 1.0 |
| JB-Machine-LLC-NDA-1.txt | 13 | 0.9231 |
| Kerber_Non_Disclosure_Agreement.txt | 13 | 1.0 |
| LiiON%20NDA%202-27-2015%20v1.0.txt | 13 | 1.0 |
| NDA-ONSemi_IndustryAnalystConf-2011.txt | 13 | 1.0 |
| IGC-Non-Disclosure-Agreement-LSE-Sample.txt | 12 | 1.0 |
| IPTK-CO-MutualNon-DisclosureAgreement.txt | 12 | 1.0 |
| Model%20NDA%20(recommended%20by%20SWA).txt | 12 | 0.9167 |
| lti-two-way-cda-template.txt | 12 | 1.0 |
| JBF_NDA_rev-2017033-1.txt | 11 | 0.9091 |
| NDA-M5-Systems.txt | 11 | 1.0 |
| New_York_City_Bar_Association_Model_Form_of_Non-Disclosure_Agreement_2015.txt | 11 | 1.0 |
| nda-employee-template.txt | 11 | 1.0 |
| Inaturals_NDA.txt | 10 | 0.9 |
| NDA-SqillerBetaTesters.txt | 10 | 1.0 |
| NDA-Artop-Inno-2017.txt | 9 | 1.0 |
| NDA_-_GWI_-_Technohubs_version_V1.txt | 9 | 1.0 |
| khronos-mutual-nda.txt | 9 | 1.0 |
| mcgill_mitacs_terms-january2013.txt | 9 | 1.0 |
| NDA-Seeed.txt | 8 | 1.0 |
| ingram-non-disclosure.txt | 8 | 0.875 |
| NDA-Dollar-General-Portfolio.txt | 7 | 1.0 |
| NDA-for-Gar-Kenyon-Suppliers.txt | 7 | 1.0 |
| NDA-ROI-Corporation.txt | 5 | 1.0 |
| nda_gtl_inria.txt | 5 | 1.0 |
| nda_form_motorola.txt | 4 | 1.0 |
| HNBA-2017-18-Confidentiality-Agreement.txt | 1 | 1.0 |
