

resource "aws_iam_role" "snowflake_integration_role" {
  name = "SkuSense_SnowflakeIntegrationRole"
  assume_role_policy = <<POLICY
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::375609200837:user/gds11000-s"
      },
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": {
          "sts:ExternalId": "RM39814_SFCRole=4_D2/p8sg4w1pMi9V9GPD6H2MI86s="
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
      Action   = ["s3:GetObject","s3:PutObject","s3:ListBucket"],
      Resource = [
        aws_s3_bucket.raw_data.arn,
        "${aws_s3_bucket.raw_data.arn}/*",
        "${aws_s3_bucket.raw_data.arn}/bronze/*",
        "${aws_s3_bucket.raw_data.arn}/silver/*",
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