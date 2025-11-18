# AWS Cloud Cost Optimizer

A comprehensive solution for collecting AWS billing data from CloudWatch and Cost Explorer, then pushing the metrics to Prometheus for monitoring and analysis.

## Features

- **Automated Data Collection**: GitHub Actions workflow that runs every 6 hours
- **Multiple Data Sources**: 
  - AWS CloudWatch Billing metrics
  - AWS Cost Explorer API
  - AWS Budgets information
- **Prometheus Integration**: Push metrics to Prometheus via Pushgateway
- **Grafana Ready**: Metrics formatted for easy visualization
- **Error Handling**: Robust error handling with detailed logging
- **Flexible Deployment**: Support for both GitHub Actions and local development

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  AWS Services   │    │ GitHub Actions  │    │   Prometheus    │
│                 │    │                 │    │                 │
│ • CloudWatch    │───▶│ • Collect Data  │───▶│ • Pushgateway   │
│ • Cost Explorer │    │ • Transform     │    │ • Time Series   │
│ • Budgets       │    │ • Push Metrics  │    │ • Grafana       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Metrics Collected

### Cost Metrics
- `aws_billing_blended_cost_usd`: Blended cost by service
- `aws_billing_unblended_cost_usd`: Unblended cost by service
- `aws_billing_estimated_charges_total_usd`: Total estimated charges
- `aws_billing_estimated_charges_by_service_usd`: Estimated charges by service

### Budget Metrics
- `aws_budget_limit_usd`: Budget limits
- `aws_budget_actual_spend_usd`: Actual spend against budgets
- `aws_budget_forecasted_spend_usd`: Forecasted spend
- `aws_budget_utilization_percentage`: Budget utilization percentage

## Setup

### Prerequisites

1. **AWS Account**: With appropriate permissions for billing data
2. **AWS IAM Role/User**: With the following permissions:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": [
           "cloudwatch:GetMetricStatistics",
           "cloudwatch:ListMetrics",
           "ce:GetCostAndUsage",
           "ce:GetDimensionValues",
           "budgets:DescribeBudgets",
           "budgets:DescribeBudgetPerformanceHistory"
         ],
         "Resource": "*"
       }
     ]
   }
   ```
3. **Prometheus Pushgateway**: Accessible endpoint for pushing metrics

### GitHub Secrets Configuration

Add the following secrets to your GitHub repository:

#### Required Secrets
- `AWS_ROLE_ARN`: ARN of the IAM role for OIDC authentication (recommended)
  - OR `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` for key-based auth
- `AWS_ACCOUNT_ID`: Your AWS account ID (12-digit number)
- `PROMETHEUS_PUSHGATEWAY_URL`: URL of your Prometheus Pushgateway (e.g., `https://pushgateway.example.com`)

#### Optional Secrets
- `SLACK_WEBHOOK_URL`: Slack webhook for failure notifications

### AWS OIDC Setup (Recommended)

1. Create an OIDC identity provider in AWS IAM:
   ```bash
   aws iam create-open-id-connect-provider \
     --url https://token.actions.githubusercontent.com \
     --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1 \
     --client-id-list sts.amazonaws.com
   ```

2. Create an IAM role with trust policy:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Principal": {
           "Federated": "arn:aws:iam::ACCOUNT-ID:oidc-provider/token.actions.githubusercontent.com"
         },
         "Action": "sts:AssumeRoleWithWebIdentity",
         "Condition": {
           "StringEquals": {
             "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
             "token.actions.githubusercontent.com:sub": "repo:YOUR-USERNAME/cloud-cost-optimizer:ref:refs/heads/main"
           }
         }
       }
     ]
   }
   ```

## Local Development

### Using Docker Compose

1. **Clone the repository**:
   ```bash
   git clone https://github.com/your-username/cloud-cost-optimizer.git
   cd cloud-cost-optimizer
   ```

2. **Set up environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env with your AWS credentials and configuration
   ```

3. **Start the monitoring stack**:
   ```bash
   docker-compose up -d prometheus pushgateway grafana
   ```

4. **Run the billing collector**:
   ```bash
   docker-compose up billing-collector
   ```

5. **Access the services**:
   - Prometheus: http://localhost:9090
   - Pushgateway: http://localhost:9091
   - Grafana: http://localhost:3000 (admin/admin)

### Manual Setup

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Set environment variables**:
   ```bash
   export AWS_ACCESS_KEY_ID="your-key"
   export AWS_SECRET_ACCESS_KEY="your-secret"
   export AWS_REGION="us-east-1"
   export AWS_ACCOUNT_ID="123456789012"
   export PROMETHEUS_PUSHGATEWAY_URL="http://localhost:9091"
   ```

3. **Run the collector**:
   ```bash
   python scripts/collect_billing_data.py
   ```

4. **Push to Prometheus**:
   ```bash
   python scripts/push_to_prometheus.py
   ```

## Configuration

### Workflow Configuration

The GitHub Actions workflow can be configured by modifying `.github/workflows/aws-billing-collector.yml`:

- **Schedule**: Change the cron expression to adjust collection frequency
- **AWS Region**: Modify the `AWS_REGION` environment variable
- **Timeout**: Adjust step timeouts as needed

### Application Configuration

Modify `config/config.yml` to customize:

- AWS services to monitor
- Collection parameters
- Prometheus settings
- Notification preferences
- Logging configuration

## Monitoring and Alerts

### Grafana Dashboards

Create dashboards in Grafana using the collected metrics:

1. **Cost Overview Dashboard**:
   - Total costs over time
   - Cost breakdown by service
   - Month-over-month comparison

2. **Budget Monitoring Dashboard**:
   - Budget utilization
   - Forecasted vs actual spend
   - Budget alerts

3. **Service Deep Dive**:
   - Individual service costs
   - Usage trends
   - Cost optimization opportunities

### Example Queries

```promql
# Total AWS costs
sum(aws_billing_estimated_charges_total_usd)

# Cost by service
sum by (service) (aws_billing_estimated_charges_by_service_usd)

# Budget utilization over 80%
aws_budget_utilization_percentage > 80

# Month-over-month cost increase
increase(aws_billing_estimated_charges_total_usd[30d])
```

## Troubleshooting

### Common Issues

1. **AWS Permissions**: Ensure your IAM role/user has the required permissions
2. **Region**: Billing metrics are only available in `us-east-1`
3. **Pushgateway Connection**: Verify the Pushgateway URL is accessible
4. **Data Delay**: AWS billing data may have a delay of up to 24 hours

### Logs

Check the workflow logs in GitHub Actions or local logs in the `logs/` directory:

- `logs/billing_collector.log`: Data collection logs
- `logs/prometheus_pusher.log`: Metric push logs

### Manual Testing

Test individual components:

```bash
# Test AWS connection
python -c "import boto3; print(boto3.client('sts').get_caller_identity())"

# Test Pushgateway connection
curl -X GET http://your-pushgateway:9091/-/healthy

# Validate metrics format
python scripts/collect_billing_data.py
cat data/billing_metrics.json | jq '.[0]'
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Security

- Use IAM roles with minimal required permissions
- Store sensitive data in GitHub Secrets
- Regularly rotate access keys if using key-based authentication
- Monitor access logs for unusual activity

## Cost Considerations

- The GitHub Actions workflow runs on GitHub's servers (included in your plan)
- AWS API calls are typically free for billing/cost data
- Prometheus storage costs depend on your deployment
- Consider adjusting collection frequency based on your needs
