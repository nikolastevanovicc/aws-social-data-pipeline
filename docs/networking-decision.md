# Networking Decision for KT1

## Decision

Za KT1 Lambdu deployujemo bez VPC attachment-a.

## Rationale

- KT1 cilj je stabilan end-to-end bronze ingestion baseline (`S3 + Lambda + IAM + EventBridge`).
- Lambda bez VPC-a ima direktan outbound pristup ka Hacker News API-ju i smanjuje rizik da demo padne zbog NAT konfiguracije.
- Time zadrzavamo fokus na functional requirement za prvu kontrolnu tacku.

## Planned upgrade for final phase

U finalnoj verziji prelazimo na punu mrežnu usklađenost:
- VPC sa private subnet-ovima za Lambde
- NAT (gateway ili instance) za outbound internet saobracaj
- S3 Gateway Endpoint za privatnu Lambda -> S3 komunikaciju
- Minimalna security group pravila prema least privilege principu
