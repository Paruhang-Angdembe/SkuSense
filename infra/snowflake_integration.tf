

resource "aws_iam_role" "snowflake_integration_role" {
  name = "SkuSense_SnowflakeIntegrationRole"
  assume_role_policy = <<POLICY
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::250260913919:user/edx91000-s"
        },
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": {
          "sts:ExternalId": "LG51718_SFCRole=2_AZ1GcaL+0EnIpEwR0K59OlXS8e8="
        }
      }
    }
  ]
}
POLICY
}

# Grant it S3 permissions for your buckets
resource "aws_iam_policy" "snowflake_s3_access" {
  name   = "SkuSenseSnowflakeS3Access"
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect   = "Allow",
      Action   = [
        "s3:GetObject",
        "s3:PutObject",
        "s3:ListBucket"
        ],
      Resource = [
        "arn:aws:s3:::${aws_s3_bucket.raw_data.bucket}",
        "arn:aws:s3:::${aws_s3_bucket.raw_data.bucket}/*",
        "arn:aws:s3:::${aws_s3_bucket.raw_data.bucket}/bronze/*",
        "arn:aws:s3:::${aws_s3_bucket.raw_data.bucket}/silver/*",
      ]
    }]
  })
}
resource "aws_iam_role_policy_attachment" "attach_snowflake_s3" {
  role       = aws_iam_role.snowflake_integration_role.name
  policy_arn = aws_iam_policy.snowflake_s3_access.arn
}

output "snowflake_integration_role_arn" {
  description = "ARN of the IAM role Snowflake will assume to read/write S3"
  value       = aws_iam_role.snowflake_integration_role.arn
}