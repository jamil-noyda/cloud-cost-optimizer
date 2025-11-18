#!/usr/bin/env python3
"""
Prometheus Pushgateway Client

This script pushes the collected AWS billing metrics to Prometheus via the Pushgateway.
"""

import os
import json
import logging
import requests
import datetime
from typing import Dict, List, Any
from urllib.parse import urljoin
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/prometheus_pusher.log', mode='a'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class PrometheusMetricFormatter:
    """Formats metrics for Prometheus Pushgateway"""
    
    @staticmethod
    def sanitize_metric_name(name: str) -> str:
        """Sanitize metric name for Prometheus"""
        # Replace invalid characters with underscores
        import re
        return re.sub(r'[^a-zA-Z0-9_:]', '_', name)
    
    @staticmethod
    def sanitize_label_name(name: str) -> str:
        """Sanitize label name for Prometheus"""
        import re
        return re.sub(r'[^a-zA-Z0-9_]', '_', name)
    
    @staticmethod
    def sanitize_label_value(value: str) -> str:
        """Sanitize label value for Prometheus"""
        # Escape quotes and backslashes
        return str(value).replace('\\', '\\\\').replace('"', '\\"')
    
    @staticmethod
    def format_metric_for_pushgateway(metric_data: Dict[str, Any]) -> str:
        """Format a single metric for Pushgateway"""
        name = PrometheusMetricFormatter.sanitize_metric_name(metric_data['name'])
        value = metric_data['value']
        labels = metric_data.get('labels', {})
        help_text = metric_data.get('help_text', '')
        
        # Build labels string
        label_pairs = []
        for label_name, label_value in labels.items():
            clean_name = PrometheusMetricFormatter.sanitize_label_name(label_name)
            clean_value = PrometheusMetricFormatter.sanitize_label_value(label_value)
            label_pairs.append(f'{clean_name}="{clean_value}"')
        
        labels_str = ','.join(label_pairs)
        if labels_str:
            labels_str = '{' + labels_str + '}'
        
        # Format the metric
        lines = []
        if help_text:
            lines.append(f'# HELP {name} {help_text}')
            lines.append(f'# TYPE {name} gauge')
        
        lines.append(f'{name}{labels_str} {value}')
        
        return '\n'.join(lines)

