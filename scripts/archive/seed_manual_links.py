"""Write data/reports/mfapi_et_manual_links.csv from embedded user paste."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "reports" / "mfapi_et_manual_links.csv"

# Embedded CSV (mf_scheme_code, mfapi_name_cleaned, ET Link, mf_category)
CSV = r"""mf_scheme_code,mfapi_name_cleaned,ET Link,mf_category
125345,360 One Liquid Fund,https://www.etmoney.com/mutual-funds/360-one-liquid-fund-direct-growth/21882,Debt Scheme - Liquid Fund
154051,Abakkus Liquid Fund,https://www.etmoney.com/mutual-funds/abakkus-liquid-fund-direct-growth/46017,Debt Scheme - Liquid Fund
119568,Aditya Birla Sun Life Liquid Fund,https://www.etmoney.com/mutual-funds/aditya-birla-sun-life-liquid-fund-direct-growth/15367,Debt Scheme - Liquid Fund
120389,Axis Liquid Fund,https://www.etmoney.com/mutual-funds/axis-liquid-direct-fund-growth/15315,Debt Scheme - Liquid Fund
151833,Bajaj Finserv Liquid Fund,https://www.etmoney.com/mutual-funds/bajaj-finserv-liquid-fund-direct-growth/44000,Debt Scheme - Liquid Fund
118364,Bandhan Liquid Fund,https://www.etmoney.com/mutual-funds/bandhan-liquid-fund-direct-plan-growth/16035,Debt Scheme - Liquid Fund
119369,Bank Of India Liquid Fund,https://www.etmoney.com/mutual-funds/bank-of-india-liquid-fund-direct-growth/15841,Debt Scheme - Liquid Fund
119415,Baroda Bnp Paribas Liquid Fund,https://www.etmoney.com/mutual-funds/baroda-bnp-paribas-liquid-direct-fund-growth/15341,Debt Scheme - Liquid Fund
130479,Bnp Paribas Liquid Fund,,Debt Scheme - Liquid Fund
118305,Canara Robeco Liquid Fund,https://www.etmoney.com/mutual-funds/canara-robeco-liquid-direct-plan-growth/16178,Debt Scheme - Liquid Fund
154011,Capitalmind Liquid Fund,https://www.etmoney.com/mutual-funds/capitalmind-liquid-fund-direct-growth/45965,Debt Scheme - Liquid Fund
119125,Dsp Liquidity Fund,https://www.etmoney.com/mutual-funds/dsp-liquidity-direct-growth/15678,Debt Scheme - Liquid Fund
140196,Edelweiss Liquid Fund,https://www.etmoney.com/mutual-funds/edelweiss-liquid-direct-growth/16139,Debt Scheme - Liquid Fund
118577,Franklin India Liquid Fund - Super Institutional,https://www.etmoney.com/mutual-funds/franklin-india-liquid-fund-super-institutional-plan-direct-growth/16411,Debt Scheme - Liquid Fund
119135,Groww Liquid Fund ( Formerly Known As Indiabulls Liquid )fund,,Debt Scheme - Liquid Fund
119091,Hdfc Liquid Fund,https://www.etmoney.com/mutual-funds/hdfc-liquid-direct-plan-growth/15734,Debt Scheme - Liquid Fund
120038,Hsbc Liquid Fund,https://www.etmoney.com/mutual-funds/hsbc-liquid-fund-direct-growth/15852,Debt Scheme - Liquid Fund
120197,Icici Prudential Liquid Fund,https://www.etmoney.com/mutual-funds/icici-prudential-liquid-fund-direct-plan-growth/15528,Debt Scheme - Liquid Fund
147937,Indiabulls Liquid Fund,,Debt Scheme - Liquid Fund
147939,Indiabulls Liquid Fund,,Debt Scheme - Liquid Fund
120537,Invesco India Liquid Fund,https://www.etmoney.com/mutual-funds/invesco-india-liquid-fund-direct-growth/16343,Debt Scheme - Liquid Fund
147157,Iti Liquid Fund,https://www.etmoney.com/mutual-funds/iti-liquid-fund-direct-growth/40317,Debt Scheme - Liquid Fund
153651,Jioblackrock Liquid Fund,,Debt Scheme - Liquid Fund
120406,Jm Liquid Fund,,Debt Scheme - Liquid Fund
148414,Jm Liquid Fund - Unclaimed Application Refund Amount I.e.f.,,Debt Scheme - Liquid Fund
148413,Jm Liquid Fund - Unclaimed Brokerage I.e.f.,,Debt Scheme - Liquid Fund
139257,Jm Liquid Fund Unclaimed Redemption,,Debt Scheme - Liquid Fund
139259,Jm Liquid Fund Unclaimed Redemption Ief,,Debt Scheme - Liquid Fund
119766,Kotak Liquid Fund,https://www.etmoney.com/mutual-funds/kotak-liquid-direct-growth/15932,Debt Scheme - Liquid Fund
119790,L&t Liquid Fund,,Debt Scheme - Liquid Fund
120249,Lic Mf Liquid Fund,https://www.etmoney.com/mutual-funds/lic-mf-liquid-fund-direct-growth/16385,Debt Scheme - Liquid Fund
139538,Mahindra Manulife Liquid Fund,,Debt Scheme - Liquid Fund
118859,Mirae Asset Liquid Fund,https://www.etmoney.com/mutual-funds/mirae-asset-liquid-fund-direct-growth/16117,Debt Scheme - Liquid Fund
145834,Motilal Oswal Liquid Fund,https://www.etmoney.com/mutual-funds/motilal-oswal-liquid-fund-direct-growth/38994,Debt Scheme - Liquid Fund
119164,Navi Liquid Fund,https://www.etmoney.com/mutual-funds/navi-liquid-fund-direct-growth/16036,Debt Scheme - Liquid Fund
118701,Nippon India Liquid Fund,https://www.etmoney.com/mutual-funds/nippon-india-liquid-fund-direct-growth/15667,Debt Scheme - Liquid Fund
143269,Parag Parikh Liquid Fund,https://www.etmoney.com/mutual-funds/parag-parikh-liquid-fund-direct-growth/36497,Debt Scheme - Liquid Fund
138299,Pgim India Liquid Fund,https://www.etmoney.com/mutual-funds/pgim-india-liquid-fund-direct-plan-growth/15172,Debt Scheme - Liquid Fund
119468,Principal Cash Management Fund,,Debt Scheme - Liquid Fund
120837,Quant Liquid Fund,https://www.etmoney.com/mutual-funds/quant-liquid-direct-fund-growth/16587,Debt Scheme - Liquid Fund
119800,Sbi Liquid Fund,https://www.etmoney.com/mutual-funds/sbi-liquid-fund-direct-plan-growth/15869,Debt Scheme - Liquid Fund
153035,Shriram Liquid Fund,,Debt Scheme - Liquid Fund
149664,Sundaram Liquid Fund (formerly Known As Principal Cash Management Fund),https://www.etmoney.com/mutual-funds/sundaram-liquid-direct-growth/16095,Debt Scheme - Liquid Fund
119686,Sundaram Money Fund,https://www.etmoney.com/mutual-funds/sundaram-money-market-fund-direct-growth/38210,Debt Scheme - Liquid Fund
119861,Tata Liquid Fund,https://www.etmoney.com/mutual-funds/tata-liquid-fund-direct-growth/16286,Debt Scheme - Liquid Fund
118893,Taurus Liquid Fund,,Debt Scheme - Liquid Fund
153883,The Wealth Company Liquid Fund,https://www.etmoney.com/mutual-funds/the-wealth-company-liquid-fund-direct-growth/45839,Debt Scheme - Liquid Fund
148841,Trustmf Liquid Fund,,Debt Scheme - Liquid Fund
153570,Unifi Liquid Fund,,Debt Scheme - Liquid Fund
119303,Union Liquid Fund,https://www.etmoney.com/mutual-funds/union-liquid-fund-direct-growth/15984,Debt Scheme - Liquid Fund
120304,Uti- Liquid Cash Plan,https://www.etmoney.com/mutual-funds/uti-liquid-direct-growth/15325,Debt Scheme - Liquid Fund
145971,Whiteoak Capital Liquid Fund,https://www.etmoney.com/mutual-funds/whiteoak-capital-liquid-fund-direct-growth/39125,Debt Scheme - Liquid Fund
118610,Reliance Liquid Fund - Cash Plan,,Direct
119661,Aditya Birla Sun Life Tax Plan,https://www.etmoney.com/mutual-funds/aditya-birla-sun-life-elss-tax-saver-direct-growth/15456,Equity Scheme - ELSS
134045,Baroda Elss 96 Plan B,,Equity Scheme - ELSS
120147,Bnp Paribas Long Term Equity Fund,https://www.etmoney.com/mutual-funds/baroda-bnp-paribas-elss-tax-saver-fund-direct-growth/15299,Equity Scheme - ELSS
138394,Dhfl Pramerica Tax Plan,,Equity Scheme - ELSS
140241,Edelweiss Tax Advantage Fund,https://www.etmoney.com/mutual-funds/edelweiss-elss-tax-saver-fund-direct-growth/17318,Equity Scheme - ELSS
141808,Groww Elss Tax Saver Fund (formerly Known As Indiabulls Tax Savings Fund),,Equity Scheme - ELSS
118929,Hdfc Long Term Advantage Plan,https://www.etmoney.com/mutual-funds/hdfc-elss-tax-saver-fund-direct-plan-growth/15727,Equity Scheme - ELSS
119417,L&t Tax Advantage Fund,,Equity Scheme - ELSS
135654,Navi Elss Tax Saver Fund,,Equity Scheme - ELSS
151611,Nj Elss Tax Saver Scheme,,Equity Scheme - ELSS
145819,Shriram Elss Tax Saver Fund,,Equity Scheme - ELSS
118866,Taurus Elss Tax Saver Fund,,Equity Scheme - ELSS
153859,Jioblackrock Flexi Cap Fund,,Equity Scheme - Flexi Cap Fund
151917,Nj Flexi Cap Fund,,Equity Scheme - Flexi Cap Fund
144905,Shriram Flexi Cap Fund,,Equity Scheme - Flexi Cap Fund
118883,Taurus Flexi Cap Fund,,Equity Scheme - Flexi Cap Fund
152584,Trustmf Flexi Cap Fund,,Equity Scheme - Flexi Cap Fund
153543,Unifi Flexi Cap Fund,,Equity Scheme - Flexi Cap Fund
141813,Bnp Paribas Focused 25 Equity Fund,https://www.etmoney.com/mutual-funds/baroda-bnp-paribas-focused-fund-direct-growth/35140,Equity Scheme - Focused Fund
145376,L&t Focused Equity Fund,,Equity Scheme - Focused Fund
119464,Principal Focused Multicap Fund,,Equity Scheme - Focused Fund
149533,Sundaram Focused Fund (formerly Known As Principal Focused Multicap Fund),https://www.etmoney.com/mutual-funds/sundaram-focused-fund-direct-growth/16177,Equity Scheme - Focused Fund
119578,Sundaram Select Focus,,Equity Scheme - Focused Fund
135677,Navi Large & Midcap Fund,,Equity Scheme - Large & Mid Cap Fund
119441,Principal Emerging Bluechip Fund,,Equity Scheme - Large & Mid Cap Fund
119367,Baroda Large Cap Fund - Plan B,https://www.etmoney.com/mutual-funds/baroda-bnp-paribas-large-cap-fund-direct-growth/15286,Equity Scheme - Large Cap Fund
119133,Groww Largecap Fund (formerly Known As Indiabulls Blue Chip Fund),,Equity Scheme - Large Cap Fund
118344,Idbi India Top 100 Equity Fund,,Equity Scheme - Large Cap Fund
154307,Jioblackrock Large Cap Fund,,Equity Scheme - Large Cap Fund
119148,Navi Large Cap Equity Fund,,Equity Scheme - Large Cap Fund
148524,Principal Large Cap Fund,,Equity Scheme - Large Cap Fund
118870,Taurus Large Cap Fund,,Equity Scheme - Large Cap Fund
119392,Baroda Mid-cap Fund- Plan B,,Equity Scheme - Mid Cap Fund
120002,Bnp Paribas Mid Cap Fund,https://www.etmoney.com/mutual-funds/baroda-bnp-paribas-midcap-fund-direct-growth/15293,Equity Scheme - Mid Cap Fund
140461,Idbi Midcap Fund,,Equity Scheme - Mid Cap Fund
147778,Principal Midcap Fund,,Equity Scheme - Mid Cap Fund
118872,Taurus Mid Cap Fund,,Equity Scheme - Mid Cap Fund
153034,Groww Multicap Fund,,Equity Scheme - Multi Cap Fund
119291,L&t Flexicap Fund,,Equity Scheme - Multi Cap Fund
119452,Principal Multi Cap Growth Fund,,Equity Scheme - Multi Cap Fund
147587,Sundaram Equity Fund,https://www.etmoney.com/mutual-funds/sundaram-multi-cap-fund-direct-growth/16143,Equity Scheme - Multi Cap Fund
119572,Sundaram Multi Asset Fund,https://www.etmoney.com/mutual-funds/sundaram-multi-asset-allocation-fund-direct-growth/44407,Equity Scheme - Multi Cap Fund
153644,Trustmf Multi Cap Fund,,Equity Scheme - Multi Cap Fund
119591,Aditya Birla Sun Life Consumption Fund,https://www.etmoney.com/mutual-funds/aditya-birla-sun-life-consumption-direct-fund-growth/15401,Equity Scheme - Sectoral/ Thematic
148637,Aditya Birla Sun Life Esg Integration Strategy Fund,https://www.etmoney.com/mutual-funds/aditya-birla-sun-life-esg-integration-strategy-fund-direct-growth/41689,Equity Scheme - Sectoral/ Thematic
119517,Aditya Birla Sun Life International Equity Fund,,Equity Scheme - Sectoral/ Thematic
133516,Aditya Birla Sun Life Manufacturing Equity Fund,https://www.etmoney.com/mutual-funds/aditya-birla-sun-life-manufacturing-equity-fund-direct-growth/28712,Equity Scheme - Sectoral/ Thematic
152158,Aditya Birla Sun Life Transportation And Logistics Fund,https://www.etmoney.com/mutual-funds/aditya-birla-sun-life-transportation-and-logistics-fund-direct-growth/44211,Equity Scheme - Sectoral/ Thematic
152805,Axis Consumption Fund,https://www.etmoney.com/mutual-funds/axis-consumption-fund-direct-growth/44826,Equity Scheme - Sectoral/ Thematic
147928,Axis Esg Integration Strategy Fund,https://www.etmoney.com/mutual-funds/axis-esg-integration-strategy-fund-direct-growth/41003,Equity Scheme - Sectoral/ Thematic
152202,Axis India Manufacturing Fund,https://www.etmoney.com/mutual-funds/axis-india-manufacturing-fund-direct-growth/44224,Equity Scheme - Sectoral/ Thematic
148634,Axis Innovation Fund,https://www.etmoney.com/mutual-funds/axis-innovation-fund-direct-growth/41693,Equity Scheme - Sectoral/ Thematic
153075,Bajaj Finserv Consumption Fund,https://www.etmoney.com/mutual-funds/bajaj-finserv-consumption-fund-direct-growth/45048,Equity Scheme - Sectoral/ Thematic
152607,Bandhan Innovation Fund,https://www.etmoney.com/mutual-funds/bandhan-innovation-fund-direct-growth/44610,Equity Scheme - Sectoral/ Thematic
150716,Bandhan Transportation And Logistics Fund,https://www.etmoney.com/mutual-funds/bandhan-transportation-and-logistics-fund-direct-growth/43069,Equity Scheme - Sectoral/ Thematic
153139,Bank Of India Consumption Fund,https://www.etmoney.com/mutual-funds/bank-of-india-consumption-fund-direct-growth/45167,Equity Scheme - Sectoral/ Thematic
154195,Baroda Bnp Paribas Best-in-class Strategy Fund,https://www.etmoney.com/mutual-funds/baroda-bnp-paribas-esg-best-in-class-strategy-fund-direct-growth/46163,Equity Scheme - Sectoral/ Thematic
150266,Baroda Bnp Paribas India Consumption Fund,https://www.etmoney.com/mutual-funds/baroda-bnp-paribas-india-consumption-fund-direct-growth/37823,Equity Scheme - Sectoral/ Thematic
152470,Baroda Bnp Paribas Innovation Fund,https://www.etmoney.com/mutual-funds/baroda-bnp-paribas-innovation-fund-direct-growth/44467,Equity Scheme - Sectoral/ Thematic
152697,Baroda Bnp Paribas Manufacturing Fund,https://www.etmoney.com/mutual-funds/baroda-bnp-paribas-manufacturing-fund-direct-growth/44726,Equity Scheme - Sectoral/ Thematic
144634,Bnp Paribas India Consumption Fund,,Equity Scheme - Sectoral/ Thematic
154250,Canara Robeco Banking And Financials Services Fund,https://www.etmoney.com/mutual-funds/canara-robeco-banking-and-financial-services-fund-direct-growth/46187,Equity Scheme - Sectoral/ Thematic
118273,Canara Robeco Consumption Fund,https://www.etmoney.com/mutual-funds/canara-robeco-consumption-fund-direct-growth/16163,Equity Scheme - Sectoral/ Thematic
152450,Canara Robeco Manufacturing Fund,https://www.etmoney.com/mutual-funds/canara-robeco-manufacturing-fund-direct-growth/44491,Equity Scheme - Sectoral/ Thematic
119247,Dsp India T.i.g.e.r. Fund,https://www.etmoney.com/mutual-funds/dsp-india-tiger-the-infrastructure-growth-and-economic-reforms-fund-direct-growth/15977,Equity Scheme - Sectoral/ Thematic
153214,Edelweiss Consumption Fund,https://www.etmoney.com/mutual-funds/edelweiss-consumption-fund-direct-growth/45237,Equity Scheme - Sectoral/ Thematic
152254,Groww Banking & Financial Services Fund,,Equity Scheme - Sectoral/ Thematic
151804,Hdfc Consumption Fund,https://www.etmoney.com/mutual-funds/hdfc-consumption-fund-direct-growth/43966,Equity Scheme - Sectoral/ Thematic
153620,Hdfc Innovation Fund,https://www.etmoney.com/mutual-funds/hdfc-innovation-fund-direct-growth/45625,Equity Scheme - Sectoral/ Thematic
152600,Hdfc Manufacturing Fund,https://www.etmoney.com/mutual-funds/hdfc-manufacturing-fund-direct-growth/44652,Equity Scheme - Sectoral/ Thematic
151901,Hdfc Transportation And Logistics Fund,https://www.etmoney.com/mutual-funds/hdfc-transportation-and-logistics-fund-direct-growth/44079,Equity Scheme - Sectoral/ Thematic
152032,Hsbc Consumption Fund,https://www.etmoney.com/mutual-funds/hsbc-consumption-fund-direct-growth/44099,Equity Scheme - Sectoral/ Thematic
120034,Hsbc Infrastructure Equity Fund,https://www.etmoney.com/mutual-funds/hsbc-infrastructure-fund-direct-growth/15842,Equity Scheme - Sectoral/ Thematic
146951,Icici Prudential Bharat Consumption Fund,https://www.etmoney.com/mutual-funds/icici-prudential-bharat-consumption-fund-direct-growth/40150,Equity Scheme - Sectoral/ Thematic
148516,Icici Prudential Esg Exclusionary Strategy Fund,https://www.etmoney.com/mutual-funds/icici-prudential-esg-exclusionary-strategy-fund-direct-growth/41595,Equity Scheme - Sectoral/ Thematic
151580,Icici Prudential Innovation Fund,https://www.etmoney.com/mutual-funds/icici-prudential-innovation-fund-direct-growth/43851,Equity Scheme - Sectoral/ Thematic
150685,Icici Prudential Transportation And Logistics Fund,https://www.etmoney.com/mutual-funds/icici-prudential-transportation-and-logistics-fund-direct-growth/43065,Equity Scheme - Sectoral/ Thematic
153900,Invesco India Consumption Fund,https://www.etmoney.com/mutual-funds/invesco-india-consumption-fund-direct-growth/45859,Equity Scheme - Sectoral/ Thematic
148751,Invesco India Esg Integration Strategy Fund,https://www.etmoney.com/mutual-funds/invesco-india-esg-integration-strategy-fund-direct-growth/41807,Equity Scheme - Sectoral/ Thematic
152756,Invesco India Manufacturing Fund,https://www.etmoney.com/mutual-funds/invesco-india-manufacturing-fund-direct-growth/44796,Equity Scheme - Sectoral/ Thematic
153260,Iti Bharat Consumption Fund,,Equity Scheme - Sectoral/ Thematic
154082,Jioblackrock Sector Rotation Fund,,Equity Scheme - Sectoral/ Thematic
152169,Kotak Consumption Fund,https://www.etmoney.com/mutual-funds/kotak-consumption-fund-direct-growth/44240,Equity Scheme - Sectoral/ Thematic
148606,Kotak Esg Exclusionary Strategy Fund,https://www.etmoney.com/mutual-funds/kotak-esg-exclusionary-strategy-fund-direct-growth/41670,Equity Scheme - Sectoral/ Thematic
149841,Kotak Manufacture In India Fund,https://www.etmoney.com/mutual-funds/kotak-manufacture-in-india-fund-direct-growth/42505,Equity Scheme - Sectoral/ Thematic
153118,Kotak Transportation & Logistics Fund,https://www.etmoney.com/mutual-funds/kotak-transportation-and-logistics-fund-direct-growth/45089,Equity Scheme - Sectoral/ Thematic
153948,Lic Mf Consumption Fund,https://www.etmoney.com/mutual-funds/lic-mf-consumption-fund-direct-growth/45898,Equity Scheme - Sectoral/ Thematic
152920,Lic Mf Manufacturing Fund,https://www.etmoney.com/mutual-funds/lic-mf-manufacturing-fund-direct-growth/44945,Equity Scheme - Sectoral/ Thematic
145356,Mahindra Manulife Consumption Fund,https://www.etmoney.com/mutual-funds/mahindra-manulife-consumption-fund-direct-growth/38326,Equity Scheme - Sectoral/ Thematic
154121,Mahindra Manulife Innovation Opportunities Fund,https://www.etmoney.com/mutual-funds/mahindra-manulife-innovation-opportunities-fund-direct-growth/46063,Equity Scheme - Sectoral/ Thematic
152672,Mahindra Manulife Manufacturing Fund,https://www.etmoney.com/mutual-funds/mahindra-manulife-manufacturing-fund-direct-growth/44715,Equity Scheme - Sectoral/ Thematic
118837,Mirae Asset Great Consumer Fund,https://www.etmoney.com/mutual-funds/mirae-asset-great-consumer-fund-direct-growth/16147,Equity Scheme - Sectoral/ Thematic
153913,Motilal Oswal Consumption Fund,https://www.etmoney.com/mutual-funds/motilal-oswal-consumption-fund-direct-growth/45873,Equity Scheme - Sectoral/ Thematic
153258,Motilal Oswal Innovation Opportunities Fund,https://www.etmoney.com/mutual-funds/motilal-oswal-innovation-opportunities-fund-direct-growth/45257,Equity Scheme - Sectoral/ Thematic
152760,Motilal Oswal Manufacturing Fund,https://www.etmoney.com/mutual-funds/motilal-oswal-manufacturing-fund-direct-growth/44802,Equity Scheme - Sectoral/ Thematic
118724,Nippon India Consumption Fund,https://www.etmoney.com/mutual-funds/nippon-india-consumption-fund-direct-growth/15698,Equity Scheme - Sectoral/ Thematic
152033,Nippon India Innovation Fund,https://www.etmoney.com/mutual-funds/nippon-india-innovation-fund-direct-growth/44109,Equity Scheme - Sectoral/ Thematic
134923,Nippon India Us Equity Opportunities Fund,,Equity Scheme - Sectoral/ Thematic
152336,Quant Consumption Fund,https://www.etmoney.com/mutual-funds/quant-consumption-fund-direct-growth/44418,Equity Scheme - Sectoral/ Thematic
151916,Quant Manufacturing Fund,https://www.etmoney.com/mutual-funds/quant-manufacturing-fund-direct-growth/44075,Equity Scheme - Sectoral/ Thematic
147372,Quantum Esg Best In Class Strategy Fund,https://www.etmoney.com/mutual-funds/quantum-esg-best-in-class-strategy-fund-direct-growth/40488,Equity Scheme - Sectoral/ Thematic
152657,Sbi Automotive Opportunities Fund,https://www.etmoney.com/mutual-funds/sbi-automotive-opportunities-fund-direct-growth/44707,Equity Scheme - Sectoral/ Thematic
120575,Sbi Consumption Opportunities Fund,https://www.etmoney.com/mutual-funds/sbi-consumption-opportunities-fund-direct-growth/17081,Equity Scheme - Sectoral/ Thematic
119709,Sbi Esg Exclusionary Strategy Fund,https://www.etmoney.com/mutual-funds/sbi-esg-exclusionary-strategy-fund-direct-plan-growth/15786,Equity Scheme - Sectoral/ Thematic
152776,Sbi Innovative Opportunities Fund,https://www.etmoney.com/mutual-funds/sbi-innovative-opportunities-fund-direct-growth/44819,Equity Scheme - Sectoral/ Thematic
153076,Shriram Multi Sector Rotation Fund,,Equity Scheme - Sectoral/ Thematic
119595,Sundaram Consumption Fund (formerly Known As Sundaram Rural And Consumption Fund),https://www.etmoney.com/mutual-funds/sundaram-consumption-fund-direct-growth/15730,Equity Scheme - Sectoral/ Thematic
135805,Tata India Consumer Fund,https://www.etmoney.com/mutual-funds/tata-india-consumer-fund-direct-growth/30859,Equity Scheme - Sectoral/ Thematic
153055,Tata India Innovation Fund,https://www.etmoney.com/mutual-funds/tata-india-innovation-fund-direct-growth/45075,Equity Scheme - Sectoral/ Thematic
118868,Taurus Banking & Financial Services Fund,,Equity Scheme - Sectoral/ Thematic
118876,Taurus Ethical Fund,,Equity Scheme - Sectoral/ Thematic
118879,Taurus Infrastructure Fund,,Equity Scheme - Sectoral/ Thematic
154020,Union Consumption Fund,https://www.etmoney.com/mutual-funds/union-consumption-fund-direct-growth/45996,Equity Scheme - Sectoral/ Thematic
151905,Union Innovation & Opportunities Fund,https://www.etmoney.com/mutual-funds/union-innovation-and-opportunities-fund-direct-growth/44063,Equity Scheme - Sectoral/ Thematic
120780,Uti India Consumer Fund,https://www.etmoney.com/mutual-funds/uti-india-consumer-fund-direct-growth/15461,Equity Scheme - Sectoral/ Thematic
152087,Uti Innovation Fund,https://www.etmoney.com/mutual-funds/uti-innovation-fund-direct-growth/44180,Equity Scheme - Sectoral/ Thematic
120731,Uti-transportation And Logistics Fund,https://www.etmoney.com/mutual-funds/uti-transportation-and-logistics-fund-direct-growth/15522,Equity Scheme - Sectoral/ Thematic
154161,Whiteoak Capital Consumption Opportunities Fund,https://www.etmoney.com/mutual-funds/whiteoak-capital-consumption-opportunities-fund-direct-growth/46106,Equity Scheme - Sectoral/ Thematic
152962,Whiteoak Capital Esg Best-in-class Strategy Fund,https://www.etmoney.com/mutual-funds/whiteoak-capital-esg-best-in-class-strategy-fund-direct-growth/45004,Equity Scheme - Sectoral/ Thematic
152349,Whiteoak Capital Pharma And Heathcare Fund,https://www.etmoney.com/mutual-funds/whiteoak-capital-pharma-and-healthcare-fund-direct-growth/44426,Equity Scheme - Sectoral/ Thematic
154063,Groww Small Cap Fund,,Equity Scheme - Small Cap Fund
141475,Idbi Small Cap Fund,,Equity Scheme - Small Cap Fund
129220,L&t Emerging Businesses Fund,,Equity Scheme - Small Cap Fund
147131,Principal Small Cap Fund,,Equity Scheme - Small Cap Fund
152939,Trustmf Small Cap Fund,,Equity Scheme - Small Cap Fund
135341,Groww Value Fund (formerly Known As Indiabulls Value Fund),,Equity Scheme - Value Fund
120323,Icici Prudential Value Fund (erstwhile Value Discovery Fund),https://www.etmoney.com/mutual-funds/icici-prudential-value-direct-growth/15389,Equity Scheme - Value Fund
144455,Idbi Long Term Value Fund,,Equity Scheme - Value Fund
119404,L&t India Value Fund,,Equity Scheme - Value Fund
118345,Idbi Liquid Fund,,Formerly Known as IIFL Mutual Fund
148415,Jm Liquid Fund - Withheld Brokerage I.e.f.,,Formerly Known as IIFL Mutual Fund
119326,Baroda Hybrid Equity Fund - Plan B,,Hybrid Scheme - Aggressive Hybrid Fund
141006,Bnp Paribas Substantial Equity Hybrid Fund,,Hybrid Scheme - Aggressive Hybrid Fund
145599,Groww Aggressive Hybrid Fund (formerly Known As Indiabulls Equity Hybrid Fund),,Hybrid Scheme - Aggressive Hybrid Fund
145228,Hsbc Equity Hybrid Fund,,Hybrid Scheme - Aggressive Hybrid Fund
139971,Idbi Hybrid Equity Fund,,Hybrid Scheme - Aggressive Hybrid Fund
144681,Motilal Oswal Equity Hybrid Fund (mofeh),,Hybrid Scheme - Aggressive Hybrid Fund
148265,Nippon India Aggressive Hybrid Fund - Segregated Portfolio 2,https://www.etmoney.com/mutual-funds/nippon-india-aggressive-hybrid-fund-direct-growth/15726,Hybrid Scheme - Aggressive Hybrid Fund
147689,Nippon India Equity Hybrid Fund - Segregated Portfolio 1,,Hybrid Scheme - Aggressive Hybrid Fund
119484,Principal Hybrid Equity Fund,,Hybrid Scheme - Aggressive Hybrid Fund
125711,Shriram Aggressive Hybrid Fund,,Hybrid Scheme - Aggressive Hybrid Fund
154320,Groww Arbitrage Fund,,Hybrid Scheme - Arbitrage Fund
133181,Groww Arbitrage Fund (formerly Known As Indiabulls Arbitrage Fund),,Hybrid Scheme - Arbitrage Fund
129052,Hdfc Arbitrage Fund,,Hybrid Scheme - Arbitrage Fund
154076,Jioblackrock Arbitrage Fund,,Hybrid Scheme - Arbitrage Fund
144658,Navi Arbitrage Fund,,Hybrid Scheme - Arbitrage Fund
150367,Nj Arbitrage Fund,,Hybrid Scheme - Arbitrage Fund
139221,Principal Arbitrage Fund,,Hybrid Scheme - Arbitrage Fund
149550,Sundaram Arbitrage Fund (formerly Known As Prinicpal Arbitrage Fund),https://www.etmoney.com/mutual-funds/sundaram-arbitrage-fund-direct-growth/31779,Hybrid Scheme - Arbitrage Fund
153804,Trustmf Arbitrage Fund,,Hybrid Scheme - Arbitrage Fund
119542,Sundaram Equity Hybrid Fund,,Hybrid Scheme - Balanced Hybrid Fund
120480,Axis Conservative Hybrid Fund,https://www.etmoney.com/mutual-funds/axis-conservative-hybrid-fund-direct-growth/16893,Hybrid Scheme - Conservative Hybrid Fund
118491,Bandhan Conservative Hybrid Fund,https://www.etmoney.com/mutual-funds/bandhan-conservative-hybrid-fund-direct-plan-growth/16088,Hybrid Scheme - Conservative Hybrid Fund
150206,Baroda Bnp Paribas Conservative Hybrid Fund,https://www.etmoney.com/mutual-funds/baroda-bnp-paribas-conservative-hybrid-fund-direct-growth/15295,Hybrid Scheme - Conservative Hybrid Fund
119389,Baroda Conservative Hybrid Fund - Plan B,,Hybrid Scheme - Conservative Hybrid Fund
120082,Bnp Paribas Conservative Hybrid Fund,,Hybrid Scheme - Conservative Hybrid Fund
118309,Canara Robeco Conservative Hybrid Fund,https://www.etmoney.com/mutual-funds/canara-robeco-conservative-hybrid-fund-direct-growth/15337,Hybrid Scheme - Conservative Hybrid Fund
138464,Dhfl Pramerica Hybrid Debt Fund,,Hybrid Scheme - Conservative Hybrid Fund
118574,Franklin India Conservative Hybrid Fund,https://www.etmoney.com/mutual-funds/franklin-india-conservative-hybrid-fund-a-direct-growth/17386,Hybrid Scheme - Conservative Hybrid Fund
148302,Franklin India Debt Hybrid Fund - Segregated Portfolio 1 (10.25% Yes Bank Ltd Co 05mar20),,Hybrid Scheme - Conservative Hybrid Fund
119118,Hdfc Hybrid Debt Fund,https://www.etmoney.com/mutual-funds/hdfc-hybrid-debt-fund-direct-growth/16016,Hybrid Scheme - Conservative Hybrid Fund
120073,Hsbc Conservative Hybrid Fund,https://www.etmoney.com/mutual-funds/hsbc-conservative-hybrid-fund-direct-growth/16617,Hybrid Scheme - Conservative Hybrid Fund
135689,Indiabulls Savings Income Fund,,Hybrid Scheme - Conservative Hybrid Fund
120154,Kotak Debt Hybrid,https://www.etmoney.com/mutual-funds/kotak-debt-hybrid-fund-direct-growth/17351,Hybrid Scheme - Conservative Hybrid Fund
119852,L&t Conservative Hybrid Fund,,Hybrid Scheme - Conservative Hybrid Fund
120276,Lic Mf Conservative Hybrid Fund,https://www.etmoney.com/mutual-funds/lic-mf-conservative-hybrid-fund-direct-growth/17015,Hybrid Scheme - Conservative Hybrid Fund
119156,Navi Conservative Hybrid Fund,,Hybrid Scheme - Conservative Hybrid Fund
118726,Nippon India Conservative Hybrid Fund,https://www.etmoney.com/mutual-funds/nippon-india-conservative-hybrid-fund-direct-growth/15711,Hybrid Scheme - Conservative Hybrid Fund
148296,Nippon India Conservative Hybrid Fund - Segregated Portfolio 2,,Hybrid Scheme - Conservative Hybrid Fund
148143,Nippon India Hybrid Bond Fund - Segregated Portfolio 1,,Hybrid Scheme - Conservative Hybrid Fund
148958,Parag Parikh Conservative Hybrid Fund,https://www.etmoney.com/mutual-funds/parag-parikh-conservative-hybrid-fund-direct-growth/41952,Hybrid Scheme - Conservative Hybrid Fund
119839,Sbi Conservative Hybrid Fund,https://www.etmoney.com/mutual-funds/sbi-conservative-hybrid-fund-direct-growth/17072,Hybrid Scheme - Conservative Hybrid Fund
119635,Sundaram Conservative Hybrid Fund (formerly Known As Sundaram Debt Oriented Hybrid Fund),https://www.etmoney.com/mutual-funds/sundaram-conservative-hybrid-fund-direct-plan-growth/16786,Hybrid Scheme - Conservative Hybrid Fund
120779,Uti Conservative Hybrid Fund,https://www.etmoney.com/mutual-funds/uti-conservative-hybrid-fund-direct-growth/15371,Hybrid Scheme - Conservative Hybrid Fund
146402,Bnp Paribas Dynamic Equity Fund,,Hybrid Scheme - Dynamic Asset Allocation or Balanced Advantage
120042,Hsbc Dynamic Asset Allocation Fund,,Hybrid Scheme - Dynamic Asset Allocation or Balanced Advantage
149264,Nj Balanced Advantage Fund,,Hybrid Scheme - Dynamic Asset Allocation or Balanced Advantage
119482,Principal Balanced Advantage Fund,,Hybrid Scheme - Dynamic Asset Allocation or Balanced Advantage
134110,Sbi Dynamic Asset Allocation Fund,,Hybrid Scheme - Dynamic Asset Allocation or Balanced Advantage
147406,Shriram Balanced Advantage Fund,,Hybrid Scheme - Dynamic Asset Allocation or Balanced Advantage
149717,Sundaram Balanced Advantage Fund ( Formerly Known As Principal Balanced Advantage Fund),https://www.etmoney.com/mutual-funds/sundaram-balanced-advantage-fund-direct-growth/16205,Hybrid Scheme - Dynamic Asset Allocation or Balanced Advantage
153376,Unifi Dynamic Asset Allocation Fund,,Hybrid Scheme - Dynamic Asset Allocation or Balanced Advantage
132995,Aditya Birla Sun Life Equity Savings Fund,https://www.etmoney.com/mutual-funds/aditya-birla-sun-life-equity-savings-fund-direct-growth/28190,Hybrid Scheme - Equity Savings
135120,Axis Equity Savings Fund,https://www.etmoney.com/mutual-funds/axis-equity-savings-fund-direct-growth/30202,Hybrid Scheme - Equity Savings
153758,Bajaj Finserv Equity Savings Fund,https://www.etmoney.com/mutual-funds/bajaj-finserv-equity-savings-fund-direct-growth/45732,Hybrid Scheme - Equity Savings
118477,Bandhan Equity Savings Fund,https://www.etmoney.com/mutual-funds/bandhan-equity-savings-fund-direct-growth/17411,Hybrid Scheme - Equity Savings
147496,Baroda Bnp Paribas Equity Savings Fund,https://www.etmoney.com/mutual-funds/baroda-bnp-paribas-equity-savings-fund-direct-growth/40597,Hybrid Scheme - Equity Savings
136567,Dsp Equity Savings Fund,https://www.etmoney.com/mutual-funds/dsp-equity-savings-fund-direct-growth/31638,Hybrid Scheme - Equity Savings
140347,Edelweiss Equity Savings Fund,https://www.etmoney.com/mutual-funds/edelweiss-equity-savings-fund-direct-growth/27749,Hybrid Scheme - Equity Savings
144466,Franklin India Equity Savings Fund,https://www.etmoney.com/mutual-funds/franklin-india-equity-savings-fund-direct-growth/37750,Hybrid Scheme - Equity Savings
119128,Hdfc Equity Savings Fund,https://www.etmoney.com/mutual-funds/hdfc-equity-savings-direct-plan-growth/15685,Hybrid Scheme - Equity Savings
151060,Hsbc Equity Savings Fund,https://www.etmoney.com/mutual-funds/hsbc-equity-savings-fund-direct-growth/15850,Hybrid Scheme - Equity Savings
118452,Idbi Equity Savings Fund,,Hybrid Scheme - Equity Savings
146457,Invesco India Equity Savings Fund,https://www.etmoney.com/mutual-funds/invesco-india-equity-savings-fund-direct-growth/39639,Hybrid Scheme - Equity Savings
131373,Kotak Equity Savings Fund,https://www.etmoney.com/mutual-funds/kotak-equity-savings-fund-direct-growth/27688,Hybrid Scheme - Equity Savings
119802,L&t Equity Savings Fund,,Hybrid Scheme - Equity Savings
151952,Lic Mf Equity Savings Fund,https://www.etmoney.com/mutual-funds/lic-mf-equity-savings-fund-direct-growth/16079,Hybrid Scheme - Equity Savings
140444,Mahindra Manulife Equity Savings Fund,https://www.etmoney.com/mutual-funds/mahindra-manulife-equity-savings-fund-direct-growth/33847,Hybrid Scheme - Equity Savings
145693,Mirae Asset Equity Savings Fund,https://www.etmoney.com/mutual-funds/mirae-asset-equity-savings-fund-direct-growth/38866,Hybrid Scheme - Equity Savings
134594,Nippon India Equity Savings Fund,https://www.etmoney.com/mutual-funds/nippon-india-equity-savings-fund-direct-growth/29719,Hybrid Scheme - Equity Savings
147697,Nippon India Equity Savings Fund - Segregated Portfolio 1,,Hybrid Scheme - Equity Savings
148274,Nippon India Equity Savings Fund - Segregated Portfolio 2,,Hybrid Scheme - Equity Savings
138376,Pgim India Equity Savings Fund,https://www.etmoney.com/mutual-funds/pgim-india-equity-savings-fund-direct-growth/15959,Hybrid Scheme - Equity Savings
119472,Principal Equity Savings Fund,,Hybrid Scheme - Equity Savings
153705,Quant Equity Savings Fund,https://www.etmoney.com/mutual-funds/quant-equity-savings-fund-direct-growth/45688,Hybrid Scheme - Equity Savings
134643,Sbi Equity Savings Fund,https://www.etmoney.com/mutual-funds/sbi-equity-savings-fund-direct-growth/29779,Hybrid Scheme - Equity Savings
145478,Sundaram Equity Savings Fund,https://www.etmoney.com/mutual-funds/sundaram-equity-savings-fund-direct-growth/16382,Hybrid Scheme - Equity Savings
149679,Sundaram Equity Savings Fund (formerly Known As Principal Equity Savings Fund),,Hybrid Scheme - Equity Savings
119960,Tata Equity Savings Fund,,Hybrid Scheme - Equity Savings
144312,Union Equity Savings Fund,https://www.etmoney.com/mutual-funds/union-equity-savings-fund-direct-growth/37606,Hybrid Scheme - Equity Savings
144490,Uti Equity Savings Fund,https://www.etmoney.com/mutual-funds/uti-equity-savings-fund-direct-growth/37837,Hybrid Scheme - Equity Savings
153355,Whiteoak Capital Equity Savings Fund,https://www.etmoney.com/mutual-funds/whiteoak-capital-equity-savings-fund-direct-growth/45354,Hybrid Scheme - Equity Savings
153821,Groww Multi Asset Allocation Fund,,Hybrid Scheme - Multi Asset Allocation
154316,Kotak Multi Asset Active Fof,https://www.etmoney.com/mutual-funds/kotak-multi-asset-active-fof-direct-growth/46261,Hybrid Scheme - Multi Asset Allocation
148454,Motilal Oswal Multi Asset Fund,,Hybrid Scheme - Multi Asset Allocation
119176,Navi 3 In 1 Fund,,Hybrid Scheme - Multi Asset Allocation
152051,Shriram Multi Asset Allocation Fund,,Hybrid Scheme - Multi Asset Allocation
119612,Aditya Birla Sun Life Gilt Plus - Liquid Plan,,Income
120123,Bnp Paribas Liquid Fund,,Income
119181,Daiwa Liquid Fund,,Income
120104,Dhfl Pramerica Liquid Fund,,Income
118636,Edelweiss Liquid Fund,,Income
119935,Ing Liquid Fund - Super Institutional Plan,,Income
119905,Jpmorgan India Liquid Fund,,Income
118857,Mirae Asset Liquid Fund,,Income
119173,Morgan Stanley Liquid Fund,,Income
119360,Pinebridge India Liquid Fund,,Income
120415,Jm Floater Short Term Fund,,Liquid
120262,Sahara Liquid Fund-fixed Pricing,,Liquid
120280,Sahara Liquid Fund-variable Pricing,,Liquid
"""


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(CSV.strip() + "\n", encoding="utf-8-sig")
    print(f"Wrote {OUT} ({len(CSV.splitlines()) - 1} data rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
