# AWS Cost-Safe Demo Checklist

Use this checklist before running any AWS demo resources for the social data
pipeline. Do not deploy unless the demo needs live AWS infrastructure.

## Before Deploy

- Run `cdk synth` first and inspect the generated resources.
- Use `analytics_allowed_cidr` with your own `/32` public IP, not
  `0.0.0.0/0`.
- Remember that `NetworkStack` creates one NAT Gateway for private Lambda
  egress. Destroy the demo stacks when they are no longer needed.
- Prefer `analytics_instance_type=t3.micro` when Superset performance is
  acceptable.
- Keep `analytics_auto_stop_enabled=true`.
- Set `analytics_auto_stop_utc_hour` to a UTC hour after the planned demo.
- Do not commit real passwords, Superset admin credentials, or Superset secret
  keys.
- Check AWS Billing and Budgets in the console before creating resources.

## During Demo

- Keep the AWS console open to the EC2 instance or CloudFormation stack.
- Confirm the instance ID and public IP match the `AnalyticsStack` outputs.
- Avoid opening extra ports or changing the security group beyond the demo
  requirements.
- Do not add public tcp/5432 ingress. PostgreSQL access should come from
  `PipelineLambdaSecurityGroup` to `AnalyticsSecurityGroup`.
- Take screenshots and export any demo evidence while the instance is running.

## After Demo

- Stop the EC2 instance if you may need it again soon:

```bash
aws ec2 stop-instances --instance-ids INSTANCE_ID
```

- Destroy `AnalyticsStack` after screenshots or the demo if it is no longer
  needed. If the shared VPC is only for the demo, destroy the dependent stacks
  and `NetworkStack` too:

```bash
cd infrastructure
cdk destroy NotificationStack GoldStack SilverStack BronzeStack AnalyticsStack NetworkStack DataLakeStack
```

- Remember that stopped EC2 instances can still have storage and public IP
  related costs.
- Recheck AWS Billing and Budgets in the console.

## Inspect Resources

List EC2 instances with useful fields:

```bash
aws ec2 describe-instances \
  --query 'Reservations[].Instances[].{InstanceId:InstanceId,State:State.Name,Type:InstanceType,PublicIp:PublicIpAddress,Name:Tags[?Key==`Name`]|[0].Value}' \
  --output table
```

Inspect CloudFormation stacks:

```bash
aws cloudformation describe-stacks \
  --query 'Stacks[].{StackName:StackName,Status:StackStatus,Created:CreationTime}' \
  --output table
```
