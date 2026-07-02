from aws_cdk import CfnOutput, Stack, Tags, aws_ec2 as ec2
from constructs import Construct


class NetworkStack(Stack):

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        analytics_allowed_cidr: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        allowed_cidr = self._resolve_analytics_allowed_cidr(analytics_allowed_cidr)

        self.vpc = ec2.Vpc(
            self,
            "PipelineVpc",
            max_azs=2,
            nat_gateways=1,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                ),
                ec2.SubnetConfiguration(
                    name="private-egress",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=24,
                ),
            ],
        )
        Tags.of(self.vpc).add("Name", "social-pipeline-vpc")

        self.vpc.add_gateway_endpoint(
            "S3GatewayEndpoint",
            service=ec2.GatewayVpcEndpointAwsService.S3,
        )

        self.pipeline_lambda_security_group = ec2.SecurityGroup(
            self,
            "PipelineLambdaSecurityGroup",
            vpc=self.vpc,
            allow_all_outbound=True,
            description="Security group for pipeline Lambda functions.",
        )
        Tags.of(self.pipeline_lambda_security_group).add(
            "Name", "social-pipeline-lambda-sg"
        )

        self.analytics_security_group = ec2.SecurityGroup(
            self,
            "AnalyticsSecurityGroup",
            vpc=self.vpc,
            allow_all_outbound=True,
            description="Security group for analytics EC2, PostgreSQL, and Superset.",
        )
        Tags.of(self.analytics_security_group).add(
            "Name", "social-analytics-shared-sg"
        )

        self.analytics_security_group.add_ingress_rule(
            ec2.Peer.ipv4(allowed_cidr),
            ec2.Port.tcp(8088),
            "Superset web UI access from the configured analytics CIDR.",
        )
        self.analytics_security_group.add_ingress_rule(
            self.pipeline_lambda_security_group,
            ec2.Port.tcp(5432),
            "PostgreSQL access from pipeline Lambda functions.",
        )

        CfnOutput(self, "VpcId", value=self.vpc.vpc_id)
        CfnOutput(
            self,
            "PipelineLambdaSecurityGroupId",
            value=self.pipeline_lambda_security_group.security_group_id,
        )
        CfnOutput(
            self,
            "AnalyticsSecurityGroupId",
            value=self.analytics_security_group.security_group_id,
        )

    def _resolve_analytics_allowed_cidr(
        self, analytics_allowed_cidr: str | None
    ) -> str:
        if analytics_allowed_cidr:
            return analytics_allowed_cidr

        context_cidr = self.node.try_get_context("analytics_allowed_cidr")
        if context_cidr:
            return str(context_cidr)

        raise ValueError(
            "analytics_allowed_cidr is required for NetworkStack. "
            "Pass it with '-c analytics_allowed_cidr=x.x.x.x/32'."
        )
