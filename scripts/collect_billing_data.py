#!/usr/bin/env python3
"""
AWS Billing Data Collector

This script fetches billing and cost data from AWS CloudWatch and prepares it
for ingestion into Prometheus via the Pushgateway.
"""

import os
import json
import logging
import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/billing_collector.log', mode='a'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class BillingMetric:
    """Represents a billing metric for Prometheus"""
    name: str
    value: float
    labels: Dict[str, str]
    timestamp: datetime.datetime
    help_text: str = ""

class AWSBillingCollector:
    """Collects billing data from AWS CloudWatch"""
    
    def __init__(self):
        self.region = os.getenv('AWS_REGION', 'us-east-1')
        self.account_id = os.getenv('AWS_ACCOUNT_ID', '')
        
        # Initialize AWS clients
        try:
            self.cloudwatch = boto3.client('cloudwatch', region_name=self.region)
            self.ce_client = boto3.client('ce', region_name=self.region)  # Cost Explorer
            logger.info(f"Initialized AWS clients for region: {self.region}")
        except NoCredentialsError:
            logger.error("AWS credentials not found. Please configure AWS credentials.")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize AWS clients: {str(e)}")
            raise
    
    def get_current_costs(self, days_back: int = 1) -> List[BillingMetric]:
        """Get current costs from AWS Cost Explorer"""
        metrics = []
        
        try:
            end_date = datetime.datetime.now().date()
            start_date = end_date - datetime.timedelta(days=days_back)
            
            # Get cost by service
            response = self.ce_client.get_cost_and_usage(
                TimePeriod={
                    'Start': start_date.strftime('%Y-%m-%d'),
                    'End': end_date.strftime('%Y-%m-%d')
                },
                Granularity='DAILY',
                Metrics=['BlendedCost', 'UnblendedCost', 'UsageQuantity'],
                GroupBy=[
                    {'Type': 'DIMENSION', 'Key': 'SERVICE'},
                ]
            )
            
            current_time = datetime.datetime.now()
            
            for result in response['ResultsByTime']:
                date = result['TimePeriod']['Start']
                
                for group in result['Groups']:
                    service = group['Keys'][0] if group['Keys'] else 'Unknown'
                    
                    # BlendedCost metric
                    blended_cost = float(group['Metrics']['BlendedCost']['Amount'])
                    if blended_cost > 0:
                        metrics.append(BillingMetric(
                            name='aws_billing_blended_cost_usd',
                            value=blended_cost,
                            labels={
                                'service': service,
                                'account_id': self.account_id,
                                'date': date,
                                'currency': group['Metrics']['BlendedCost']['Unit']
                            },
                            timestamp=current_time,
                            help_text='AWS blended cost by service in USD'
                        ))
                    
                    # UnblendedCost metric
                    unblended_cost = float(group['Metrics']['UnblendedCost']['Amount'])
                    if unblended_cost > 0:
                        metrics.append(BillingMetric(
                            name='aws_billing_unblended_cost_usd',
                            value=unblended_cost,
                            labels={
                                'service': service,
                                'account_id': self.account_id,
                                'date': date,
                                'currency': group['Metrics']['UnblendedCost']['Unit']
                            },
                            timestamp=current_time,
                            help_text='AWS unblended cost by service in USD'
                        ))
            
            logger.info(f"Collected {len(metrics)} cost metrics")
            
        except Exception as e:
            logger.error(f"Failed to get cost data: {str(e)}")
            
        return metrics
    
    def get_cloudwatch_billing_metrics(self) -> List[BillingMetric]:
        """Get billing metrics from CloudWatch"""
        metrics = []
        
        try:
            # Get estimated charges
            response = self.cloudwatch.get_metric_statistics(
                Namespace='AWS/Billing',
                MetricName='EstimatedCharges',
                Dimensions=[
                    {'Name': 'Currency', 'Value': 'USD'},
                ],
                StartTime=datetime.datetime.now() - datetime.timedelta(days=1),
                EndTime=datetime.datetime.now(),
                Period=86400,  # 1 day
                Statistics=['Maximum']
            )
            
            current_time = datetime.datetime.now()
            
            for datapoint in response['Datapoints']:
                metrics.append(BillingMetric(
                    name='aws_billing_estimated_charges_total_usd',
                    value=datapoint['Maximum'],
                    labels={
                        'account_id': self.account_id,
                        'currency': 'USD'
                    },
                    timestamp=current_time,
                    help_text='AWS total estimated charges in USD'
                ))
            
            # Get estimated charges by service
            services_response = self.cloudwatch.list_metrics(
                Namespace='AWS/Billing',
                MetricName='EstimatedCharges'
            )
            
            services = set()
            for metric in services_response['Metrics']:
                for dimension in metric['Dimensions']:
                    if dimension['Name'] == 'ServiceName':
                        services.add(dimension['Value'])
            
            # Get metrics for each service
            for service in services:
                try:
                    service_response = self.cloudwatch.get_metric_statistics(
                        Namespace='AWS/Billing',
                        MetricName='EstimatedCharges',
                        Dimensions=[
                            {'Name': 'Currency', 'Value': 'USD'},
                            {'Name': 'ServiceName', 'Value': service}
                        ],
                        StartTime=datetime.datetime.now() - datetime.timedelta(days=1),
                        EndTime=datetime.datetime.now(),
                        Period=86400,
                        Statistics=['Maximum']
                    )
                    
                    for datapoint in service_response['Datapoints']:
                        metrics.append(BillingMetric(
                            name='aws_billing_estimated_charges_by_service_usd',
                            value=datapoint['Maximum'],
                            labels={
                                'service': service,
                                'account_id': self.account_id,
                                'currency': 'USD'
                            },
                            timestamp=current_time,
                            help_text='AWS estimated charges by service in USD'
                        ))
                        
                except Exception as e:
                    logger.warning(f"Failed to get metrics for service {service}: {str(e)}")
                    continue
            
            logger.info(f"Collected {len(metrics)} CloudWatch billing metrics")
            
        except Exception as e:
            logger.error(f"Failed to get CloudWatch billing metrics: {str(e)}")
            
        return metrics
    
    def get_budget_metrics(self) -> List[BillingMetric]:
        """Get budget information"""
        metrics = []
        
        try:
            budgets_client = boto3.client('budgets', region_name=self.region)
            
            # List all budgets
            response = budgets_client.describe_budgets(
                AccountId=self.account_id
            )
            
            current_time = datetime.datetime.now()
            
            for budget in response.get('Budgets', []):
                budget_name = budget['BudgetName']
                budget_limit = float(budget['BudgetLimit']['Amount'])
                
                # Get budget performance
                perf_response = budgets_client.describe_budget_performance_history(
                    AccountId=self.account_id,
                    BudgetName=budget_name,
                    TimePeriod={
                        'Start': datetime.datetime.now() - datetime.timedelta(days=30),
                        'End': datetime.datetime.now()
                    }
                )
                
                if perf_response.get('BudgetPerformanceHistory'):
                    latest_performance = perf_response['BudgetPerformanceHistory'][-1]
                    actual_spend = float(latest_performance.get('ActualCost', {}).get('Amount', 0))
                    forecasted_spend = float(latest_performance.get('ForecastedCost', {}).get('Amount', 0))
                    
                    # Budget limit metric
                    metrics.append(BillingMetric(
                        name='aws_budget_limit_usd',
                        value=budget_limit,
                        labels={
                            'budget_name': budget_name,
                            'account_id': self.account_id,
                            'budget_type': budget.get('BudgetType', 'COST')
                        },
                        timestamp=current_time,
                        help_text='AWS budget limit in USD'
                    ))
                    
                    # Actual spend metric
                    metrics.append(BillingMetric(
                        name='aws_budget_actual_spend_usd',
                        value=actual_spend,
                        labels={
                            'budget_name': budget_name,
                            'account_id': self.account_id,
                            'budget_type': budget.get('BudgetType', 'COST')
                        },
                        timestamp=current_time,
                        help_text='AWS budget actual spend in USD'
                    ))
                    
                    # Forecasted spend metric
                    metrics.append(BillingMetric(
                        name='aws_budget_forecasted_spend_usd',
                        value=forecasted_spend,
                        labels={
                            'budget_name': budget_name,
                            'account_id': self.account_id,
                            'budget_type': budget.get('BudgetType', 'COST')
                        },
                        timestamp=current_time,
                        help_text='AWS budget forecasted spend in USD'
                    ))
                    
                    # Budget utilization percentage
                    utilization = (actual_spend / budget_limit * 100) if budget_limit > 0 else 0
                    metrics.append(BillingMetric(
                        name='aws_budget_utilization_percentage',
                        value=utilization,
                        labels={
                            'budget_name': budget_name,
                            'account_id': self.account_id,
                            'budget_type': budget.get('BudgetType', 'COST')
                        },
                        timestamp=current_time,
                        help_text='AWS budget utilization as percentage'
                    ))
            
            logger.info(f"Collected {len(metrics)} budget metrics")
            
        except Exception as e:
            logger.error(f"Failed to get budget metrics: {str(e)}")
            
        return metrics
    
    def save_metrics_to_file(self, metrics: List[BillingMetric], filename: str = 'data/billing_metrics.json'):
        """Save metrics to JSON file"""
        try:
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            
            metrics_data = []
            for metric in metrics:
                metric_dict = asdict(metric)
                metric_dict['timestamp'] = metric.timestamp.isoformat()
                metrics_data.append(metric_dict)
            
            with open(filename, 'w') as f:
                json.dump(metrics_data, f, indent=2, default=str)
            
            logger.info(f"Saved {len(metrics)} metrics to {filename}")
            
        except Exception as e:
            logger.error(f"Failed to save metrics to file: {str(e)}")