class PrometheusPusher:
    """Pushes metrics to Prometheus Pushgateway"""
    
    def __init__(self, pushgateway_url: str, job_name: str = 'aws-billing-collector'):
        self.pushgateway_url = pushgateway_url.rstrip('/')
        self.job_name = job_name
        self.session = requests.Session()
        
        # Set reasonable timeouts
        self.session.timeout = (10, 30)  # (connect, read) timeout
        
        logger.info(f"Initialized Prometheus pusher for {pushgateway_url}, job: {job_name}")
    
    def push_metrics(self, metrics_data: List[Dict[str, Any]], instance: str = None) -> bool:
        """Push metrics to Pushgateway"""
        if not metrics_data:
            logger.warning("No metrics to push")
            return True
        
        try:
            # Group metrics by name for better organization
            grouped_metrics = {}
            for metric in metrics_data:
                metric_name = metric['name']
                if metric_name not in grouped_metrics:
                    grouped_metrics[metric_name] = []
                grouped_metrics[metric_name].append(metric)
            
            # Format all metrics
            formatted_metrics = []
            for metric_name, metrics_list in grouped_metrics.items():
                # Add HELP and TYPE only once per metric name
                if metrics_list:
                    first_metric = metrics_list[0]
                    help_text = first_metric.get('help_text', '')
                    if help_text:
                        formatted_metrics.append(f'# HELP {metric_name} {help_text}')
                        formatted_metrics.append(f'# TYPE {metric_name} gauge')
                
                # Add all metric instances
                for metric in metrics_list:
                    metric_line = PrometheusMetricFormatter.format_metric_for_pushgateway(metric)
                    # Remove HELP and TYPE lines as we added them above
                    lines = metric_line.split('\n')
                    for line in lines:
                        if not line.startswith('#'):
                            formatted_metrics.append(line)
            
            # Join all metrics
            metrics_payload = '\n'.join(formatted_metrics)
            
            # Build URL for pushgateway
            url_parts = [self.pushgateway_url, 'metrics', 'job', self.job_name]
            if instance:
                url_parts.extend(['instance', instance])
            
            push_url = '/'.join(url_parts)
            
            # Log the payload for debugging (truncated)
            payload_preview = metrics_payload[:500] + '...' if len(metrics_payload) > 500 else metrics_payload
            logger.debug(f"Pushing metrics to {push_url}:\n{payload_preview}")
            
            # Push to Pushgateway
            response = self.session.post(
                push_url,
                data=metrics_payload,
                headers={'Content-Type': 'text/plain; version=0.0.4'},
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info(f"Successfully pushed {len(metrics_data)} metrics to Prometheus")
                return True
            else:
                logger.error(f"Failed to push metrics. Status: {response.status_code}, Response: {response.text}")
                return False
                
        except requests.exceptions.Timeout:
            logger.error("Timeout while pushing metrics to Prometheus")
            return False
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error while pushing metrics: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error while pushing metrics: {str(e)}")
            return False
    
    def push_metrics_individually(self, metrics_data: List[Dict[str, Any]], instance: str = None) -> bool:
        """Push metrics individually (fallback method)"""
        success_count = 0
        
        for i, metric in enumerate(metrics_data):
            try:
                success = self.push_metrics([metric], instance)
                if success:
                    success_count += 1
                else:
                    logger.warning(f"Failed to push metric {i+1}/{len(metrics_data)}: {metric.get('name', 'unknown')}")
                
                # Add small delay to avoid overwhelming the pushgateway
                if i > 0 and i % 10 == 0:
                    time.sleep(0.1)
                    
            except Exception as e:
                logger.error(f"Error pushing individual metric {i+1}: {str(e)}")
                continue
        
        logger.info(f"Successfully pushed {success_count}/{len(metrics_data)} metrics individually")
        return success_count > 0
    
    def delete_metrics(self, instance: str = None) -> bool:
        """Delete metrics from Pushgateway"""
        try:
            url_parts = [self.pushgateway_url, 'metrics', 'job', self.job_name]
            if instance:
                url_parts.extend(['instance', instance])
            
            delete_url = '/'.join(url_parts)
            
            response = self.session.delete(delete_url, timeout=10)
            
            if response.status_code == 202:
                logger.info("Successfully deleted metrics from Prometheus")
                return True
            else:
                logger.warning(f"Delete request returned status: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error deleting metrics: {str(e)}")
            return False
    
    def health_check(self) -> bool:
        """Check if Pushgateway is healthy"""
        try:
            health_url = urljoin(self.pushgateway_url, '/-/healthy')
            response = self.session.get(health_url, timeout=5)
            
            if response.status_code == 200:
                logger.info("Pushgateway health check passed")
                return True
            else:
                logger.warning(f"Pushgateway health check failed with status: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Pushgateway health check failed: {str(e)}")
            return False

def load_metrics_from_file(filename: str = 'data/billing_metrics.json') -> List[Dict[str, Any]]:
    """Load metrics from JSON file"""
    try:
        with open(filename, 'r') as f:
            metrics_data = json.load(f)
        
        logger.info(f"Loaded {len(metrics_data)} metrics from {filename}")
        return metrics_data
        
    except FileNotFoundError:
        logger.error(f"Metrics file not found: {filename}")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in metrics file: {str(e)}")
        return []
    except Exception as e:
        logger.error(f"Error loading metrics file: {str(e)}")
        return []

def main():
    """Main execution function"""
    try:
        # Create logs directory
        os.makedirs('logs', exist_ok=True)
        
        logger.info("Starting Prometheus metrics push")
        
        # Get configuration
        pushgateway_url = os.getenv('PROMETHEUS_PUSHGATEWAY_URL')
        job_name = os.getenv('PROMETHEUS_JOB_NAME', 'aws-billing-collector')
        instance_name = os.getenv('PROMETHEUS_INSTANCE_NAME', 'github-actions')
        
        if not pushgateway_url:
            logger.error("PROMETHEUS_PUSHGATEWAY_URL environment variable is required")
            return False
        
        # Load metrics
        metrics_data = load_metrics_from_file()
        if not metrics_data:
            logger.error("No metrics to push")
            return False
        
        # Initialize pusher
        pusher = PrometheusPusher(pushgateway_url, job_name)
        
        # Health check
        if not pusher.health_check():
            logger.warning("Pushgateway health check failed, but continuing...")
        
        # Try to push all metrics at once first
        logger.info(f"Attempting to push {len(metrics_data)} metrics to Prometheus...")
        success = pusher.push_metrics(metrics_data, instance_name)
        
        # If batch push fails, try individual pushes
        if not success:
            logger.warning("Batch push failed, trying individual pushes...")
            success = pusher.push_metrics_individually(metrics_data, instance_name)
        
        if success:
            logger.info("Successfully completed metrics push to Prometheus")
            
            # Save a summary
            summary = {
                'timestamp': datetime.datetime.now().isoformat(),
                'total_metrics': len(metrics_data),
                'pushgateway_url': pushgateway_url,
                'job_name': job_name,
                'instance_name': instance_name,
                'status': 'success'
            }
            
            with open('data/push_summary.json', 'w') as f:
                json.dump(summary, f, indent=2)
            
            return True
        else:
            logger.error("Failed to push metrics to Prometheus")
            return False
            
    except Exception as e:
        logger.error(f"Unexpected error in main: {str(e)}")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)