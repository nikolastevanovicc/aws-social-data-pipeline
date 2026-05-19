# KT1 Test Plan

## Infrastructure tests

- `cdk synth` prolazi bez greske.
- `cdk deploy` kreira S3 bucket, Lambda, IAM policy i EventBridge rule.
- Lambda env var `DATA_LAKE_BUCKET` je postavljena.
- EventBridge schedule je `cron(0 2 * * ? *)`.

## Functional smoke tests

- Invoke sa `{"date":"YYYY-MM-DD"}` vraca summary payload.
- Invoke sa `{}` koristi prethodni dan u UTC.
- CloudWatch log stream postoji za Lambda funkciju.

## Security checks

- Nema `AdministratorAccess`.
- Nema wildcard admin akcija (`*`, `s3:*`, `iam:*`) u custom policy dokumentu.