def main():
    """Main execution function"""
    try:
        # Create necessary directories
        os.makedirs('data', exist_ok=True)
        os.makedirs('logs', exist_ok=True)
        
        logger.info("Starting AWS billing data collection")
        
        # Initialize collector
        collector = AWSBillingCollector()
        
        # Collect all metrics
        all_metrics = []
        
        # Get current costs
        logger.info("Collecting current costs...")
        cost_metrics = collector.get_current_costs(days_back=2)
        all_metrics.extend(cost_metrics)
        
        # Get CloudWatch billing metrics
        logger.info("Collecting CloudWatch billing metrics...")
        cw_metrics = collector.get_cloudwatch_billing_metrics()
        all_metrics.extend(cw_metrics)
        
        # Get budget metrics (only if account ID is provided)
        if collector.account_id:
            logger.info("Collecting budget metrics...")
            budget_metrics = collector.get_budget_metrics()
            all_metrics.extend(budget_metrics)
        else:
            logger.warning("AWS_ACCOUNT_ID not provided, skipping budget metrics")
        
        # Save metrics to file
        collector.save_metrics_to_file(all_metrics)
        
        logger.info(f"Successfully collected {len(all_metrics)} total metrics")
        
        # Print summary
        metric_counts = {}
        for metric in all_metrics:
            metric_counts[metric.name] = metric_counts.get(metric.name, 0) + 1
        
        logger.info("Metric summary:")
        for metric_name, count in metric_counts.items():
            logger.info(f"  {metric_name}: {count} data points")
        
    except Exception as e:
        logger.error(f"Failed to collect billing data: {str(e)}")
        raise

if __name__ == "__main__":
    main()