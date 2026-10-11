# PAY-01 decision table 1.0.0
All routes include full applicability, matching evidence and no required
external advance. Applicability to a partial amount fails the whole route.

| Protected | Full postpay | Global condition | payment gate |
|---|---|---|---|
| unknown | unknown | no advance | manual |
| unavailable | unavailable | no advance | manual |
| unknown | confirmed | no advance | pass postpay |
| confirmed | unknown | no advance | pass protected |
| confirmed | confirmed | no advance | pass both |
| conflict | confirmed | no advance | pass postpay, expose conflict |
| confirmed | conflict | no advance | pass protected, expose conflict |
| confirmed | unavailable | internal protected prepayment | pass protected |
| confirmed | unknown | optional risky external alternative | pass protected |
| any | any | mandatory global external advance | manual |
| any | any | global conflict | manual |
| partial or generic badge | unavailable | no advance | manual |
| seller claims protected | unavailable | no platform transaction evidence | manual |
