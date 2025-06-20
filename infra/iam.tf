data "aws_region" "current" {}

data "aws_caller_identity" "current" {}

data "aws_iam_policy_document" "glue_assume" {
  statement {
    actions    = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["glue.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "glue_role" {
  name               = "SkuSenseGlueRole"
  assume_role_policy = data.aws_iam_policy_document.glue_assume.json
}

resource "aws_iam_policy" "glue_s3_access" {
  name   = "SkuSenseGlueS3Access"
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      #-----S3 Access
      {
        Action   = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket"
        ],
        Effect   = "Allow",
        Resource = [
          aws_s3_bucket.raw_data.arn,
          "${aws_s3_bucket.raw_data.arn}/*",
          "${aws_s3_bucket.raw_data.arn}/bronze/*",
          "${aws_s3_bucket.raw_data.arn}/silver/*",
        ]
      },
      #-----CloudWatch Logs
      {
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ],
        Effect = "Allow",
        Resource = "arn:aws:logs:*:${data.aws_caller_identity.current.account_id}:log-group:/aws-glue/*"
      },
      #-----Glue Catalog access
      {
        Action = [
          # read / write
          "glue:GetDatabase",
          "glue:GetDatabases",
          "glue:CreateDatabase",         # ← NEW
          "glue:DeleteDatabase",         # safe cleanup
          "glue:GetTable",
          "glue:CreateTable",
          "glue:UpdateTable",
          "glue:DeleteTable"
        ],
        Effect = "Allow",
        Resource = [
          # whole catalog for CreateDatabase
          "arn:aws:glue:*:${data.aws_caller_identity.current.account_id}:catalog",

          # explicit project DBs
          "arn:aws:glue:*:${data.aws_caller_identity.current.account_id}:database/skusense_raw_db",
          "arn:aws:glue:*:${data.aws_caller_identity.current.account_id}:table/skusense_raw_db/*",

          # allow the default DB probe
          "arn:aws:glue:*:${data.aws_caller_identity.current.account_id}:database/default"
        ]
      },
      {
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ],
        Effect = "Allow",
        Resource = [
          # Glue’s asset bucket for your account / region
          "arn:aws:s3:::aws-glue-assets-${data.aws_caller_identity.current.account_id}-us-east-1",
          "arn:aws:s3:::aws-glue-assets-${data.aws_caller_identity.current.account_id}-us-east-1/*"
        ]
      },
    ]
  })
}

resource "aws_iam_role_policy_attachment" "attach_s3" {
  role       = aws_iam_role.glue_role.name
  policy_arn = aws_iam_policy.glue_s3_access.arn
}
