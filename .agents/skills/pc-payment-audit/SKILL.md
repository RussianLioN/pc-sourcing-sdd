---
name: pc-payment-audit
description: Audit Avito payment-route evidence against PAY-01 in this project, including preorder, conflicting routes and external advances.
---
Read `specs/001-offline/decision-table.md` and the specific Offer plus Evidence.
First distinguish purchase-wide advance/conflict from route-only conditions.
Evaluate protected and postpay independently for whole item, amount, Moscow
and order terms. A generic delivery badge is insufficient. Protected requires
platform_transaction; seller_statement may confirm explicit full postpay
without external advance. Preserve origin and observation time.
Return passed routes, manual reason, evidence IDs and payment gate; never
infer stock from payment. Unknown or conflict on one route does not override
the other valid route. Optional risky alternatives do not override it either.
Run `python -m pytest tests/test_payment.py`; inspect protected-conflict,
postpay-conflict, optional-risk and global-advance fixtures. Do not rewrite
golden values. No live lookup or seller contact is needed to audit fixtures.
