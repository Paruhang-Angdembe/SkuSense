# 1. IAM Role for Step Functions
resource "aws_iam_role" "stepfunctions_role" {
  name = "SkuSense_StepFunctionsRole"
  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect    = "Allow",
      Principal = { Service = "states.amazonaws.com" },
      Action    = "sts:AssumeRole"
    }]
  })
}

# 2. Inline policy allowing it to start your two Glue jobs and write logs
resource "aws_iam_role_policy" "stepfunctions_policy" {
  name = "SkuSense_StepFunctionsPolicy"
  role = aws_iam_role.stepfunctions_role.id
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect   = "Allow",
        Action   = [
          "glue:StartJobRun",
          "glue:GetJobRun",
          "glue:GetJobRuns",
          "glue:BatchStopJobRun"
        ],
        Resource = [
          "arn:aws:glue:us-east-1:${data.aws_caller_identity.current.account_id}:job/bronze_job",
          "arn:aws:glue:us-east-1:${data.aws_caller_identity.current.account_id}:job/silver_job"
        ]
      },
      # CloudWatch Logs permissions
      {
        Effect   = "Allow",
        Action   = [
          "logs:CreateLogDelivery",
          "logs:GetLogDelivery",
          "logs:UpdateLogDelivery",
          "logs:DeleteLogDelivery",
          "logs:ListLogDeliveries",
          "logs:PutResourcePolicy",
          "logs:DescribeResourcePolicies",
          "logs:DescribeLogGroups"
        ],
        Resource = "*"
      },
      # Allow creation of the log-group itself
      {
        Effect   = "Allow",
        Action   = ["logs:CreateLogGroup"],
        Resource = [
          "arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:log-group:/aws/stepfunctions/SkuSense_Pipeline"
        ]
      },
      # Allow writing into any log stream under that group
      {
        Effect   = "Allow",
        Action   = [
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogStreams"
        ],
        Resource = [
          "arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:log-group:/aws/stepfunctions/SkuSense_Pipeline:*"
        ]
      }
    ]
  })
}

# 3. CloudWatch Log Group for Step Functions
# CloudWatch logs will capture every state transition, input/output payload, and error.
resource "aws_cloudwatch_log_group" "sf_logs" {
  name              = "/aws/stepfunctions/SkuSense_Pipeline"
  retention_in_days = 14
}

# 4. The State Machine definition with timeout and retry
resource "aws_sfn_state_machine" "sku_pipeline" {
  name     = "SkuSense_Pipeline"
  role_arn = aws_iam_role.stepfunctions_role.arn
  definition = <<EOF
{
  "Comment": "Pipeline: Bronze → Silver",
  "StartAt": "RunBronze",
  "TimeoutSeconds": 3600,
  "States": {
    "RunBronze": {
      "Type": "Task",
      "Resource": "arn:aws:states:::glue:startJobRun.sync",
      "Parameters": {
        "JobName": "bronze_job",
        "Arguments": {
          "--BUCKET.$": "$.BUCKET"
        }
      },
      "TimeoutSeconds": 1800,
      "Retry": [{
        "ErrorEquals": ["States.ALL"],
        "IntervalSeconds": 30,
        "MaxAttempts": 2,
        "BackoffRate": 2.0
      }],
      "ResultPath": null,
      "Next": "RunSilver"
    },
    "RunSilver": {
      "Type": "Task",
      "Resource": "arn:aws:states:::glue:startJobRun.sync",
      "Parameters": {
        "JobName": "silver_job",
        "Arguments": {
          "--BUCKET.$": "$.BUCKET"
        }
      },
      "TimeoutSeconds": 1800,
      "Retry": [{
        "ErrorEquals": ["States.ALL"],
        "IntervalSeconds": 30,
        "MaxAttempts": 2,
        "BackoffRate": 2.0
      }],
      "ResultPath": null,
      "End": true
    }
  }
}
EOF
  logging_configuration {
    level                   = "ALL"
    include_execution_data  = true
    log_destination         = "${aws_cloudwatch_log_group.sf_logs.arn}:*"
  }
}

# 5. Expose the ARN so you can trigger it later
output "pipeline_arn" {
  description = "ARN of the Glue Bronze→Silver Step Functions pipeline"
  value       = aws_sfn_state_machine.sku_pipeline.arn
}